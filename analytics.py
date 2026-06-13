"""Analytics: υπολογισμός όλων των μετρικών του πίνακα ελέγχου και του slideshow.

Single source of truth για τα στατιστικά. Συνδυάζει σημασιολογικά δεδομένα από
το GraphDB (προϊόντα, τιμές, κατασκευαστές) με δεδομένα συμπεριφοράς από τη
SQLite (χρήστες, δημοτικότητα, wishlist).

Διαχωρισμός ευθυνών:
  - db.py        → καθαρή πρόσβαση/συναλλαγές στη SQLite
  - graphdb.py   → εκτέλεση SPARQL στο GraphDB
  - analytics.py → ΕΔΩ: υπολογισμός/σύνθεση μετρικών (καμία άλλη λογική analytics
                   δεν πρέπει να ζει σκόρπια σε db.py ή στο main.py)

Κάθε μετρική είναι μια αυτοτελής συνάρτηση· η get_dashboard_stats() απλώς τις
συνθέτει σε ένα ενιαίο payload για το frontend.
"""
import datetime

import db
from config import CATEGORY_CLASSES, CATEGORY_LABELS
from graphdb import query_graphdb, bval


# ───────────────────────────────────── Δημοφιλέστερα προϊόντα (slideshow) ────
def get_popular_products(limit: int = 8) -> list:
    """Τα top-N πιο δημοφιλή προϊόντα συνολικά (για την αρχική σελίδα)."""
    top = db.get_top_popular_uris(limit)
    if not top:
        return []

    pop_map = {uri: score for uri, score in top}
    values = " ".join(f"<{uri}>" for uri, _ in top)
    query = f"""
    PREFIX gr: <http://purl.org/goodrelations/v1#>
    PREFIX schema1: <http://schema.org/>
    SELECT ?uri ?name ?price ?image
    WHERE {{
        VALUES ?uri {{ {values} }}
        ?uri gr:name ?name ;
             schema1:price ?price ;
             schema1:image ?image .
    }}
    """
    results = query_graphdb(query)
    rdf_map = {bval(r, "uri"): r for r in results}

    products = []
    for uri, _ in top:  # διατηρούμε τη σειρά δημοτικότητας
        r = rdf_map.get(uri)
        if not r:
            continue
        products.append({
            "id":         uri,
            "name":       bval(r, "name"),
            "price":      float(bval(r, "price")),
            "image":      bval(r, "image"),
            "popularity": pop_map.get(uri, 0),
        })
    return products


# ──────────────────────────────────────────────────── KPI (συγκεντρωτικά) ────
def _kpi_counts() -> dict:
    """Σύνολα χρηστών, προσθηκών στη wishlist και προϊόντων (από SQLite)."""
    with db.get_db_connection() as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_wishlists = conn.execute(
            "SELECT SUM(total_additions) FROM product_popularity"
        ).fetchone()[0] or 0
        total_products = conn.execute(
            "SELECT COUNT(*) FROM product_popularity"
        ).fetchone()[0]
    return {
        "total_users": total_users,
        "total_wishlists": total_wishlists,
        "total_products": total_products,
    }


# ──────────────────────────────────────────────── Top δημοφιλή προϊόντα ────
def _product_name(uri: str) -> str:
    """Το gr:name ενός προϊόντος από το GraphDB (fallback: το τελευταίο τμήμα του URI)."""
    res = query_graphdb(
        f"PREFIX gr: <http://purl.org/goodrelations/v1#> "
        f"SELECT ?name WHERE {{ <{uri}> gr:name ?name . }}"
    )
    return bval(res[0], "name") if res else uri.split("/")[-1]


def _top_products(limit: int = 10) -> list:
    """Λίστα {name, popularity} για τα δημοφιλέστερα προϊόντα (leaderboard)."""
    with db.get_db_connection() as conn:
        rows = conn.execute(
            "SELECT product_uri, popularity_score FROM product_popularity "
            "ORDER BY popularity_score DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {"name": _product_name(row["product_uri"]), "popularity": row["popularity_score"]}
        for row in rows
    ]


# ───────────────────────────────────────── Κατηγορίες: πλήθος & μέση τιμή ────
def _category_breakdown() -> tuple:
    """Επιστρέφει (category_counts, avg_prices) ανά κατηγορία προϊόντος (από GraphDB)."""
    cat_map = {CATEGORY_LABELS[k]: v for k, v in CATEGORY_CLASSES.items()}
    category_counts = []
    avg_prices = []
    for label, rdf_class in cat_map.items():
        res_count = query_graphdb(
            f"PREFIX pto: <http://www.productontology.org/id/> "
            f"SELECT (COUNT(?u) AS ?c) WHERE {{ ?u a {rdf_class} . }}"
        )
        count = int(bval(res_count[0], "c")) if res_count and bval(res_count[0], "c") else 0
        category_counts.append({"category": label, "count": count})

        res_avg = query_graphdb(
            f"PREFIX pto: <http://www.productontology.org/id/> "
            f"PREFIX schema1: <http://schema.org/> "
            f"SELECT (AVG(?price) AS ?avg) WHERE {{ "
            f"  ?u a {rdf_class} ; schema1:price ?price . }}"
        )
        avg = round(float(bval(res_avg[0], "avg")), 2) if res_avg and bval(res_avg[0], "avg") else 0
        avg_prices.append({"category": label, "avg_price": avg})

    return category_counts, avg_prices


# ───────────────────────────────── Ακρότατα τιμών ανά κατηγορία ────
def _price_extreme(rdf_class: str, ascending: bool) -> dict | None:
    """Το φθηνότερο (ascending) ή ακριβότερο προϊόν μιας κλάσης (όνομα, τιμή, εικόνα)."""
    order = "ASC" if ascending else "DESC"
    res = query_graphdb(
        f"PREFIX pto: <http://www.productontology.org/id/> "
        f"PREFIX gr: <http://purl.org/goodrelations/v1#> "
        f"PREFIX schema1: <http://schema.org/> "
        f"SELECT ?name ?price ?image WHERE {{ "
        f"  ?u a {rdf_class} ; gr:name ?name ; schema1:price ?price . "
        f"  OPTIONAL {{ ?u schema1:image ?image . }} "
        f"}} ORDER BY {order}(?price) LIMIT 1"
    )
    if not res:
        return None
    r = res[0]
    return {
        "name": bval(r, "name"),
        "price": float(bval(r, "price")),
        "image": bval(r, "image") or None,
    }


def get_price_extremes_per_category() -> list:
    """Ανά κατηγορία: το φθηνότερο και το ακριβότερο προϊόν."""
    cat_map = {CATEGORY_LABELS[k]: v for k, v in CATEGORY_CLASSES.items()}
    extremes = []
    for label, rdf_class in cat_map.items():
        cheapest = _price_extreme(rdf_class, ascending=True)
        priciest = _price_extreme(rdf_class, ascending=False)
        if cheapest or priciest:
            extremes.append({"category": label, "cheapest": cheapest, "priciest": priciest})
    return extremes


# ───────────────────────────────────────────────────────── Top brands ────
def _top_brands(limit: int = 5) -> list:
    """Οι κατασκευαστές με τα περισσότερα προϊόντα (από GraphDB)."""
    brand_res = query_graphdb(
        "PREFIX schema1: <http://schema.org/> "
        "SELECT ?brand (COUNT(?p) AS ?cnt) WHERE { "
        "  ?p schema1:manufacturer ?brand . } "
        f"GROUP BY ?brand ORDER BY DESC(?cnt) LIMIT {limit}"
    )
    top_brands = []
    for row in brand_res:
        brand_uri = bval(row, "brand")
        brand_name = brand_uri.split("Brand_")[-1] if "Brand_" in brand_uri else brand_uri.split("/")[-1]
        top_brands.append({"brand": brand_name, "count": int(bval(row, "cnt"))})
    return top_brands


# ─────────────────────────────────────────── Χρονοσειρά εγγραφών χρηστών ────
def get_registrations_timeline(days: int = 30) -> list:
    """Εγγραφές χρηστών ανά ημέρα για τις τελευταίες `days` μέρες.

    Επιστρέφει λίστα από dicts {date, count, cumulative}, με τα κενά διαστήματα
    γεμισμένα με 0 ώστε το γράφημα να είναι συνεχές. Το `cumulative` ξεκινά από
    το σύνολο των χρηστών που είχαν ήδη εγγραφεί πριν το παράθυρο."""
    today = datetime.date.today()
    window_start = today - datetime.timedelta(days=days - 1)
    start_iso = window_start.isoformat()

    with db.get_db_connection() as conn:
        rows = conn.execute(
            "SELECT date(created_at) AS d, COUNT(*) AS c FROM users "
            "WHERE date(created_at) >= ? GROUP BY date(created_at)",
            (start_iso,),
        ).fetchall()
        baseline = conn.execute(
            "SELECT COUNT(*) FROM users WHERE date(created_at) < ?",
            (start_iso,),
        ).fetchone()[0]

    counts = {r["d"]: r["c"] for r in rows}
    timeline = []
    running = baseline
    for offset in range(days):
        day = window_start + datetime.timedelta(days=offset)
        iso = day.isoformat()
        count = counts.get(iso, 0)
        running += count
        timeline.append({"date": iso, "count": count, "cumulative": running})
    return timeline


# ────────────────────────────────────── Δραστηριότητα wishlist (προσθήκες) ────
def get_wishlist_activity_timeline(days: int = 30) -> list:
    """Προσθήκες στη wishlist ανά ημέρα για τις τελευταίες `days` μέρες.

    Μετρά τις γραμμές του πίνακα wishlist βάσει `added_at` (γεμίζει τα κενά με 0).
    Προσοχή: όταν ένας χρήστης αφαιρεί ένα προϊόν, η γραμμή διαγράφεται· άρα η
    σειρά αποτυπώνει τις προσθήκες που παραμένουν ενεργές, ανά ημέρα προσθήκης
    (το σωρευτικό total_additions δεν φέρει χρονοσήμανση)."""
    today = datetime.date.today()
    window_start = today - datetime.timedelta(days=days - 1)
    start_iso = window_start.isoformat()

    with db.get_db_connection() as conn:
        rows = conn.execute(
            "SELECT date(added_at) AS d, COUNT(*) AS c FROM wishlist "
            "WHERE date(added_at) >= ? GROUP BY date(added_at)",
            (start_iso,),
        ).fetchall()

    counts = {r["d"]: r["c"] for r in rows}
    timeline = []
    for offset in range(days):
        iso = (window_start + datetime.timedelta(days=offset)).isoformat()
        timeline.append({"date": iso, "count": counts.get(iso, 0)})
    return timeline


# ───────────────────────────────────────── Προϊόντα που εγκαταλείπονται ────
def get_abandoned_products(limit: int = 6) -> list:
    """Προϊόντα που προστέθηκαν στη wishlist και αργότερα αφαιρέθηκαν.

    abandoned = total_additions − popularity_score (πόσες φορές αφαιρέθηκε).
    Ταξινόμηση κατά φθίνον abandoned· περιλαμβάνει το τρέχον πλήθος (retained),
    τις συνολικές προσθήκες και το ποσοστό εγκατάλειψης."""
    with db.get_db_connection() as conn:
        rows = conn.execute(
            "SELECT product_uri, popularity_score, total_additions, "
            "(total_additions - popularity_score) AS abandoned "
            "FROM product_popularity "
            "WHERE total_additions > popularity_score "
            "ORDER BY abandoned DESC, total_additions DESC LIMIT ?",
            (limit,),
        ).fetchall()

    products = []
    for r in rows:
        additions = r["total_additions"]
        abandoned = r["abandoned"]
        products.append({
            "name": _product_name(r["product_uri"]),
            "abandoned": abandoned,
            "additions": additions,
            "current": r["popularity_score"],
            "rate": round(abandoned / additions * 100) if additions else 0,
        })
    return products


# ───────────────────────────────────────────── Engagement / ενεργοί χρήστες ────
def get_engagement_stats() -> dict:
    """Engagement χρηστών: πόσοι έχουν ≥1 αγαπημένο (ενεργοί) έναντι του συνόλου.

    Περιλαμβάνει επίσης τον μέσο αριθμό αγαπημένων ανά ενεργό χρήστη και την
    κατανομή του μεγέθους της λίστας σε κάδους (1 / 2–3 / 4–5 / 6+)."""
    with db.get_db_connection() as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        # πλήθος αγαπημένων ανά χρήστη — μόνο για όσους έχουν ≥1
        size_rows = conn.execute(
            "SELECT user_id, COUNT(*) AS n FROM wishlist GROUP BY user_id"
        ).fetchall()

    active_users = len(size_rows)
    inactive_users = max(0, total_users - active_users)
    total_items = sum(r["n"] for r in size_rows)
    engagement_rate = round(active_users / total_users * 100, 1) if total_users else 0.0
    avg_items = round(total_items / active_users, 1) if active_users else 0.0

    buckets = [
        {"label": "1 προϊόν", "lo": 1, "hi": 1, "count": 0},
        {"label": "2–3", "lo": 2, "hi": 3, "count": 0},
        {"label": "4–5", "lo": 4, "hi": 5, "count": 0},
        {"label": "6+", "lo": 6, "hi": None, "count": 0},
    ]
    for r in size_rows:
        n = r["n"]
        for b in buckets:
            if n >= b["lo"] and (b["hi"] is None or n <= b["hi"]):
                b["count"] += 1
                break

    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "engagement_rate": engagement_rate,
        "avg_items": avg_items,
        "distribution": [{"label": b["label"], "count": b["count"]} for b in buckets],
    }


# ──────────────────────────────────────── Σύνθεση: πλήρες payload dashboard ────
def get_dashboard_stats() -> dict:
    """Συνθέτει όλες τις μετρικές σε ένα ενιαίο payload για το frontend."""
    category_counts, avg_prices = _category_breakdown()
    return {
        **_kpi_counts(),
        "registrations_timeline": get_registrations_timeline(),
        "wishlist_activity": get_wishlist_activity_timeline(),
        "engagement": get_engagement_stats(),
        "abandoned_products": get_abandoned_products(),
        "top_products": _top_products(),
        "category_counts": category_counts,
        "avg_prices": avg_prices,
        "top_brands": _top_brands(),
    }
