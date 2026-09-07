import rdflib
from collections import defaultdict

g = rdflib.Graph()
g.parse("data/master_eshop_enriched.ttl", format="turtle")

PTO = rdflib.Namespace("http://www.productontology.org/id/")
GR = rdflib.Namespace("http://purl.org/goodrelations/v1#")

classes = {
    "Laptop": PTO.Laptop,
    "Smartphone": PTO.Smartphone,
    "Tablet": PTO.Tablet_computer,
    "Television": PTO.Television_set,
    "Smartwatch": PTO.Smartwatch,
    "Desktop": PTO.Desktop_computer,
    "Monitor": PTO.Computer_monitor,
    "Console": PTO.Game_console,
    "Headphones": PTO.Headphones,
}

print("=== GLOBAL PROPERTIES (100% of all products) ===")
all_products = list(g.subjects(rdflib.RDF.type, GR.ProductOrService))
print(f"Total Products: {len(all_products)}")

global_prop_counts = defaultdict(int)
for p in all_products:
    props = set(g.predicates(subject=p))
    for pr in props:
        global_prop_counts[pr] += 1

global_100 = [p for p, c in global_prop_counts.items() if c == len(all_products)]
print("Global 100% Properties:")
for p in global_100:
    print(f"  {p}")

print("\n=== CATEGORY PROPERTIES (100% within category) ===")
for cat_name, cat_uri in classes.items():
    instances = list(g.subjects(rdflib.RDF.type, cat_uri))
    if not instances:
        print(f"\n{cat_name}: 0 instances found!")
        continue
    
    print(f"\n{cat_name} (Total: {len(instances)})")
    prop_counts = defaultdict(int)
    quant_counts = defaultdict(int)
    
    for i in instances:
        # Normal properties
        props = set(g.predicates(subject=i))
        for pr in props:
            prop_counts[pr] += 1
            
        # Quantitative properties
        quants = list(g.objects(subject=i, predicate=GR.quantitativeProductOrServiceProperty))
        for q in quants:
            # extract basename from URI
            q_str = str(q)
            if "_" in q_str:
                basename = q_str.split("_", 1)[1] # e.g., 'ram' from 'ESHOP_XYZ_ram'
                # actually, let's just get the suffix. E.g. 58318540_ram -> ram
                basename = "_".join(q_str.split("/")[-1].split("_")[1:])
                quant_counts[basename] += 1

    cat_100 = [p for p, c in prop_counts.items() if c == len(instances)]
    quant_100 = [q for q, c in quant_counts.items() if c == len(instances)]
    
    print("  Properties (100%):")
    for p in cat_100:
        if p not in global_100: # only print category-specific ones
            print(f"    {p}")
            
    print("  Quantitative Values (100%):")
    for q in quant_100:
        print(f"    {q}")

