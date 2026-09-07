"""Service αναζήτησης με φίλτρα πάνω στο GraphDB.

Μεταφράζει τα φίλτρα του χρήστη  σε δυναμικά κατασκευασμένο SPARQL ερώτημα.
"""
from config import CATEGORY_CLASSES
from graphdb import query_graphdb

# Αντιστοίχιση κατηγορικού πεδίου με SPARQL predicate
FIELD_PREDICATE = {
    "os":          "schema1:operatingSystem",
    "color":       "schema1:color",
    "definition":  "prop:definition",
    "cpu":         "prop:cpu_model",
    "releaseDate": "schema1:releaseDate",
    "ram_type":    "prop:ram_type",
    "storage_type": "prop:storage_type",
    "console_platform": "prop:console_platform",
    "console_edition": "prop:console_edition",
    "console_bundle": "prop:console_bundle",
    "use_case":    "prop:use_case",
    "headphone_type": "prop:headphone_type",
    "connection":  "prop:connection",
    "gpu_memory":  "prop:gpu_memory",
    "case_size":   "prop:case_size",
    "hdr_support": "prop:hdr_support",
    "height_adjustment": "prop:height_adjustment",
    "is_curved":   "prop:is_curved",
    "is_ultrawide": "prop:is_ultrawide",
    "is_portable": "prop:is_portable",
    "panel_type":  "prop:panel_type",
    "has_anc":     "prop:has_anc",
}


def search_category(category, filters, prop_ranges, price_min, price_max) -> list:
    """Φιλτράρει τα προϊόντα μιας κατηγορίας και επιστρέφει τη λίστα αποτελεσμάτων."""
    rdf_class = CATEGORY_CLASSES[category]
    filter_clauses = [f"FILTER(?price >= {price_min} && ?price <= {price_max})"]
    quant_joins = []
    cat_joins = []

    for key, values in filters.items():
        if not values:
            continue
        if key == "brand":
            vals = ", ".join(f'"{v}"' for v in values)
            cat_joins.append(
                '?uri schema1:manufacturer ?bURI .\n'
                '        BIND(REPLACE(STR(?bURI), "^.*Brand_", "") AS ?brand)'
            )
            filter_clauses.append(f"FILTER(?brand IN ({vals}))")
        elif key == "resolution":
            # "1920×1080" → ζεύγος ποσοτικών φίλτρων width + height
            pairs = []
            ri = len(quant_joins)
            for val in values:
                parts = val.split("×")
                if len(parts) == 2:
                    try:
                        w, h = float(parts[0]), float(parts[1])
                        pairs.append(f"(?qvRW{ri} = {w} && ?qvRH{ri} = {h})")
                    except ValueError:
                        pass
            if pairs:
                quant_joins.append(
                    f"?uri gr:quantitativeProductOrServiceProperty ?qnRW{ri} .\n"
                    f"        ?qnRW{ri} gr:hasValueFloat ?qvRW{ri} .\n"
                    f'        FILTER(STRENDS(STR(?qnRW{ri}), "_resolution_width"))\n'
                    f"        ?uri gr:quantitativeProductOrServiceProperty ?qnRH{ri} .\n"
                    f"        ?qnRH{ri} gr:hasValueFloat ?qvRH{ri} .\n"
                    f'        FILTER(STRENDS(STR(?qnRH{ri}), "_resolution_height"))\n'
                    f"        FILTER({' || '.join(pairs)})"
                )
        elif key == "vesa_mount":
            pairs = []
            ri = len(quant_joins)
            for val in values:
                parts = val.split("×")
                if len(parts) == 2:
                    try:
                        w, h = float(parts[0]), float(parts[1])
                        pairs.append(f"(?qvVW{ri} = {w} && ?qvVH{ri} = {h})")
                    except ValueError:
                        pass
            if pairs:
                quant_joins.append(
                    f"?uri gr:quantitativeProductOrServiceProperty ?qnVW{ri} .\n"
                    f"        ?qnVW{ri} gr:hasValueFloat ?qvVW{ri} .\n"
                    f'        FILTER(STRENDS(STR(?qnVW{ri}), "_vesa_width"))\n'
                    f"        ?uri gr:quantitativeProductOrServiceProperty ?qnVH{ri} .\n"
                    f"        ?qnVH{ri} gr:hasValueFloat ?qvVH{ri} .\n"
                    f'        FILTER(STRENDS(STR(?qnVH{ri}), "_vesa_height"))\n'
                    f"        FILTER({' || '.join(pairs)})"
                )
        elif key in FIELD_PREDICATE:
            mapped_vals = []
            for v in values:
                if v == "Ναι":
                    mapped_vals.append('"true"')
                elif v == "Όχι":
                    mapped_vals.append('"false"')
                else:
                    mapped_vals.append(f'"{v}"')
            vals = ", ".join(mapped_vals)
            cat_joins.append(f"?uri {FIELD_PREDICATE[key]} ?{key} .")
            filter_clauses.append(f"FILTER(STR(?{key}) IN ({vals}))")

    # Ποσοτικά εύρη (RAM, storage, screen_size, κ.λπ.)
    for prop_name, rng in prop_ranges.items():
        i = len(quant_joins)
        mn = float(rng.get("min", 0))
        mx = float(rng.get("max", 999999))
        quant_joins.append(
            f"?uri gr:quantitativeProductOrServiceProperty ?qn{i} .\n"
            f"        ?qn{i} gr:hasValueFloat ?qv{i} .\n"
            f'        FILTER(STRENDS(STR(?qn{i}), "_{prop_name}"))\n'
            f"        FILTER(?qv{i} >= {mn} && ?qv{i} <= {mx})"
        )

    sparql = f"""
    PREFIX gr:     <http://purl.org/goodrelations/v1#>
    PREFIX schema1: <http://schema.org/>
    PREFIX prop:   <http://www.myeshop.gr/property/>
    PREFIX pto:    <http://www.productontology.org/id/>

    SELECT DISTINCT ?uri ?name ?price ?image
    WHERE {{
        ?uri a {rdf_class} ;
             gr:name ?name ;
             schema1:price ?price ;
             schema1:image ?image .
        {chr(10).join(cat_joins)}
        {chr(10).join(quant_joins)}
        {chr(10).join(filter_clauses)}
    }}
    """
    bindings = query_graphdb(sparql)
    seen = set()
    products = []
    for b in bindings:
        uri = b["uri"]["value"]
        if uri in seen:
            continue
        seen.add(uri)
        products.append({
            "id":    uri,
            "name":  b["name"]["value"],
            "price": float(b["price"]["value"]),
            "image": b.get("image", {}).get("value", ""),
        })
    return products
