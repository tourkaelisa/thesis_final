"""Μετατροπή JSON δεδομένων σε Σημασιολογικό Γράφο (RDF Triplestore).
Διαβάζει τα καθαρισμένα JSON αρχεία, ταυτοποιεί τις κλάσεις 
βάσει της Οντολογίας Προϊόντων (PTO), μοντελοποιεί τις σχέσεις χρησιμοποιώντας GoodRelations (gr) και Schema.org, 
και εξάγει το τελικό αποτέλεσμα σε μορφή Turtle (.ttl).
"""
import json
import os
import re
from rdflib import Graph, Literal, RDF, URIRef, Namespace
from rdflib.namespace import XSD

# 1. Ορισμός Ονοματοχώρων (Namespaces) για την παραγωγή σημασιολογικών τριπλέτων
GR = Namespace("http://purl.org/goodrelations/v1#")
PTO = Namespace("http://www.productontology.org/id/")
SCHEMA = Namespace("http://schema.org/")
ESHOP = Namespace("http://www.myeshop.gr/resource/")
PROP = Namespace("http://www.myeshop.gr/property/")

def get_pto_class(category):
    """Αντιστοιχίζει το όνομα της κατηγορίας προϊόντος στην κατάλληλη 
    κλάση (Class) της Οντολογίας Προϊόντων (PTO).
    """
    cat = category.lower()
    if "laptop" in cat: return PTO.Laptop
    if "κινητά" in cat or "mobile" in cat: return PTO.Smartphone
    if "tv" in cat or "τηλεορ" in cat: return PTO.Television_set
    if "tablet" in cat: return PTO.Tablet_computer
    if "watch" in cat: return PTO.Smartwatch
    if "monitor" in cat: return PTO.Computer_monitor
    if "headphone" in cat: return PTO.Headphones
    if "desktop" in cat or "σταθεροί" in cat or "pc" in cat: return PTO.Desktop_computer
    if "console" in cat or "κονσόλες" in cat: return PTO.Game_console
    return GR.ProductOrService

def create_rdf():
    """Εκτελεί τη μαζική μετατροπή των JSON δεδομένων σε γράφο RDF.
    Αναλύει δυναμικά τα ποσοτικά (Quantitative) και ποιοτικά (Qualitative) 
    χαρακτηριστικά, δημιουργώντας τις απαραίτητες δομές (Nodes) και διασυνδέσεις.
    """
    g = Graph()
    g.bind("gr", GR)
    g.bind("pto", PTO)
    g.bind("schema", SCHEMA)
    g.bind("eshop", ESHOP)
    g.bind("prop", PROP)

    input_dir = 'data/cleaned_data'
    files = [f for f in os.listdir(input_dir) if f.endswith('.json')]

    for file_name in files:
        with open(os.path.join(input_dir, file_name), 'r', encoding='utf-8') as f:
            products = json.load(f)
        
        for i, item in enumerate(products):
            category_tag = file_name.replace('cleaned_', '').replace('.json', '')
            prod_id = f"{category_tag}_{i+1}"
            
            product_uri = ESHOP[prod_id]
            g.add((product_uri, RDF.type, GR.ProductOrService))
            
            # Χειρισμός ελλιπών δεδομένων: Αν η κατηγορία απουσιάζει ("N/A"), 
            # εξάγεται αυτόματα από το όνομα του αντίστοιχου αρχείου
            actual_cat = item['category'] if item['category'] != "N/A" else category_tag
            g.add((product_uri, RDF.type, get_pto_class(actual_cat)))
            
            g.add((product_uri, GR.name, Literal(item['name'], lang="el")))
            g.add((product_uri, SCHEMA.image, URIRef(item['image'])))
            g.add((product_uri, SCHEMA.url, URIRef(item['url'])))
            g.add((product_uri, SCHEMA.price, Literal(item['price'], datatype=XSD.float)))
            g.add((product_uri, SCHEMA.priceCurrency, Literal("EUR")))

            brand = item['name'].split()[0]
            
            # Κανονικοποίηση (Normalization) συγκεκριμένων προβληματικών 
            # ονομασιών κατασκευαστών που εξάγονται απευθείας από τον τίτλο
            brand_normalization = {
                "Audio": "Audio-Technica",
                "AirPods": "Apple"
            }
            if brand in brand_normalization:
                brand = brand_normalization[brand]
                
            brand_uri = ESHOP[f"Brand_{brand}"]
            g.add((product_uri, SCHEMA.manufacturer, brand_uri))

            specs = item.get('specs', {})
            
            # --- ΔΥΝΑΜΙΚΗ ΣΗΜΑΣΙΟΛΟΓΙΚΗ ΧΑΡΤΟΓΡΑΦΗΣΗ ΧΑΡΑΚΤΗΡΙΣΤΙΚΩΝ (DYNAMIC SPEC MAPPING) ---
            for spec_key, spec_val in specs.items():
                
                # 1. Ποσοτικά Χαρακτηριστικά (Quantitative Values): Δημιουργία κόμβων (nodes) 
                # βάσει της κλάσης gr:QuantitativeValue (π.χ. screen_size_num)
                if spec_key.endswith('_num'):
                    base_name = spec_key.replace('_num', '') # βγάζει το "screen_size"
                    unit_key = f"{base_name}_unit" # ψάχνει το "screen_size_unit"
                    
                    q_val_uri = ESHOP[f"{prod_id}_{base_name}"]
                    g.add((q_val_uri, RDF.type, GR.QuantitativeValue))
                    g.add((q_val_uri, GR.hasValueFloat, Literal(spec_val, datatype=XSD.float)))
                    
                    unit_map = {"inches": "INH", "GB": "E34", "kg": "KGM", "gr": "GRM", "mAh": "MAH", "Hz": "HTZ", "GHz": "GHZ", "MP": "C62", "mm": "MMT","px": "E37", "ms": "C26", "hrs": "HUR"}
                    unit_code = unit_map.get(specs.get(unit_key), "C62") 
                    g.add((q_val_uri, GR.hasUnitOfMeasurement, Literal(unit_code)))
                    g.add((product_uri, GR.quantitativeProductOrServiceProperty, q_val_uri))

               # 2. Ποιοτικά Χαρακτηριστικά (Qualitative Values): Διαχείριση κειμένων (Strings) 
               # και λογικών τιμών (Booleans) αγνοώντας τις μονάδες μέτρησης (_unit)
                elif not spec_key.endswith('_unit'):
                    clean_key = spec_key.replace('\xa0', ' ').strip()
                    val_str = str(spec_val).strip()
                    
                    if val_str:
                        # Διαχωρισμός πολλαπλών τιμών σε διακριτές εγγραφές (π.χ. "Android, iOS")
                        values_list = [v.strip() for v in val_str.replace('/', ',').split(',')]
                        
                        for v in values_list:
                            if not v: continue
                            
                            if "Χρώμα" in clean_key:
                                g.add((product_uri, SCHEMA.color, Literal(v, lang="el")))
                                
                            elif "Έτος Κυκλοφορίας" in clean_key:
                                # Εντοπισμός έτους κυκλοφορίας (4 ψηφία που ξεκινούν με 19 ή 20)
                                year_match = re.search(r'\b(19|20)\d{2}\b', v)
                                if year_match:
                                    # Χρήση του τύπου δεδομένων xsd:gYear για ορθή σημασιολογική αναπαράσταση
                                    g.add((product_uri, SCHEMA.releaseDate, Literal(year_match.group(), datatype=XSD.gYear)))
                                else:
                                    # Εναλλακτική λύση (Fallback) σε απλό κείμενο εάν η μορφοποίηση δεν είναι τυπική
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
                            elif "panel_type" in clean_key:
                                g.add((product_uri, PROP.panel_type, Literal(v, datatype=XSD.string)))
                            elif "hdr" in clean_key:
                                if isinstance(spec_val, bool):
                                    g.add((product_uri, PROP.hdr_support, Literal(spec_val, datatype=XSD.boolean)))
                            elif "curved" in clean_key:
                                if isinstance(spec_val, bool):
                                    g.add((product_uri, PROP.is_curved, Literal(spec_val, datatype=XSD.boolean)))
                            elif "ultrawide" in clean_key:
                                if isinstance(spec_val, bool):
                                    g.add((product_uri, PROP.is_ultrawide, Literal(spec_val, datatype=XSD.boolean)))
                            elif "height_adjust" in clean_key:
                                if isinstance(spec_val, bool):
                                    g.add((product_uri, PROP.height_adjustment, Literal(spec_val, datatype=XSD.boolean)))
                            elif "connection_type_text" in clean_key:
                                g.add((product_uri, PROP.connection_type, Literal(v, datatype=XSD.string)))
                            elif "headphone_type_text" in clean_key:
                                g.add((product_uri, PROP.headphone_type, Literal(v, datatype=XSD.string)))
                            elif "has_anc" in clean_key:
                                if isinstance(spec_val, bool):
                                    g.add((product_uri, PROP.has_anc, Literal(spec_val, datatype=XSD.boolean)))
                            elif "use_case_text" in clean_key:
                                g.add((product_uri, PROP.use_case, Literal(v, datatype=XSD.string)))
                            elif "desktop_use_text" in clean_key:
                                g.add((product_uri, PROP.use_case, Literal(v, datatype=XSD.string)))
                            elif "os_name" in clean_key:
                                g.add((product_uri, SCHEMA.operatingSystem, Literal(v, datatype=XSD.string)))
                            elif "ram_type" in clean_key:
                                g.add((product_uri, PROP.ram_type, Literal(v, datatype=XSD.string)))
                            elif "storage_type" in clean_key:
                                g.add((product_uri, PROP.storage_type, Literal(v, datatype=XSD.string)))
                            elif "gpu_memory" in clean_key:
                                g.add((product_uri, PROP.gpu_memory, Literal(v, datatype=XSD.string)))
                            elif "case_size_text" in clean_key:
                                g.add((product_uri, PROP.case_size, Literal(v, datatype=XSD.string)))
                            elif "console_platform" in clean_key:
                                g.add((product_uri, PROP.console_platform, Literal(v, datatype=XSD.string)))
                            elif "console_edition" in clean_key:
                                g.add((product_uri, PROP.console_edition, Literal(v, datatype=XSD.string)))
                            elif "console_bundle" in clean_key:
                                g.add((product_uri, PROP.console_bundle, Literal(v, datatype=XSD.string)))
                            elif "is_portable" in clean_key:
                                if isinstance(spec_val, bool):
                                    g.add((product_uri, PROP.is_portable, Literal(spec_val, datatype=XSD.boolean)))
                            
            # --- ΑΝΑΠΑΡΑΣΤΑΣΗ ΤΙΜΗΣ & ΕΜΠΟΡΙΚΗΣ ΠΡΟΣΦΟΡΑΣ (PRICING & OFFERING) ---
            price_spec = ESHOP[f"price_{prod_id}"]
            g.add((price_spec, RDF.type, GR.UnitPriceSpecification))
            g.add((price_spec, GR.hasCurrencyValue, Literal(item['price'], datatype=XSD.float)))
            g.add((price_spec, GR.hasCurrency, Literal("EUR")))
            
            offer = ESHOP[f"offer_{prod_id}"]
            g.add((offer, RDF.type, GR.Offering))
            g.add((offer, GR.includes, product_uri))
            g.add((offer, GR.hasPriceSpecification, price_spec))

    g.serialize(destination="data/master_eshop_fixed.ttl", format="turtle")
    print("\nΟλοκληρώθηκε")

if __name__ == "__main__":
    create_rdf()