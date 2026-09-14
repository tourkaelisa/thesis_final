"""Service λίστας αγαπημένων (wishlist): toggle, αφαίρεση και ανάκτηση προϊόντων."""
import db
from graphdb import query_graphdb

#Toggle ενός προϊόντος στη wishlist
def toggle(user_id, product_uri):
    return db.toggle_wishlist(user_id, product_uri)

#Αφαίρεση ενός προϊόντος από τη wishlist
def remove(user_id, product_uri):
    db.remove_from_wishlist(user_id, product_uri)

#Τα προϊόντα της wishlist ενός χρήστη, με σειρά προσθήκης
def get_products(user_id) -> list:
    uris = db.get_wishlist_uris(user_id)
    if not uris:
        return []
    values_block = " ".join(f"(<{u}>)" for u in uris)
    sparql = f"""
    PREFIX gr: <http://purl.org/goodrelations/v1#>
    PREFIX schema1: <http://schema.org/>
    SELECT ?uri ?name ?price ?image ?brand
    WHERE {{
        VALUES (?uri) {{ {values_block} }}
        ?uri gr:name ?name ;
             schema1:price ?price ;
             schema1:image ?image .
        OPTIONAL {{ ?uri schema1:manufacturer ?bURI .
                    BIND(REPLACE(STR(?bURI), "^.*Brand_", "") AS ?brand) }}
    }}
    """
    bindings = query_graphdb(sparql)
    products = []
    for b in bindings:
        products.append({
            "id":    b["uri"]["value"],
            "name":  b["name"]["value"],
            "price": float(b["price"]["value"]),
            "image": b.get("image", {}).get("value", ""),
            "brand": b.get("brand", {}).get("value", ""),
        })
    uri_order = {u: i for i, u in enumerate(uris)}
    products.sort(key=lambda p: uri_order.get(p["id"], 999))
    return products
