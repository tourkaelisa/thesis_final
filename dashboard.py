"""Service: δημοφιλέστερα προϊόντα (slideshow) και στατιστικά πίνακα ελέγχου.

Συνδυάζει σημασιολογικά δεδομένα από το GraphDB με δεδομένα συμπεριφοράς
(δημοτικότητα, χρήστες) από τη SQLite.
"""
import db
from config import CATEGORY_CLASSES, CATEGORY_LABELS
from graphdb import query_graphdb, bval


def get_popular_slides() -> list:
    """Το πιο δημοφιλές προϊόν ανά κατηγορία (για το slideshow της αρχικής)."""
    slides = []
    for cat_key, rdf_class in CATEGORY_CLASSES.items():
        query = f"""
        PREFIX gr: <http://purl.org/goodrelations/v1#>
        PREFIX schema1: <http://schema.org/>
        PREFIX pto: <http://www.productontology.org/id/>
        SELECT ?uri ?name ?price ?image
        WHERE {{
            ?uri a {rdf_class} ;
                 gr:name ?name ;
                 schema1:price ?price ;
                 schema1:image ?image .
        }}
        """
        results = query_graphdb(query)
        if not results:
            continue
        rdf_map = {bval(r, "uri"): r for r in results}
        uris = list(rdf_map.keys())
        top = db.get_top_popular(uris)
        if not top:
            continue
        r = rdf_map.get(top["product_uri"])
        if r:
            slides.append({
                "category":      CATEGORY_LABELS[cat_key],
                "categoryRoute": f"/{cat_key}",
                "id":            top["product_uri"],
                "name":          bval(r, "name"),
                "price":         float(bval(r, "price")),
                "image":         bval(r, "image"),
                "popularity":    top["popularity_score"],
            })
    return slides


def get_dashboard_stats() -> dict:
    """Συγκεντρωτικά στοιχεία: από SQLite (χρήστες/δημοτικότητα) + GraphDB (γράφος)."""
    total_users, total_wishlists, total_products, top_rows = db.get_dashboard_db_stats()
    stats = {
        "total_users": total_users,
        "total_wishlists": total_wishlists,
        "total_products": total_products,
    }

    top_products = []
    for row in top_rows:
        uri = row["product_uri"]
        name_res = query_graphdb(
            f"PREFIX gr: <http://purl.org/goodrelations/v1#> "
            f"SELECT ?name WHERE {{ <{uri}> gr:name ?name . }}"
        )
        name = bval(name_res[0], "name") if name_res else uri.split("/")[-1]
        top_products.append({"name": name, "popularity": row["popularity_score"]})
    stats["top_products"] = top_products

    cat_map_dash = {CATEGORY_LABELS[k]: v for k, v in CATEGORY_CLASSES.items()}
    category_counts = []
    avg_prices = []
    for label, rdf_class in cat_map_dash.items():
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

    stats["category_counts"] = category_counts
    stats["avg_prices"] = avg_prices

    brand_res = query_graphdb(
        "PREFIX schema1: <http://schema.org/> "
        "SELECT ?brand (COUNT(?p) AS ?cnt) WHERE { "
        "  ?p schema1:manufacturer ?brand . } "
        "GROUP BY ?brand ORDER BY DESC(?cnt) LIMIT 5"
    )
    top_brands = []
    for row in brand_res:
        brand_uri = bval(row, "brand")
        brand_name = brand_uri.split("Brand_")[-1] if "Brand_" in brand_uri else brand_uri.split("/")[-1]
        top_brands.append({"brand": brand_name, "count": int(bval(row, "cnt"))})
    stats["top_brands"] = top_brands

    return stats
