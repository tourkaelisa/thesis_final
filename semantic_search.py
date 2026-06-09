"""
Semantic search για το semantic e-shop — καθαρή προσέγγιση Knowledge Graph (NL → SPARQL).

Ροή:
  1. Rule-based parsing του ελεύθερου (ελληνικού/αγγλικού) ερωτήματος σε δομημένους
     περιορισμούς: κατηγορία, μάρκα, τιμή, specs (ram/storage/οθόνη/μπαταρία/κάμερα/
     refresh/βάρος), χρώμα, λειτουργικό, CPU, ανάλυση, έτος κυκλοφορίας, ταξινόμηση.
  2. Δυναμική κατασκευή SPARQL πάνω στον γράφο (GraphDB) — όπως το search_category.

Καμία εξωτερική βιβλιοθήκη/μοντέλο — μόνο SPARQL πάνω στην οντολογία.
"""

import re
import unicodedata

# Κλάση οντολογίας -> (route, ετικέτα, λέξεις-κλειδιά ανίχνευσης κατηγορίας)
TYPE_INFO = {
    "http://www.productontology.org/id/Laptop": {
        "route": "laptops", "label": "Laptops",
        "keywords": ["laptop", "laptops", "notebook", "υπολογιστης", "φορητος", "λαπτοπ"],
    },
    "http://www.productontology.org/id/Smartphone": {
        "route": "mobiles", "label": "Mobiles",
        "keywords": ["mobile", "mobiles", "phone", "smartphone", "κινητο", "τηλεφωνο"],
    },
    "http://www.productontology.org/id/Tablet_computer": {
        "route": "tablets", "label": "Tablets",
        "keywords": ["tablet", "tablets", "ipad", "ταμπλετ"],
    },
    "http://www.productontology.org/id/Television_set": {
        "route": "tvs", "label": "Τηλεοράσεις",
        "keywords": ["tv", "tvs", "television", "τηλεοραση", "τηλεορασεις", "τιβι"],
    },
    "http://www.productontology.org/id/Smartwatch": {
        "route": "smartwatches", "label": "Smartwatches",
        "keywords": ["watch", "smartwatch", "smartwatches", "ρολοι", "ρολογι", "wearable"],
    },
}

ROUTE_TO_CLASS = {info["route"]: uri.split("/")[-1] for uri, info in TYPE_INFO.items()}
TYPE_URI_TO_INFO = TYPE_INFO

# spec keyword -> όνομα ποσοτικής ιδιότητας στον γράφο (απλά αριθμητικά patterns)
_SPEC_PATTERNS = [
    ("ram", re.compile(r"(\d+)\s*gb\s*ram|ram\s*(\d+)|(\d+)\s*gb\s*μνημη")),
    ("refresh_rate", re.compile(r"(\d+)\s*hz")),
    ("screen_size", re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:ιντσ|inch|in\b|″|\")")),
    ("camera_main_mp", re.compile(r"(\d+)\s*mp")),
]

_DEFINITION_KEYWORDS = {
    "4k": "4K", "uhd": "Ultra HD", "ultra hd": "Ultra HD",
    "full hd": "Full HD", "fhd": "Full HD", "8k": "8K", "qhd": "QHD",
    "2k": "2K", "hd ready": "HD Ready",
}

# Χρώμα: λέξεις-κλειδιά (norm) -> ακριβής τιμή όπως αποθηκεύεται στον γράφο
_COLOR_MAP = [
    (["μαυρ", "black"], "Μαύρο"),
    (["λευκ", "ασπρ", "white"], "Λευκό"),
    (["ασημ", "silver"], "Ασημί"),
    (["γκρι", "grey", "gray"], "Γκρι"),
    (["γαλαζ", "light blue", "ανοιχτο μπλε"], "Γαλάζιο"),
    (["μπλε", "blue"], "Μπλε"),
    (["κιτριν", "yellow"], "Κίτρινο"),
    (["μπεζ", "beige"], "Μπεζ"),
    (["μωβ", "purple", "violet"], "Μωβ"),
    (["πορτοκαλ", "orange"], "Πορτοκαλί"),
    (["πρασιν", "green"], "Πράσινο"),
    (["ροζ", "pink"], "Ροζ"),
    (["χρυσ", "gold"], "Χρυσό"),
]

# Λειτουργικό: λέξεις-κλειδιά (norm) -> (ετικέτα, needle για CONTAINS στο ?os)
_OS_MAP = [
    (["android"], "Android", "android"),
    (["ipados", "ipad os"], "iPadOS", "ipados"),
    (["ios", "iphone"], "iOS", "ios"),
    (["windows", "win 11", "win11"], "Windows", "windows"),
    (["harmonyos", "harmony"], "HarmonyOS", "harmony"),
    (["tizen"], "Tizen", "tizen"),
    (["webos", "web os"], "WebOS", "webos"),
    (["google tv", "googletv"], "Google TV", "google tv"),
    (["vidaa"], "Vidaa", "vidaa"),
]

# CPU: λέξεις-κλειδιά (norm) -> (ετικέτα, needle για CONTAINS στο ?cpu)
_CPU_MAP = [
    (["core i9", "i9"], "Core i9", "i9"),
    (["core i7", "i7"], "Core i7", "i7"),
    (["core i5", "i5"], "Core i5", "i5"),
    (["core i3", "i3"], "Core i3", "i3"),
    (["ryzen 7"], "Ryzen 7", "ryzen 7"),
    (["ryzen 5"], "Ryzen 5", "ryzen 5"),
    (["ryzen 3"], "Ryzen 3", "ryzen 3"),
    (["ryzen"], "Ryzen", "ryzen"),
    (["celeron"], "Celeron", "celeron"),
]

# Μάρκες που υπάρχουν στα δεδομένα (norm -> original) — φορτώνονται στο startup.
_BRANDS: dict[str, str] = {}


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _norm(text: str) -> str:
    return _strip_accents((text or "").lower())


def load_brands(query_fn) -> dict[str, str]:
    """Φορτώνει τις μάρκες από το GraphDB (μία φορά στο startup)."""
    global _BRANDS
    q = """
    PREFIX schema1: <http://schema.org/>
    SELECT DISTINCT ?brand WHERE {
        ?p schema1:manufacturer ?bURI .
        BIND(REPLACE(STR(?bURI), "^.*Brand_", "") AS ?brand)
    }
    """
    brands = {}
    try:
        for b in query_fn(q):
            name = b["brand"]["value"]
            if name:
                brands[_norm(name)] = name
    except Exception as e:
        print(f"[semantic_search] Αποτυχία φόρτωσης μαρκών: {e}")
    _BRANDS = brands
    print(f"[semantic_search] Φορτώθηκαν {len(brands)} μάρκες.")
    return brands


def _has(n: str, kw: str) -> bool:
    return re.search(rf"\b{re.escape(kw)}", n) is not None


def parse_query(text: str) -> dict:
    raw = text or ""
    n = _norm(raw)

    c: dict = {
        "category": None, "category_label": None,
        "brands": [],
        "price_min": None, "price_max": None,
        "specs": {},
        "definition": None,
        "colors": [],
        "os": None, "os_label": None,
        "cpu": None, "cpu_label": None,
        "release_year": None,
        "release_from": None,
        "sort": None,
    }

    # --- Κατηγορία ---
    for type_uri, info in TYPE_INFO.items():
        if any(_has(n, k) for k in info["keywords"]):
            c["category"] = info["route"]
            c["category_label"] = info["label"]
            break

    # --- Μάρκα ---
    for brand_norm, brand_orig in _BRANDS.items():
        if re.search(rf"\b{re.escape(brand_norm)}\b", n):
            c["brands"].append(brand_orig)

    # --- Τιμή ---
    range_pattern = re.search(r"(?:απο|μεταξυ|between|from)\s*(\d+).{0,6}(?:εως|ως|to|και|-)\s*(\d+)", n)
    simple_range = re.search(r"(\d+)\s*-\s*(\d+)\s*(?:€|ευρω|euro)?", n)
    if range_pattern:
        a, b = int(range_pattern.group(1)), int(range_pattern.group(2))
        c["price_min"], c["price_max"] = min(a, b), max(a, b)
    elif simple_range:
        a, b = int(simple_range.group(1)), int(simple_range.group(2))
        c["price_min"], c["price_max"] = min(a, b), max(a, b)
    elif (m := re.search(r"(?:κατω απο|μεχρι|εως|ως|under|less than|<|μικροτερ\w*\s*απο)\s*(\d+)", n)):
        c["price_max"] = int(m.group(1))
    elif (m := re.search(r"(?:πανω απο|ανω|over|more than|>|μεγαλυτερ\w*\s*απο|τουλαχιστον)\s*(\d+)", n)):
        c["price_min"] = int(m.group(1))
    elif (m := re.search(r"(?:γυρω στα|περιπου|around|about)\s*(\d+)", n)):
        v = int(m.group(1))
        c["price_min"], c["price_max"] = int(v * 0.8), int(v * 1.2)
    elif (m := re.search(r"(\d{2,6})\s*(?:€|ευρω|euro)", n)):
        c["price_max"] = int(m.group(1))

    # --- Specs (αριθμητικά patterns) ---
    for prop_name, pat in _SPEC_PATTERNS:
        m = pat.search(n)
        if m:
            val = next((g for g in m.groups() if g), None)
            if val is None:
                continue
            val = float(val.replace(",", "."))
            if prop_name == "screen_size":
                c["specs"][prop_name] = (val - 0.3, val + 0.3)
            elif prop_name == "ram":
                c["specs"][prop_name] = (val, None)
            else:
                c["specs"][prop_name] = (val * 0.9, None)

    # --- Αποθήκευση (διαχωρισμός από RAM) ---
    for m in re.finditer(r"(\d+)\s*(tb|gb)", n):
        num, unit = int(m.group(1)), m.group(2)
        tail = n[m.end():m.end() + 6]
        if "ram" in tail or "μνημη" in tail:
            continue
        if unit == "tb":
            c["specs"]["storage"] = (num * 1024, None)
            break
        if unit == "gb" and num >= 128:
            c["specs"]["storage"] = (float(num), None)
            break

    # --- Ποιοτικά -> ποσοτικά κατώφλια ---
    cat = c["category"]
    if re.search(r"(καλη|δυνατη|μεγαλη)\s+καμερα|good camera|great camera", n):
        c["specs"].setdefault("camera_main_mp", (48.0, None))
    if re.search(r"μεγαλη\s+μπαταρια|big battery|large battery|αυτονομια", n):
        if cat in (None, "mobiles", "tablets"):
            c["specs"].setdefault("battery", (5000.0, None))
    if re.search(r"ελαφρ\w*|lightweight|light\b", n):
        if cat in (None, "laptops"):
            c["specs"].setdefault("weight", (None, 1.6))

    # --- Definition (4K / Full HD ...) ---
    for kw, label in _DEFINITION_KEYWORDS.items():
        if _has(n, kw):
            c["definition"] = label
            break

    # --- Χρώμα ---
    for keys, value in _COLOR_MAP:
        if any(_has(n, k) for k in keys):
            c["colors"].append(value)

    # --- Λειτουργικό ---
    for keys, label, needle in _OS_MAP:
        if any(_has(n, k) for k in keys):
            c["os"], c["os_label"] = needle, label
            break

    # --- CPU ---
    for keys, label, needle in _CPU_MAP:
        if any(_has(n, k) for k in keys):
            c["cpu"], c["cpu_label"] = needle, label
            break

    # --- Έτος κυκλοφορίας / πρόσφατα ---
    for m in re.finditer(r"\b(20(?:1[5-9]|2[0-7]))\b", n):
        y = int(m.group(1))
        if y not in (c["price_min"], c["price_max"]):  # να μην μπερδευτεί με τιμή
            c["release_year"] = y
            break
    if c["release_year"] is None and re.search(r"\bνεο\w*|καινουρ\w*|προσφατ\w*|recent|latest|newest|new\b", n):
        c["release_from"] = 2024

    # --- Ταξινόμηση (και από ποιοτικά επίθετα τιμής) ---
    if re.search(r"φθην\w*|cheap\w*|οικονομικ\w*", n):
        c["sort"] = "price_asc"
    elif re.search(r"ακριβ\w*|expensive|premium|πολυτελ\w*", n):
        c["sort"] = "price_desc"
    elif re.search(r"νεοτερ\w*|πιο νεα|πιο προσφατ\w*|newest|latest", n):
        c["sort"] = "newest"

    return c


_PREFIXES = """
PREFIX gr: <http://purl.org/goodrelations/v1#>
PREFIX schema1: <http://schema.org/>
PREFIX prop: <http://www.myeshop.gr/property/>
PREFIX pto: <http://www.productontology.org/id/>
"""


def build_sparql(c: dict, include_specs: bool = True) -> str:
    if c["category"]:
        classes = f"pto:{ROUTE_TO_CLASS[c['category']]}"
    else:
        classes = " ".join(f"pto:{cls}" for cls in ROUTE_TO_CLASS.values())

    blocks = []
    filters = []

    # Μάρκα
    if c["brands"]:
        vals = ", ".join(f'"{b}"' for b in c["brands"])
        filters.append(f"FILTER(?brand IN ({vals}))")

    # Τιμή
    if c["price_min"] is not None:
        filters.append(f"FILTER(?price >= {c['price_min']})")
    if c["price_max"] is not None:
        filters.append(f"FILTER(?price <= {c['price_max']})")

    # Definition
    if c["definition"]:
        blocks.append("?uri prop:definition ?def .")
        filters.append(f'FILTER(CONTAINS(LCASE(STR(?def)), "{c["definition"].lower()}"))')

    # Χρώμα
    if c["colors"]:
        vals = ", ".join(f'"{v}"' for v in c["colors"])
        blocks.append("?uri schema1:color ?color .")
        filters.append(f"FILTER(?color IN ({vals}))")

    # Λειτουργικό
    if c["os"]:
        blocks.append("?uri schema1:operatingSystem ?os .")
        filters.append(f'FILTER(CONTAINS(LCASE(STR(?os)), "{c["os"]}"))')

    # CPU
    if c["cpu"]:
        blocks.append("?uri prop:cpu_model ?cpu .")
        filters.append(f'FILTER(CONTAINS(LCASE(STR(?cpu)), "{c["cpu"]}"))')

    # Έτος κυκλοφορίας / πρόσφατα
    if c["release_year"] is not None:
        filters.append(f'FILTER(STR(?rd) = "{c["release_year"]}")')
    elif c["release_from"] is not None:
        filters.append(f'FILTER(STR(?rd) >= "{c["release_from"]}")')

    # Specs (ποσοτικά)
    if include_specs:
        for i, (prop_name, (lo, hi)) in enumerate(c["specs"].items()):
            blocks.append(
                f"?uri gr:quantitativeProductOrServiceProperty ?qn{i} .\n"
                f"        ?qn{i} gr:hasValueFloat ?qv{i} .\n"
                f'        FILTER(STRENDS(STR(?qn{i}), "_{prop_name}"))'
            )
            if lo is not None:
                filters.append(f"FILTER(?qv{i} >= {lo})")
            if hi is not None:
                filters.append(f"FILTER(?qv{i} <= {hi})")

    # Ταξινόμηση
    order_by = ""
    if c["sort"] == "price_asc":
        order_by = "ORDER BY ASC(?price)"
    elif c["sort"] == "price_desc":
        order_by = "ORDER BY DESC(?price)"
    elif c["sort"] == "newest":
        order_by = "ORDER BY DESC(?rd)"

    query = f"""{_PREFIXES}
SELECT DISTINCT ?uri ?type ?name ?price ?image ?brand ?rd
WHERE {{
    VALUES ?type {{ {classes} }}
    ?uri a ?type ;
         gr:name ?name ;
         schema1:price ?price ;
         schema1:image ?image .
    OPTIONAL {{ ?uri schema1:manufacturer ?bURI .
                BIND(REPLACE(STR(?bURI), "^.*Brand_", "") AS ?brand) }}
    OPTIONAL {{ ?uri schema1:releaseDate ?rd . }}
    {chr(10).join("    " + b for b in blocks)}
    {chr(10).join("    " + f for f in filters)}
}}
{order_by}
LIMIT 100
"""
    return query


def _format(bindings: list) -> list[dict]:
    seen = set()
    products = []
    for b in bindings:
        uri = b["uri"]["value"]
        if uri in seen:
            continue
        seen.add(uri)
        type_uri = b.get("type", {}).get("value", "")
        info = TYPE_URI_TO_INFO.get(type_uri, {})
        products.append({
            "id": uri,
            "name": b["name"]["value"],
            "price": float(b["price"]["value"]),
            "image": b.get("image", {}).get("value", ""),
            "brand": b.get("brand", {}).get("value", ""),
            "category": info.get("route", ""),
            "categoryLabel": info.get("label", ""),
            "releaseDate": b.get("rd", {}).get("value", ""),
        })
    return products


def search(query: str, query_fn, popularity_fn=None, top_n: int = 60) -> dict:
    c = parse_query(query)

    interpreted = {
        "category": c["category_label"],
        "brands": c["brands"],
        "priceMin": c["price_min"],
        "priceMax": c["price_max"],
        "specs": {k: {"min": v[0], "max": v[1]} for k, v in c["specs"].items()},
        "definition": c["definition"],
        "colors": c["colors"],
        "os": c["os_label"],
        "cpu": c["cpu_label"],
        "releaseYear": c["release_year"],
        "releaseFrom": c["release_from"],
        "sort": c["sort"],
        "relaxedSpecs": False,
    }

    bindings = query_fn(build_sparql(c))
    products = _format(bindings)

    # Αν οι σκληροί περιορισμοί (specs) δεν αφήνουν τίποτα, χαλαρώνουμε τα specs.
    if not products and c["specs"]:
        interpreted["relaxedSpecs"] = True
        products = _format(query_fn(build_sparql(c, include_specs=False)))

    # Κατάταξη: αν δεν ζητήθηκε ρητή ταξινόμηση, με δημοτικότητα.
    if not c["sort"] and popularity_fn:
        products.sort(key=lambda p: popularity_fn(p["id"]), reverse=True)

    return {"interpreted": interpreted, "products": products[:top_n]}
