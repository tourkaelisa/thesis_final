"""Analytics: υπολογισμός όλων των μετρικών του πίνακα ελέγχου και των δημοφιλέστερων στην αρχική σελίδα.
Κάθε μετρική είναι μια αυτοτελής συνάρτηση· η get_dashboard_stats() απλώς τις
συνθέτει σε ένα ενιαίο payload για το frontend.
"""
import datetime
import db
from graphdb import query_graphdb, bval


# Δημοφιλέστερα προϊόντα (πλέγμα τοπ 8 δημοφιλεστερων στην αρχική)
def get_popular_products(limit: int = 8) -> list:
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


# KPI (Σύνολα χρηστών, προσθηκών στη wishlist και προϊόντων)
def _kpi_counts() -> dict:
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


# κάνει return το όνομα ενός προϊόντος από το URI του
def _product_name(uri: str) -> str:
    res = query_graphdb(
        f"PREFIX gr: <http://purl.org/goodrelations/v1#> "
        f"SELECT ?name WHERE {{ <{uri}> gr:name ?name . }}"
    )
    return bval(res[0], "name") if res else uri.split("/")[-1]

# τοπ 5 δημοφιλέστερα προϊόντα
def _top_products(limit: int = 5) -> list:
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


# Top brands (με τα περισσότερα προϊόντα)
def _top_brands(limit: int = 5) -> list:
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


# Χρονοσειρά εγγραφών χρηστών ανά ημέρα για τις τελεύταίες 30 μέρες
def get_registrations_timeline(days: int = 30) -> list:
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


# Προσθήκες στο wishlist - Μετρά τις γραμμές του πίνακα wishlist βάσει added_at (ταν ένας χρήστης αφαιρεί ένα προϊόν, η γραμμή διαγράφεται)
def get_wishlist_activity_timeline(days: int = 30) -> list:
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


# Προϊόντα που εγκαταλείπονται (που προστέθηκαν στη wishlist και αργότερα αφαιρέθηκαν) abandoned = total_additions − popularity_score
# περιλαμβάνει το τρέχον πλήθος, τις συνολικές προσθήκες και το ποσοστό εγκατάλειψης
def get_abandoned_products(limit: int = 6) -> list:
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


# ενεργοί χρήστες (όσοι έχουν ≥1 αγαπημένο), μέσος όρος αγαπημένων ανά ενεργό χρήστη, κατανομή μεγέθους λίστας
def get_engagement_stats() -> dict:
    with db.get_db_connection() as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
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


# payload dashboard
def get_dashboard_stats() -> dict:
    return {
        **_kpi_counts(),
        "registrations_timeline": get_registrations_timeline(),
        "wishlist_activity": get_wishlist_activity_timeline(),
        "engagement": get_engagement_stats(),
        "abandoned_products": get_abandoned_products(),
        "top_products": _top_products(),
        "top_brands": _top_brands(),
    }
