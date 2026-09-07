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

    # Δυναμική προσθήκη των ποιοτικών χαρακτηριστικών (ώστε να βγουν στα φίλτρα του frontend)
    query_qual = f"""
    PREFIX prop: <http://www.myeshop.gr/property/>
    PREFIX pto: <http://www.productontology.org/id/>
    SELECT ?uri ?pred ?val
    WHERE {{
        ?uri a {rdf_class} .
        ?uri ?pred ?val .
        FILTER(STRSTARTS(STR(?pred), "http://www.myeshop.gr/property/"))
    }}
    """
    for b in query_graphdb(query_qual):
        uri = b["uri"]["value"]
        if uri not in product_map:
            continue
        pred = b.get("pred", {}).get("value")
        val = b.get("val", {}).get("value")
        if not pred or not val or val.startswith("http"):
            continue
            
        prop_key = pred.split("/")[-1]
        if prop_key in ("cpu_model", "definition"):
            continue
            
        # Μετατροπή booleans
        if str(val).lower() == "true":
            val_str = "Ναι"
        elif str(val).lower() == "false":
            val_str = "Όχι"
        else:
            val_str = str(val)
            
        product_map[uri][prop_key] = val_str

    # Συνδυάζουμε resolution_width x resolution_height 
    for p in product_map.values():
        w = p["props"].pop("resolution_width", None)
        h = p["props"].pop("resolution_height", None)
        if w is not None and h is not None:
            p["resolution"] = f"{int(w)}×{int(h)}"
            
        vw = p["props"].pop("vesa_width", None)
        vh = p["props"].pop("vesa_height", None)
        if vw is not None and vh is not None:
            p["vesa_mount"] = f"{int(vw)}×{int(vh)}"

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
        "battery hours": "Διάρκεια Μπαταρίας",
        "screen size": "Μέγεθος Οθόνης",
        "camera main mp": "Κάμερα",
        "camera selfie mp": "Selfie Κάμερα",
        "resolution width": "Ανάλυση Πλάτος",
        "resolution height": "Ανάλυση Ύψος",
        "cpu frequency": "Συχνότητα Επεξεργαστή",
        "response time": "Χρόνος Απόκρισης",
        "vesa width": "Vesa Πλάτος",
        "vesa height": "Vesa Ύψος",
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
                "INH": "inches", "CEL": "°C", "MHT": "MHz", "HTZ": "Hz", "GHZ": "GHz",
                "SEC": "sec", "HUR": "ώρες", "KWH": "kWh", "E37": "pixels",
                "C62": "MP", "MAH": "mAh", "GRM": "gr", "C26": "ms",
            }
            if unit_str in unit_map:
                unit_str = unit_map[unit_str]

            specs.append({"name": prop_name, "value": float(val), "unit": unit_str})

    res_width = None
    res_height = None
    vesa_width = None
    vesa_height = None
    
    for s in specs[:]:
        if s["name"] == "Ανάλυση Πλάτος":
            res_width = int(s["value"])
            specs.remove(s)
        elif s["name"] == "Ανάλυση Ύψος":
            res_height = int(s["value"])
            specs.remove(s)
        elif s["name"] == "Vesa Πλάτος":
            vesa_width = int(s["value"])
            specs.remove(s)
        elif s["name"] == "Vesa Ύψος":
            vesa_height = int(s["value"])
            specs.remove(s)

    if res_width and res_height:
        specs.append({
            "name": "Ανάλυση Οθόνης",
            "value": f"{res_width} x {res_height}",
            "unit": "pixels",
        })
    elif res_width:
        specs.append({"name": "Ανάλυση Πλάτος", "value": res_width, "unit": "pixels"})
    elif res_height:
        specs.append({"name": "Ανάλυση Ύψος", "value": res_height, "unit": "pixels"})
        
    if vesa_width and vesa_height:
        specs.append({
            "name": "Βάση VESA",
            "value": f"{vesa_width} x {vesa_height}",
            "unit": "mm",
        })

    # Ανάκτηση νέων ποιοτικών χαρακτηριστικών (Strings/Booleans)
    query_qual = f"""
    PREFIX prop: <http://www.myeshop.gr/property/>
    SELECT ?pred ?val
    WHERE {{
        <{product_uri}> ?pred ?val .
        FILTER(STRSTARTS(STR(?pred), "http://www.myeshop.gr/property/"))
    }}
    """
    results_qual = query_graphdb(query_qual)
    
    qual_translate_map = {
        "ram_type": "Τύπος RAM",
        "storage_type": "Τύπος Δίσκου",
        "console_platform": "Πλατφόρμα",
        "console_edition": "Έκδοση",
        "console_bundle": "Πακέτο",
        "use_case": "Χρήση",
        "headphone_type": "Είδος",
        "connection": "Συνδεσιμότητα",
        "gpu_memory": "Μνήμη Κάρτας",
        "gpu_model": "Κάρτα Γραφικών",
        "case_size": "Μέγεθος Κουτιού",
        "is_portable": "Φορητή",
        "has_anc": "Active Noise Cancellation",
        "connection_type": "Συνδεσιμότητα",
        "hdr_support": "Υποστήριξη HDR",
        "height_adjustment": "Ρύθμιση Ύψους",
        "is_curved": "Curved",
        "is_ultrawide": "Ultrawide",
        "panel_type": "Τύπος Panel",
    }
    
    ignore_props = {"cpu_model", "definition"}
    
    qual_groups = {}
    for b in results_qual:
        pred = bval(b, "pred")
        val = bval(b, "val")
        if not pred or not val or str(val).startswith("http"):
            continue
            
        prop_key = pred.split("/")[-1]
        if prop_key in ignore_props:
            continue
            
        if str(val).lower() == "true":
            val_str = "Ναι"
        elif str(val).lower() == "false":
            val_str = "Όχι"
        else:
            val_str = str(val)
            
        prop_name = qual_translate_map.get(prop_key, prop_key.replace("_", " ").capitalize())
        if prop_name not in qual_groups:
            qual_groups[prop_name] = set()
        qual_groups[prop_name].add(val_str)

    for prop_name, vals in qual_groups.items():
        specs.append({"name": prop_name, "value": ", ".join(sorted(vals)), "unit": ""})

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
