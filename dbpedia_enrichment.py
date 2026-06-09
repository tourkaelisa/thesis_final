import os
import time
from rdflib import Graph, URIRef, Literal, Namespace
from SPARQLWrapper import SPARQLWrapper, JSON

# Ορίζουμε τα Namespaces
SCHEMA = Namespace("http://schema.org/")
OWL = Namespace("http://www.w3.org/2002/07/owl#")
ESHOP = Namespace("http://www.myeshop.gr/resource/")

# Σύνδεση με τον Server της DBpedia με Timeout 10 δευτερολέπτων
sparql = SPARQLWrapper("http://dbpedia.org/sparql")
sparql.setTimeout(10)

def enrich_graph():
    print("Φόρτωση του υπάρχοντος Γράφου...")
    g = Graph()
    
    if not os.path.exists("master_eshop_fixed.ttl"):
        print("Το αρχείο master_eshop_fixed.ttl δεν βρέθηκε!")
        return
        
    g.parse("master_eshop_fixed.ttl", format="turtle")
    
    # 1. Βρίσκουμε όλες τις μοναδικές μάρκες (αποθηκευμένες ως URIs: eshop:Brand_Apple)
    brands = {}  # brand_name -> brand_uri_node
    for s, p, o in g.triples((None, SCHEMA.manufacturer, None)):
        uri_str = str(o)
        if "Brand_" in uri_str:
            brand_name = uri_str.split("Brand_")[-1]
            brands[brand_name] = o  # κρατάμε το URI node

    print(f"Βρέθηκαν {len(brands)} μοναδικές μάρκες στο e-shop.\n")

    # 2. Λεξικό Αντιστοίχισης
    brand_uris = {
        "Apple": "http://dbpedia.org/resource/Apple_Inc.",
        "Samsung": "http://dbpedia.org/resource/Samsung_Electronics",
        "Lenovo": "http://dbpedia.org/resource/Lenovo",
        "Sony": "http://dbpedia.org/resource/Sony",
        "LG": "http://dbpedia.org/resource/LG_Electronics",
        "Garmin": "http://dbpedia.org/resource/Garmin",
        "Xiaomi": "http://dbpedia.org/resource/Xiaomi",
        "Huawei": "http://dbpedia.org/resource/Huawei",
        "HP": "http://dbpedia.org/resource/Hewlett-Packard",
        "Asus": "http://dbpedia.org/resource/Asus",
        "Dell": "http://dbpedia.org/resource/Dell",
        "Motorola": "http://dbpedia.org/resource/Motorola",
        "Google": "http://dbpedia.org/resource/Google",
        "MSI": "http://dbpedia.org/resource/Micro-Star_International",
        "OnePlus": "http://dbpedia.org/resource/OnePlus",
        "Toshiba": "http://dbpedia.org/resource/Toshiba",
        "TCL": "http://dbpedia.org/resource/TCL_Technology",
        "Hisense": "http://dbpedia.org/resource/Hisense",
        "Oppo": "http://dbpedia.org/resource/Oppo",
        "Suunto": "http://dbpedia.org/resource/Suunto",
        "Amazfit": "http://dbpedia.org/resource/Amazfit",
        "Withings": "http://dbpedia.org/resource/Withings",
        "Tesla": "http://dbpedia.org/resource/Tesla,_Inc.",
        "Nothing": "http://dbpedia.org/resource/Nothing_(company)",
        "BlackView": "http://dbpedia.org/resource/Blackview"
    }
    
    # 3. Εμπλουτισμός από DBpedia
    for brand_name, brand_node in brands.items():
        if brand_name in brand_uris:
            dbpedia_uri = brand_uris[brand_name]
            print(f"Σύνδεση με DBpedia για: {brand_name}...")

            # SPARQL Ερώτημα για Έτος Ίδρυσης, Τοποθεσία και Έδρα
            query = f"""
            PREFIX dbo: <http://dbpedia.org/ontology/>
            SELECT ?foundingYear ?location ?headquarter
            WHERE {{
                OPTIONAL {{ <{dbpedia_uri}> dbo:foundingYear ?foundingYear . }}
                OPTIONAL {{ <{dbpedia_uri}> dbo:location ?location . }}
                OPTIONAL {{ <{dbpedia_uri}> dbo:headquarter ?headquarter . }}
            }} LIMIT 1
            """

            sparql.setQuery(query)
            sparql.setReturnFormat(JSON)

            # Τα brands είναι ήδη URIs στον γράφο — προσθέτουμε απευθείας sameAs και name
            g.add((brand_node, OWL.sameAs, URIRef(dbpedia_uri)))
            g.add((brand_node, SCHEMA.name, Literal(brand_name, lang="en")))
            
            try:
                results = sparql.query().convert()
                bindings = results["results"]["bindings"]
                
                if bindings:
                    data = bindings[0]
                    
                    # 1. Προσθήκη Έτους Ίδρυσης
                    if "foundingYear" in data:
                        f_year = data["foundingYear"]["value"]
                        g.add((brand_node, SCHEMA.foundingDate, Literal(f_year)))
                    
                    # 2. Προσθήκη Τοποθεσίας (Location)
                    if "location" in data:
                        loc = data["location"]["value"]
                        if loc.startswith("http"):
                            g.add((brand_node, SCHEMA.location, URIRef(loc)))
                        else:
                            g.add((brand_node, SCHEMA.location, Literal(loc, lang="en")))
                            
                    # 3. Προσθήκη Έδρας (Headquarters)
                    if "headquarter" in data:
                        hq = data["headquarter"]["value"]
                        if hq.startswith("http"):
                            g.add((brand_node, SCHEMA.address, URIRef(hq)))
                        else:
                            g.add((brand_node, SCHEMA.address, Literal(hq, lang="en")))
            
            except Exception as e:
                print(f"  -> Σφάλμα/Timeout επικοινωνίας για {brand_name}: Προχωράμε στην επόμενη...")
            
            # Προστασία από Rate Limiting της DBpedia
            time.sleep(0.5)

    print("\nΑποθήκευση του Εμπλουτισμένου Γράφου...")
    g.serialize(destination="master_eshop_enriched.ttl", format="turtle")
    print("Ολοκλήρωση!")

if __name__ == "__main__":
    enrich_graph()