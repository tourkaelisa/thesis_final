"""Απλή αναζήτηση λέξης-κλειδιού πάνω στο GraphDB (όνομα + μάρκα) μέσω SPARQL CONTAINS.
"""

import unicodedata

# Κλάση οντολογίας - (route, ετικέτα) για την εμφάνιση κατηγορίας στα αποτελέσματα.
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


def _strip_accents(text: str) -> str:
    """Αφαιρεί τόνους/διαλυτικά ώστε «άσπρο» και «ασπρο» να θεωρούνται ίδια."""
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


# Αντιστοίχιση τονισμένων ελληνικών (πεζών) στις άτονες μορφές, για χρήση στο SPARQL.
_GREEK_ACCENTS = {
    "ά": "α", "έ": "ε", "ή": "η", "ί": "ι",
    "ό": "ο", "ύ": "υ", "ώ": "ω",
    "ϊ": "ι", "ϋ": "υ", "ΐ": "ι", "ΰ": "υ",
}


def _strip_accents_sparql(expr: str) -> str:
    """Τυλίγει μια SPARQL έκφραση με αλυσίδα REPLACE ώστε να αφαιρεθούν οι τόνοι."""
    for accented, plain in _GREEK_ACCENTS.items():
        expr = f'REPLACE({expr}, "{accented}", "{plain}")'
    return expr


def build_sparql(terms: list[str]) -> str:
    """SPARQL που απαιτεί κάθε λέξη να εμφανίζεται στο όνομα Ή στη μάρκα.
    Όνομα/μάρκα και όροι συγκρίνονται άτονα """
    name_expr = _strip_accents_sparql("LCASE(STR(?name))")
    brand_expr = _strip_accents_sparql('LCASE(COALESCE(STR(?brand), ""))')
    filters = []
    for t in terms:
        esc = _escape(t)
        filters.append(
            f'    FILTER(CONTAINS({name_expr}, "{esc}") '
            f'|| CONTAINS({brand_expr}, "{esc}"))'
        )
    return f"""{_PREFIXES}
SELECT DISTINCT ?uri ?type ?name ?price ?image
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
            "categoryLabel": info.get("label", ""),
        })
    return products


def search(query: str, query_fn, popularity_fn=None) -> list[dict]:
    """Αναζήτηση λέξης-κλειδιού. Επιστρέφει τη λίστα όλων των προϊόντων που
    ταιριάζουν (χωρίς αποκοπή σε πλήθος)."""
    terms = [_strip_accents(t) for t in query.lower().split() if t]
    if not terms:
        return []

    products = _format(query_fn(build_sparql(terms)))

    # Ταξινόμηση ώστε τα πιο δημοφιλή (περισσότερα αγαπημένα) να εμφανίζονται πρώτα.
    if popularity_fn:
        products.sort(key=lambda p: popularity_fn(p["id"]), reverse=True)

    return products
