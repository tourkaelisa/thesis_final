"""Διαδικασία Σημασιολογικού Εμπλουτισμού (Semantic Enrichment).
Συνδέει τα τοπικά δεδομένα κατασκευαστών (Brands)
του ηλεκτρονικού καταστήματος με την παγκόσμια βάση γνώσεων της DBpedia.
Μέσω SPARQL endpoints, αντλεί επιπλέον πληροφορίες (π.χ. Έτος Ίδρυσης, Έδρα)
και διασυνδέει τις οντότητες κάνοντας χρήση της ιδιότητας owl:sameAs (Linked Data).
"""
import os
import time
from rdflib import Graph, URIRef, Literal, Namespace
from SPARQLWrapper import SPARQLWrapper, JSON

# Καθορισμός των Ονοματοχώρων (Namespaces) για την οντολογία
SCHEMA = Namespace("http://schema.org/")
OWL = Namespace("http://www.w3.org/2002/07/owl#")
ESHOP = Namespace("http://www.myeshop.gr/resource/")

# Αρχικοποίηση Σύνδεσης (SPARQL Endpoint) με τη βάση γνώσεων DBpedia (με όριο απόκρισης 60 δευτερόλεπτα)
sparql = SPARQLWrapper("https://dbpedia.org/sparql")
sparql.setTimeout(60)
sparql.agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

def enrich_graph():
    """Εκτελεί τη διαδικασία σημασιολογικού εμπλουτισμού του τοπικού γράφου.
    Διαβάζει το βασικό αρχείο RDF, ταυτοποιεί τους κατασκευαστές, ανακτά δεδομένα 
    από την DBpedia, και αποθηκεύει το νέο, εμπλουτισμένο γράφημα.
    """
    print("Φόρτωση του υπάρχοντος Γράφου...")
    g = Graph()
    
    if not os.path.exists("data/master_eshop_fixed.ttl"):
        print("Το αρχείο data/master_eshop_fixed.ttl δεν βρέθηκε!")
        return
        
    g.parse("data/master_eshop_fixed.ttl", format="turtle")
    
    # 1. Εξαγωγή όλων των μοναδικών κατασκευαστών (Brands) από τα υπάρχοντα URIs (π.χ. eshop:Brand_Apple)
    brands = {}  # brand_name -> brand_uri_node
    for s, p, o in g.triples((None, SCHEMA.manufacturer, None)):
        uri_str = str(o)
        if "Brand_" in uri_str:
            brand_name = uri_str.split("Brand_")[-1]
            brands[brand_name] = o  # κρατάμε το URI node

    print(f"Βρέθηκαν {len(brands)} μοναδικές μάρκες στο e-shop.\n")

    # 2. Λεξικό Αντιστοίχισης (Entity Mapping) μεταξύ τοπικών Brands και DBpedia URIs
    brand_uris = {
        "Apple": "http://dbpedia.org/resource/Apple_Inc.",
        "Samsung": "http://dbpedia.org/resource/Samsung_Electronics",
        "Lenovo": "http://dbpedia.org/resource/Lenovo",
        "Sony": "http://dbpedia.org/resource/Sony",
        "Microsoft": "http://dbpedia.org/resource/Microsoft",
        "Nintendo": "http://dbpedia.org/resource/Nintendo",
        "LG": "http://dbpedia.org/resource/LG_Electronics",
        "Garmin": "http://dbpedia.org/resource/Garmin",
        "Xiaomi": "http://dbpedia.org/resource/Xiaomi",
        "Huawei": "http://dbpedia.org/resource/Huawei",
        "HP": "http://dbpedia.org/resource/HP_Inc.",
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
        "BlackView": "http://dbpedia.org/resource/Blackview",
        "AOC": "http://dbpedia.org/resource/AOC_International",
        "Philips": "http://dbpedia.org/resource/Philips",
        "JBL": "http://dbpedia.org/resource/JBL",
        "Marshall": "http://dbpedia.org/resource/Marshall_Amplification",
        "BeyerDynamic": "http://dbpedia.org/resource/Beyerdynamic",
        "Soundcore": "http://dbpedia.org/resource/Anker_Innovations",
        "Anker": "http://dbpedia.org/resource/Anker_Innovations",
        "Sennheiser": "http://dbpedia.org/resource/Sennheiser",
        "Audio-Technica": "http://dbpedia.org/resource/Audio-Technica",
        "Audio": "http://dbpedia.org/resource/Audio-Technica",
        "AirPods": "http://dbpedia.org/resource/Apple_Inc.",
        "Edifier": "http://dbpedia.org/resource/Edifier",
        "Aiwa": "http://dbpedia.org/resource/Aiwa",
        "Skullcandy": "http://dbpedia.org/resource/Skullcandy",
        "Creative": "http://dbpedia.org/resource/Creative_Technology",
        "Beats": "http://dbpedia.org/resource/Beats_Electronics",
        "Bose": "http://dbpedia.org/resource/Bose_Corporation",
        "Panasonic": "http://dbpedia.org/resource/Panasonic",
        "Mackie": "http://dbpedia.org/resource/Mackie",
        "AKG": "http://dbpedia.org/resource/AKG_Acoustics",
        "Pioneer": "http://dbpedia.org/resource/Pioneer_Corporation",
        "Koss": "http://dbpedia.org/resource/Koss_Corporation"
    }
    
    # 3. Σημασιολογικός Εμπλουτισμός (Semantic Enrichment) μέσω του DBpedia SPARQL Endpoint
    for brand_name, brand_node in brands.items():
        if brand_name in brand_uris:
            dbpedia_uri = brand_uris[brand_name]
            print(f"Σύνδεση με DBpedia για: {brand_name}...")

            # Εκτέλεση ερωτήματος SPARQL για την άντληση συμπληρωματικών δεδομένων (Έτος Ίδρυσης, Τοποθεσία, Έδρα)
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

            # Διασύνδεση (Linked Data): Προσθήκη της σχέσης owl:sameAs για την απόλυτη ταύτιση των οντοτήτων
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
            
            # Επιβολή καθυστέρησης προς αποφυγή υπερφόρτωσης του server της DBpedia 
            time.sleep(0.5)

    print("\nΑποθήκευση του Εμπλουτισμένου Γράφου...")
    g.serialize(destination="data/master_eshop_enriched.ttl", format="turtle")
    print("Ολοκλήρωση!")

if __name__ == "__main__":
    enrich_graph()