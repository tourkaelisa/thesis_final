"""Service καταλόγου: προβολή κατηγορίας και λεπτομέρειες προϊόντος (από GraphDB)."""
import db
from config import CATEGORY_CLASSES
from graphdb import query_graphdb, bval

# Όλα τα προϊόντα μιας κατηγορίας με τα χαρακτηριστικά τους
def get_category_products(category) -> list:
    rdf_class = CATEGORY_CLASSES[category]

    query = f"""
    PREFIX gr: <http://purl.org/goodrelations/v1#>
    PREFIX schema1: <http://schema.org/>
    PREFIX prop: <http://www.myeshop.gr/property/>
    PREFIX pto: <http://www.productontology.org/id/>
    SELECT ?uri ?name ?price ?image ?brand ?os ?color ?definition ?cpu ?releaseDate
    WHERE {{
        ?uri a {rdf_class} ;
             gr:name ?name ;
             schema1:price ?price ;
             schema1:image ?image .
        OPTIONAL {{ ?uri schema1:manufacturer ?bURI .
                    BIND(REPLACE(STR(?bURI), "^.*Brand_", "") AS ?brand) }}
        OPTIONAL {{ ?uri schema1:operatingSystem ?os . }}
        OPTIONAL {{ ?uri schema1:color ?color . }}
        OPTIONAL {{ ?uri prop:definition ?definition . }}
        OPTIONAL {{ ?uri prop:cpu_model ?cpu . }}
        OPTIONAL {{ ?uri schema1:releaseDate ?releaseDate . }}
    }}
    """
    product_map = {}
    for b in query_graphdb(query):
        uri = b["uri"]["value"]
        if uri not in product_map:
            product_map[uri] = {
                "id": uri,
                "name": b["name"]["value"],
                "price": float(b["price"]["value"]),
                "image": b.get("image", {}).get("value", ""),
                "props": {},
            }
        p = product_map[uri]
        for field in ("brand", "os", "color", "definition", "cpu", "releaseDate"):
            if field in b and field not in p:
                p[field] = b[field]["value"]

    quant_q = f"""
    PREFIX gr: <http://purl.org/goodrelations/v1#>
    PREFIX pto: <http://www.productontology.org/id/>
    SELECT ?uri ?node ?val
    WHERE {{
        ?uri a {rdf_class} ;
             gr:quantitativeProductOrServiceProperty ?node .
        ?node gr:hasValueFloat ?val .
    }}
    """
    for b in query_graphdb(quant_q):
        uri = b["uri"]["value"]
        if uri not in product_map:
            continue
        node_uri = b["node"]["value"]
        prod_local = uri.split("/")[-1]
        sep = prod_local + "_"
        if sep in node_uri:
            prop_name = node_uri.split(sep, 1)[-1]
            product_map[uri]["props"][prop_name] = float(b["val"]["value"])

    # Συνδυάζουμε resolution_width x resolution_height 
    for p in product_map.values():
        w = p["props"].pop("resolution_width", None)
        h = p["props"].pop("resolution_height", None)
        if w is not None and h is not None:
            p["resolution"] = f"{int(w)}×{int(h)}"

    return list(product_map.values())

#Πλήρεις λεπτομέρειες ενός προϊόντος
def get_product_details(product_uri, user_id) -> dict:
    query_basic = f"""
    PREFIX gr: <http://purl.org/goodrelations/v1#>
    PREFIX schema1: <http://schema.org/>
    PREFIX prop: <http://www.myeshop.gr/property/>

    SELECT ?name ?price ?image ?brand ?brandURI ?os ?color ?cpu ?definition ?releaseDate
    WHERE {{
        <{product_uri}> gr:name ?name .
        OPTIONAL {{ <{product_uri}> schema1:price ?price . }}
        OPTIONAL {{ <{product_uri}> schema1:image ?image . }}
        OPTIONAL {{ <{product_uri}> schema1:manufacturer ?brandURI . BIND(REPLACE(STR(?brandURI), "^.*Brand_", "") AS ?brand) }}
        OPTIONAL {{ <{product_uri}> schema1:operatingSystem ?os . }}
        OPTIONAL {{ <{product_uri}> schema1:color ?color . }}
        OPTIONAL {{ <{product_uri}> prop:cpu_model ?cpu . }}
        OPTIONAL {{ <{product_uri}> prop:definition ?definition . }}
        OPTIONAL {{ <{product_uri}> schema1:releaseDate ?releaseDate . }}
    }}
    """
    results_basic = query_graphdb(query_basic)
    details = {}
    os_set = set()
    color_set = set()

    for b in results_basic:
        details["name"] = bval(b, "name") or "Άγνωστο"
        details["price"] = float(bval(b, "price")) if bval(b, "price") else 0.0
        details["image"] = bval(b, "image") or ""
        if bval(b, "brand"):
            details["brand"] = bval(b, "brand")
        if bval(b, "brandURI"):
            details["brandURI"] = bval(b, "brandURI")
        if bval(b, "os"): details["os"] = bval(b, "os")
        if bval(b, "color"): details["color"] = bval(b, "color")
        if bval(b, "cpu"): details["cpu"] = bval(b, "cpu")
        if bval(b, "definition"): details["definition"] = bval(b, "definition")
        if bval(b, "releaseDate"): details["releaseDate"] = bval(b, "releaseDate")
        if bval(b, "os"): os_set.add(bval(b, "os"))
        if bval(b, "color"): color_set.add(bval(b, "color"))

    # Ενώνουμε τις πολλαπλές τιμές με κόμμα (π.χ. "Android, iOS")
    if os_set: details["os"] = ", ".join(sorted(os_set))
    if color_set: details["color"] = ", ".join(sorted(color_set))

    query_quant = f"""
    PREFIX gr: <http://purl.org/goodrelations/v1#>
    SELECT ?node ?val ?unit ?name
    WHERE {{
        <{product_uri}> gr:quantitativeProductOrServiceProperty ?node .
        ?node a gr:QuantitativeValue .
        ?node gr:hasValueFloat ?val .
        OPTIONAL {{ ?node gr:hasUnitOfMeasurement ?unit . }}
        OPTIONAL {{ ?node gr:name ?name . }}
    }}
    """
    results_quant = query_graphdb(query_quant)
    specs = []

    translate_map = {
        "ram": "Μνήμη RAM",
        "storage": "Αποθηκευτικός Χώρος",
        "refresh rate": "Ρυθμός Ανανέωσης",
        "weight": "Βάρος",
        "battery": "Μπαταρία",
        "screen size": "Μέγεθος Οθόνης",
        "camera main mp": "Βασική Κάμερα",
        "camera selfie mp": "Selfie Κάμερα",
    }

    res_width = None
    res_height = None

    for b in results_quant:
        val = bval(b, "val")
        if val is not None:
            name_v = bval(b, "name")
            if name_v:
                prop_name = name_v
            else:
                node_uri = bval(b, "node")
                prop_name = node_uri.replace(product_uri + "_", "")
                prop_name = prop_name.replace("_", " ")

            if "resolution width" in prop_name.lower():
                res_width = int(float(val))
                continue

            if "resolution height" in prop_name.lower():
                res_height = int(float(val))
                continue

            if prop_name in translate_map:
                prop_name = translate_map[prop_name]
            else:
                prop_name = prop_name.capitalize()

            unit_str = bval(b, "unit") or ""
            unit_map = {
                "E34": "GB", "CMT": "cm", "KGM": "kg", "MMT": "mm",
                "INH": "inches", "CEL": "°C", "MHT": "MHz", "HTZ": "Hz",
                "SEC": "sec", "HUR": "ώρες", "KWH": "kWh", "E37": "pixels",
                "C62": "MP", "MAH": "mAh", "GRM": "gr",
            }
            if unit_str in unit_map:
                unit_str = unit_map[unit_str]

            specs.append({"name": prop_name, "value": float(val), "unit": unit_str})

    if res_width and res_height:
        specs.append({
            "name": "Ανάλυση Οθόνης",
            "value": f"{res_width} x {res_height}",
            "unit": "pixels",
        })
    elif res_width:
        specs.append({"name": "Οριζόντια Ανάλυση", "value": res_width, "unit": "pixels"})
    elif res_height:
        specs.append({"name": "Κατακόρυφη Ανάλυση", "value": res_height, "unit": "pixels"})

    details["specs"] = specs
    details["id"] = product_uri

    details["isWishlisted"] = db.is_wishlisted(user_id, product_uri) if user_id else False

    # Ανάκτηση DBpedia link για τον κατασκευαστή
    brand_uri = details.get("brandURI", "")
    if brand_uri:
        same_as_q = f"""
        PREFIX owl: <http://www.w3.org/2002/07/owl#>
        SELECT ?dbpedia WHERE {{
            <{brand_uri}> owl:sameAs ?dbpedia .
        }} LIMIT 1
        """
        bindings = query_graphdb(same_as_q)
        if bindings:
            details["brandLink"] = bindings[0]["dbpedia"]["value"]

    return details
