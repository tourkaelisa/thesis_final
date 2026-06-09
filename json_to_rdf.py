import json
import os
import re
from rdflib import Graph, Literal, RDF, URIRef, Namespace
from rdflib.namespace import XSD

# 1. NAMESPACES
GR = Namespace("http://purl.org/goodrelations/v1#")
PTO = Namespace("http://www.productontology.org/id/")
SCHEMA = Namespace("http://schema.org/")
ESHOP = Namespace("http://www.myeshop.gr/resource/")
PROP = Namespace("http://www.myeshop.gr/property/")

def get_pto_class(category):
    cat = category.lower()
    if "laptop" in cat: return PTO.Laptop
    if "κινητά" in cat or "mobile" in cat: return PTO.Smartphone
    if "tv" in cat or "τηλεορ" in cat: return PTO.Television_set
    if "tablet" in cat: return PTO.Tablet_computer
    if "watch" in cat: return PTO.Smartwatch
    return GR.ProductOrService

def create_rdf():
    g = Graph()
    g.bind("gr", GR)
    g.bind("pto", PTO)
    g.bind("schema", SCHEMA)
    g.bind("eshop", ESHOP)
    g.bind("prop", PROP)

    input_dir = 'cleaned_data'
    files = [f for f in os.listdir(input_dir) if f.endswith('.json')]

    for file_name in files:
        with open(os.path.join(input_dir, file_name), 'r', encoding='utf-8') as f:
            products = json.load(f)
        
        for i, item in enumerate(products):
            category_tag = file_name.replace('cleaned_', '').replace('.json', '')
            prod_id = f"{category_tag}_{i+1}"
            
            product_uri = ESHOP[prod_id]
            g.add((product_uri, RDF.type, GR.ProductOrService))
            g.add((product_uri, RDF.type, get_pto_class(item['category'])))
            g.add((product_uri, GR.name, Literal(item['name'], lang="el")))
            g.add((product_uri, SCHEMA.image, URIRef(item['image'])))
            g.add((product_uri, SCHEMA.url, URIRef(item['url'])))
            g.add((product_uri, SCHEMA.price, Literal(item['price'], datatype=XSD.float)))
            g.add((product_uri, SCHEMA.priceCurrency, Literal("EUR")))

            brand = item['name'].split()[0]
            brand_uri = ESHOP[f"Brand_{brand}"]
            g.add((product_uri, SCHEMA.manufacturer, brand_uri))

            specs = item.get('specs', {})
            
            # --- ΔΥΝΑΜΙΚΗ ΧΑΡΤΟΓΡΑΦΗΣΗ ΧΑΡΑΚΤΗΡΙΣΤΙΚΩΝ ---
            for spec_key, spec_val in specs.items():
                
                # 1. ΠΟΣΟΤΙΚΑ: Αν το κλειδί τελειώνει σε "_num", π.χ. "screen_size_num"
                if spec_key.endswith('_num'):
                    base_name = spec_key.replace('_num', '') # βγάζει το "screen_size"
                    unit_key = f"{base_name}_unit" # ψάχνει το "screen_size_unit"
                    
                    q_val_uri = ESHOP[f"{prod_id}_{base_name}"]
                    g.add((q_val_uri, RDF.type, GR.QuantitativeValue))
                    g.add((q_val_uri, GR.hasValueFloat, Literal(spec_val, datatype=XSD.float)))
                    
                    unit_map = {"inches": "INH", "GB": "E34", "kg": "KGM", "gr": "GRM", "mAh": "MAH", "Hz": "HTZ", "MP": "C62", "mm": "MMT","px": "E37"}
                    unit_code = unit_map.get(specs.get(unit_key), "C62") 
                    g.add((q_val_uri, GR.hasUnitOfMeasurement, Literal(unit_code)))
                    g.add((product_uri, GR.quantitativeProductOrServiceProperty, q_val_uri))

               # 2. ΠΟΙΟΤΙΚΑ: Αγνοεί τα "_unit" και κρατάει τα υπόλοιπα (Κείμενα)
                elif not spec_key.endswith('_unit'):
                    clean_key = spec_key.replace('\xa0', ' ').strip()
                    val_str = str(spec_val).strip()
                    
                    if val_str:
                        # Χωρίζουμε τις τιμές αν υπάρχουν πολλές (π.χ. Android, iOS)
                        values_list = [v.strip() for v in val_str.replace('/', ',').split(',')]
                        
                        for v in values_list:
                            if not v: continue
                            
                            if "Χρώμα" in clean_key:
                                g.add((product_uri, SCHEMA.color, Literal(v, lang="el")))
                                
                            elif "Έτος Κυκλοφορίας" in clean_key:
                                # Ψάχνουμε για 4 συνεχόμενα ψηφία που ξεκινούν με 19 ή 20
                                year_match = re.search(r'\b(19|20)\d{2}\b', v)
                                if year_match:
                                    # Χρήση xsd:gYear για σωστή σημασιολογική αρχειοθέτηση
                                    g.add((product_uri, SCHEMA.releaseDate, Literal(year_match.group(), datatype=XSD.gYear)))
                                else:
                                    # Fallback σε κείμενο αν η τιμή είναι περίεργη
                                    g.add((product_uri, SCHEMA.releaseDate, Literal(v, lang="el")))
                                    
                            elif "Λειτουργικό Σύστημα" in clean_key or "Λογισμικό" in clean_key:
                                if re.search(r'[α-ωΑ-ΩάέήίόύώΆΈΉΊΌΎΏ]', v):
                                    g.add((product_uri, SCHEMA.operatingSystem, Literal(v, lang="el")))
                                else:
                                    g.add((product_uri, SCHEMA.operatingSystem, Literal(v, lang="en")))
                            elif "Οικογένεια" in clean_key and "Επεξεργαστής" in clean_key:
                                g.add((product_uri, PROP.cpu_model, Literal(v, lang="en")))
                            elif "Ανάλυση" in clean_key and "Οθόνη" in clean_key:
                                g.add((product_uri, PROP.screen_resolution, Literal(v, lang="en")))
                            elif "Ευκρίνεια" in clean_key:
                                g.add((product_uri, PROP.definition, Literal(v, lang="en")))

            # ΤΙΜΗ & ΠΡΟΣΦΟΡΑ
            price_spec = ESHOP[f"price_{prod_id}"]
            g.add((price_spec, RDF.type, GR.UnitPriceSpecification))
            g.add((price_spec, GR.hasCurrencyValue, Literal(item['price'], datatype=XSD.float)))
            g.add((price_spec, GR.hasCurrency, Literal("EUR")))
            
            offer = ESHOP[f"offer_{prod_id}"]
            g.add((offer, RDF.type, GR.Offering))
            g.add((offer, GR.includes, product_uri))
            g.add((offer, GR.hasPriceSpecification, price_spec))

    g.serialize(destination="master_eshop_fixed.ttl", format="turtle")
    print("\nΟλοκληρώθηκε")

if __name__ == "__main__":
    create_rdf()