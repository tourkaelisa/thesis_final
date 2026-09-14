"""Analytics: υπολογισμός όλων των μετρικών του πίνακα ελέγχου και των δημοφιλέστερων στην αρχική σελίδα.
Κάθε μετρική είναι μια αυτοτελής συνάρτηση, η get_dashboard_stats() απλώς τις συνθέτει σε ένα ενιαίο payload για το frontend.
"""
import datetime
import db
from graphdb import query_graphdb, bval


def get_popular_products(limit: int = 8) -> list:
    """Επιστρέφει τα κορυφαία σε δημοτικότητα προϊόντα για προβολή στην Αρχική σελίδα.
    Η αναζήτηση πραγματοποιείται συνδυάζοντας το σκορ από την τοπική SQLite με 
    τα πλήρη σημασιολογικά δεδομένα (όνομα, τιμή, εικόνα) από το GraphDB.
    """
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
    for uri, _ in top:  
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


def _kpi_counts() -> dict:
    """Υπολογίζει τους βασικούς Δείκτες Απόδοσης (KPIs).
    Επιστρέφει το συνολικό πλήθος των εγγεγραμμένων χρηστών, τις συνολικές
    προσθήκες προϊόντων σε λίστες αγαπημένων και το πλήθος των διαθέσιμων προϊόντων.
    """
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


def _product_name(uri: str) -> str:
    """Ανακτά την ονομασία (gr:name) ενός συγκεκριμένου προϊόντος από το GraphDB, 
    κάνοντας χρήση του μοναδικού URI του.
    """
    res = query_graphdb(
        f"PREFIX gr: <http://purl.org/goodrelations/v1#> "
        f"SELECT ?name WHERE {{ <{uri}> gr:name ?name . }}"
    )
    return bval(res[0], "name") if res else uri.split("/")[-1]

def _top_products(limit: int = 5) -> list:
    """Ανακτά τα N πιο δημοφιλή προϊόντα με βάση το τρέχον popularity_score
    από την τοπική βάση δεδομένων, για προβολή στα στατιστικά του Dashboard.
    """
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


def _top_brands(limit: int = 5) -> list:
    """Εντοπίζει τις πιο δημοφιλείς κατασκευάστριες εταιρείες (Top Brands).
    Η αναζήτηση γίνεται μεσω SPARQL query για να βρεθούν τα brands με τα περισσότερα προϊόντα.
    """
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


def get_registrations_timeline(days: int = 30) -> list:
    """Υπολογίζει τη χρονοσειρά (timeline) των εγγραφών νέων χρηστών.
    Ομαδοποιεί τις εγγραφές ανά ημέρα για το επιλεγμένο χρονικό παράθυρο
    και διατηρεί το αθροιστικό σύνολο.
    """
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


def get_wishlist_activity_timeline(days: int = 30) -> list:
    """Υπολογίζει τη χρονοσειρά της δραστηριότητας στις λίστες αγαπημένων (wishlists).
    Μετράει τον όγκο των προσθηκών προϊόντων (βάσει ημερομηνίας) ώστε να αποτυπώσει
    τη συνολική αλληλεπίδραση των χρηστών με την πλατφόρμα.
    """
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


def get_abandoned_products(limit: int = 6) -> list:
    """Εντοπίζει τα 'Εγκαταλελειμμένα' Προϊόντα (Abandoned Products).
    Αυτά ορίζονται ως τα προϊόντα που, ενώ είχαν προστεθεί σε Wishlist στο παρελθόν (total_additions),
    στη συνέχεια αφαιρέθηκαν από τους χρήστες (μειώνοντας το popularity_score).
    Επιστρέφει το ποσοστό εγκατάλειψης (abandonment rate).
    """
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


def get_engagement_stats() -> dict:
    """Υπολογίζει τα στατιστικά αλληλεπίδρασης των χρηστών (User Engagement).
    Ορίζει ως 'ενεργό χρήστη' οποιονδήποτε έχει τουλάχιστον ένα προϊόν στη λίστα αγαπημένων.
    Επιστρέφει τα σύνολα, το ποσοστό συμμετοχής, και τον μέσο όρο αντικειμένων ανά χρήστη, 
    καθώς και την κατανομή μεγέθους λίστας (histogram).
    """
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


def get_dashboard_stats() -> dict:
    """Συγκεντρώνει και επιστρέφει το συνολικό payload (JSON) των μετρικών 
    ώστε να καταναλωθεί με ένα μόνο HTTP αίτημα από το Admin Dashboard.
    """
    return {
        **_kpi_counts(),
        "registrations_timeline": get_registrations_timeline(),
        "wishlist_activity": get_wishlist_activity_timeline(),
        "engagement": get_engagement_stats(),
        "abandoned_products": get_abandoned_products(),
        "top_products": _top_products(),
        "top_brands": _top_brands(),
    }
