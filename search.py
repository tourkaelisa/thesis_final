"""Απλή αναζήτηση λέξης-κλειδιού πάνω στο GraphDB (όνομα + μάρκα).

Καμία ανάλυση φυσικής γλώσσας: το ερώτημα του χρήστη αντιστοιχίζεται απλώς ως
substring στο όνομα ή τη μάρκα του προϊόντος, μέσω SPARQL CONTAINS. Η σημασιολογική
διάσταση παραμένει στο knowledge graph και στα faceted φίλτρα ανά κατηγορία (filters.py).
"""

# Κλάση οντολογίας -> (route, ετικέτα) για την εμφάνιση κατηγορίας στα αποτελέσματα.
TYPE_INFO = {
    "http://www.productontology.org/id/Laptop":          {"route": "laptops",      "label": "Laptops"},
    "http://www.productontology.org/id/Smartphone":      {"route": "mobiles",      "label": "Mobiles"},
    "http://www.productontology.org/id/Tablet_computer": {"route": "tablets",      "label": "Tablets"},
    "http://www.productontology.org/id/Television_set":  {"route": "tvs",          "label": "Τηλεοράσεις"},
    "http://www.productontology.org/id/Smartwatch":      {"route": "smartwatches", "label": "Smartwatches"},
}

_CLASSES = " ".join(f"pto:{uri.split('/')[-1]}" for uri in TYPE_INFO)

_PREFIXES = """
PREFIX gr: <http://purl.org/goodrelations/v1#>
PREFIX schema1: <http://schema.org/>
PREFIX pto: <http://www.productontology.org/id/>
"""


def _escape(term: str) -> str:
    """Ασφαλής εισαγωγή όρου σε SPARQL string literal."""
    return term.replace("\\", "\\\\").replace('"', '\\"')


def build_sparql(terms: list[str]) -> str:
    """SPARQL που απαιτεί ΚΑΘΕ λέξη να εμφανίζεται στο όνομα Ή στη μάρκα (AND μεταξύ λέξεων)."""
    filters = []
    for t in terms:
        esc = _escape(t)
        filters.append(
            f'    FILTER(CONTAINS(LCASE(STR(?name)), "{esc}") '
            f'|| CONTAINS(LCASE(COALESCE(STR(?brand), "")), "{esc}"))'
        )
    return f"""{_PREFIXES}
SELECT DISTINCT ?uri ?type ?name ?price ?image ?brand
WHERE {{
    VALUES ?type {{ {_CLASSES} }}
    ?uri a ?type ;
         gr:name ?name ;
         schema1:price ?price ;
         schema1:image ?image .
    OPTIONAL {{ ?uri schema1:manufacturer ?bURI .
                BIND(REPLACE(STR(?bURI), "^.*Brand_", "") AS ?brand) }}
{chr(10).join(filters)}
}}
"""


def _format(bindings: list) -> list[dict]:
    seen = set()
    products = []
    for b in bindings:
        uri = b["uri"]["value"]
        if uri in seen:
            continue
        seen.add(uri)
        info = TYPE_INFO.get(b.get("type", {}).get("value", ""), {})
        products.append({
            "id": uri,
            "name": b["name"]["value"],
            "price": float(b["price"]["value"]),
            "image": b.get("image", {}).get("value", ""),
            "brand": b.get("brand", {}).get("value", ""),
            "category": info.get("route", ""),
            "categoryLabel": info.get("label", ""),
        })
    return products


def search(query: str, query_fn, popularity_fn=None) -> list[dict]:
    """Αναζήτηση λέξης-κλειδιού. Επιστρέφει τη λίστα όλων των προϊόντων που
    ταιριάζουν (χωρίς αποκοπή σε πλήθος)."""
    terms = [t for t in query.lower().split() if t]
    if not terms:
        return []

    products = _format(query_fn(build_sparql(terms)))

    # Ταξινόμηση ώστε τα πιο δημοφιλή (περισσότερα αγαπημένα) να εμφανίζονται πρώτα.
    if popularity_fn:
        products.sort(key=lambda p: popularity_fn(p["id"]), reverse=True)

    return products
