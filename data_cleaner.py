"""Διαδικασία Καθαρισμού και Τυποποίησης Δεδομένων (Data Cleaning & Normalization).
Αυτό το script διαβάζει τα ακατέργαστα JSON αρχεία (raw_data) που συλλέχθηκαν, 
ομογενοποιεί τα τεχνικά χαρακτηριστικά (χρησιμοποιώντας λεξικά χαρτογράφησης MAPPINGS),
και εξάγει τα καθαρισμένα αρχεία, έτοιμα προς μετατροπή σε RDF (Triplestore).
"""
import json
import os
import re

INPUT_DIR = 'data/raw_data'
OUTPUT_DIR = 'data/cleaned_data'

MAPPINGS = {
    "screen_size": ["Οθόνη - Διαγώνιος", "Οθόνη - Μέγεθος", "Εικόνα - Διαγώνιος", "Οθόνη - Μέγεθος Οθόνης", "Τεχνικά Χαρακτηριστικά - Μέγεθος Οθόνης", "Βασικά Χαρακτηριστικά - Μέγεθος Οθόνης", "Βασικά Χαρακτηριστικά - Διαγώνιος"],
    "ram": ["Μνήμη RAM - Χωρητικότητα Μνήμης", "Μνήμη - RAM", "Επεξεργαστής & Μνήμη - Μνήμη RAM", "Βασικά Χαρακτηριστικά - Μνήμη RAM", "Μνήμη RAM - Μέγεθος"],
    "storage": [
        "Οθόνη & Γραφικά - Χωρητικότητα",
        "Οθόνη & Γραφικά - Αποθηκευτικός Χώρος",
        "Αποθηκευτικός Χώρος - Χωρητικότητα Δίσκου",
        "Αποθηκευτικός Χώρος - Χωρητικότητα",
        "Top Specs - Χωρητικότητα",
        "Σκληρός Δίσκος - Χωρητικότητα Σκληρού Δίσκου", 
        "Μνήμη - Χωρητικότητα", 
        "Επεξεργαστής & Μνήμη - Χωρητικότητα", 
        "Βασικά Χαρακτηριστικά - Χωρητικότητα", 
        "Σκληρός Δίσκος - Χωρητικότητα",
        "Γενικά - Μέγεθος Δίσκου"
    ],
    "weight": ["Γενικά Χαρακτηριστικά - Βάρος", "Βασικά Χαρακτηριστικά - Βάρος", "Τεχνικά Χαρακτηριστικά - Βάρος", "Διαστάσεις με Βάση - Βάρος", "Διαστάσεις χωρίς Βάση - Βάρος", "Γενικά - Βάρος"],
    "refresh_rate": ["Οθόνη - Ρυθμός Ανανέωσης", "Εικόνα - Ρυθμός Ανανέωσης", "Βασικά Χαρακτηριστικά - Ρυθμός Ανανέωσης"],
    "battery": ["Μπαταρία - Χωρητικότητα", "Χωρητικότητα Μπαταρίας", "Τροφοδοσία - Χωρητικότητα", "Βασικά Χαρακτηριστικά - Χωρητικότητα Μπαταρίας", "Μπαταρία & Φόρτιση - Χωρητικότητα"],
    "battery_hours": ["Γενικά - Χρόνος Λειτουργίας", "Μπαταρία - Χρόνος Λειτουργίας", "Μπαταρία - Διάρκεια Μπαταρίας", "Μπαταρία - Μέγιστος Χρόνος Μπαταρίας"],
    "screen_resolution": ["Οθόνη - Ανάλυση", "Ανάλυση Οθόνης", "Οθόνη - Ανάλυση Οθόνης", "Εικόνα - Ανάλυση", "Τεχνικά Χαρακτηριστικά - Ανάλυση Οθόνης", "Βασικά Χαρακτηριστικά - Ανάλυση"],
    "panel": ["Βασικά Χαρακτηριστικά - Panel", "Οθόνη - Panel"],
    "response_time": ["Βασικά Χαρακτηριστικά - Χρόνος Απόκρισης (GTG)", "Βασικά Χαρακτηριστικά - Χρόνος Απόκρισης", "Οθόνη - Χρόνος Απόκρισης"],
    "hdr": ["Βασικά Χαρακτηριστικά - HDR", "Οθόνη - HDR"],
    "curved": ["Βασικά Χαρακτηριστικά - Curved", "Οθόνη - Curved"],
    "connection_type": ["Συνδεσιμότητα - Ασύρματες Συνδέσεις", "Συνδεσιμότητα - Ενσύρματες Συνδέσεις", "Top Specs - Συνδεσιμότητα", "Συνδεσιμότητα - Τύπος Σύνδεσης", "Συνδεσιμότητα - Θύρες"],
    "ultrawide": ["Βασικά Χαρακτηριστικά - UltraWide", "Οθόνη - UltraWide"],
    "height_adjust": ["Εργονομία Βάσης - Ρύθμιση Ύψους"],
    "vesa_mount": ["Εργονομία Βάσης - Δυνατότητα Επιτοίχιας Τοποθέτησης (Vesa)"],
    "headphone_type": ["Γενικά - Τύπος"],
    "noise_cancellation": ["Δυνατότητες & Λειτουργίες - Noise Cancellation", "Top Specs - Noise Cancellation"],
    "use_case": ["Γενικά - Χρήση"],
    "desktop_use": ["Γενικά - Προτεινόμενη Χρήση"],
    "os": ["Λογισμικό - Λειτουργικό Σύστημα"],
    "ram_type": ["Μνήμη RAM - Τύπος"],
    "storage_type": ["Σκληρός Δίσκος - Τύπος"],
    "gpu_memory": ["Κάρτα Γραφικών - Μέγεθος Μνήμης"],
    "console_platform": ["Γενικά - Πλατφόρμα"],
    "console_edition": ["Γενικά - Έκδοση"],
    "console_portable": ["Γενικά - Φορητή"],
    "console_bundle": ["Γενικά - Πακέτο"],
    "cpu_frequency": ["Επεξεργαστής - Συχνότητα"]
}

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def extract_number(text, as_float=False):
    """Απομονώνει και επιστρέφει την πρώτη αριθμητική τιμή από μια συμβολοσειρά (string).
    Υποστηρίζει την ανάγνωση δεκαδικών ψηφίων, μετατρέποντας το κόμμα σε τελεία.
    Αν το as_float είναι True, επιστρέφει float, διαφορετικά επιστρέφει ακέραιο (int).
    """
    text_clean = str(text).replace(',', '.')
    match = re.search(r'\d+(\.\d+)?', text_clean)
    if match:
        return float(match.group()) if as_float else int(float(match.group()))
    return None

def clean_specs(specs):
    cleaned = specs.copy() 
    
    # 1. Οθόνη
    for key in MAPPINGS["screen_size"]:
        if key in cleaned:
            num = extract_number(cleaned.pop(key), as_float=True)
            if num is not None:
                cleaned["screen_size_num"], cleaned["screen_size_unit"] = num, "inches"
            break 

    # 2. RAM
    for key in MAPPINGS["ram"]:
        if key in cleaned:
            num = extract_number(cleaned.pop(key))
            if num is not None:
                cleaned["ram_num"], cleaned["ram_unit"] = num, "GB"
            break

    # 3. Αποθηκευτικός Χώρος
    for key in MAPPINGS["storage"]:
        if key in cleaned:
            raw = str(cleaned.pop(key)).upper()
            num = extract_number(raw, as_float=True)
            if num is not None:
                if 'TB' in raw:
                    num = int(num * 1000)
                cleaned["storage_num"], cleaned["storage_unit"] = int(num), "GB"
            break

    # 4. Βάρος
    for key in MAPPINGS["weight"]:
        if key in cleaned:
            raw = str(cleaned.pop(key)).lower()
            num = extract_number(raw, as_float=True)
            if num is not None:
                cleaned["weight_num"] = num
                cleaned["weight_unit"] = "kg" if "kg" in raw else "gr"
            break

    # 5. Μπαταρία
    for key in MAPPINGS["battery"]:
        if key in cleaned:
            num = extract_number(cleaned.pop(key))
            if num is not None:
                cleaned["battery_num"], cleaned["battery_unit"] = num, "mAh"
            break
            
    # 5b. Μπαταρία (ώρες)
    for key in MAPPINGS["battery_hours"]:
        if key in cleaned:
            num = extract_number(cleaned.pop(key), as_float=True)
            if num is not None:
                cleaned["battery_hours_num"], cleaned["battery_hours_unit"] = num, "hrs"
            break

    # 6. Ρυθμός Ανανέωσης
    for key in MAPPINGS["refresh_rate"]:
        if key in cleaned:
            raw = str(cleaned.pop(key)).split('/')[-1]
            num = extract_number(raw)
            if num is not None:
                cleaned["refresh_rate_num"], cleaned["refresh_rate_unit"] = num, "Hz"
            break

    # 6. Μπαταρία
    for key in MAPPINGS["battery"]:
        if key in cleaned:
            num = extract_number(cleaned.pop(key))
            if num is not None:
                cleaned["battery_num"], cleaned["battery_unit"] = num, "mAh"
            break

    # 7. Κάμερες
    for key, val in list(cleaned.items()):
        if 'Κάμερα' in key and ('Ανάλυση' in key or 'MP' in str(val)):
            num = extract_number(val, as_float=True)
            if num is not None:
                cleaned.pop(key)
                if 'Selfie' in key or 'Μπροστινή' in key:
                    cleaned['camera_selfie_mp_num'], cleaned['camera_selfie_mp_unit'] = num, "MP"
                else:
                    cleaned['camera_main_mp_num'], cleaned['camera_main_mp_unit'] = num, "MP"

    # 8. Ανάλυση Οθόνης 
    for key in MAPPINGS["screen_resolution"]:
        if key in cleaned:
            raw_val = str(cleaned.pop(key))
            match = re.search(r'(\d+)\s*[xX*]\s*(\d+)', raw_val)
            if match:
                cleaned["resolution_width_num"], cleaned["resolution_width_unit"] = int(match.group(1)), "px"
                cleaned["resolution_height_num"], cleaned["resolution_height_unit"] = int(match.group(2)), "px"
            else:
                cleaned["screen_resolution_text"] = raw_val.replace('pixels', '').replace('px', '').strip()
            
    # 9. Panel
    for key in MAPPINGS["panel"]:
        if key in cleaned:
            cleaned["panel_type"] = cleaned.pop(key)
            break

    # 10. Response Time
    for key in MAPPINGS["response_time"]:
        if key in cleaned:
            num = extract_number(cleaned.pop(key), as_float=True)
            if num is not None:
                cleaned["response_time_num"], cleaned["response_time_unit"] = num, "ms"
            break
    
    # 11. HDR
    for key in MAPPINGS["hdr"]:
        if key in cleaned:
            cleaned["hdr"] = cleaned.pop(key)
            break

    # 12. Curved
    for key in MAPPINGS["curved"]:
        if key in cleaned:
            cleaned["curved"] = cleaned.pop(key)
            break   
    
    # 13. Connection Type
    for key in MAPPINGS["connection_type"]:
        if key in cleaned:
            cleaned["connection_type_text"] = cleaned.pop(key)
            break

    # 14. UltraWide
    for key in MAPPINGS["ultrawide"]:
        if key in cleaned:
            cleaned["ultrawide"] = cleaned.pop(key)
            break

    # 15. Height Adjust)
    for key in MAPPINGS["height_adjust"]:
        if key in cleaned:
            cleaned["height_adjust"] = cleaned.pop(key)
            break

    # 16. Vesa 
    for key in MAPPINGS.get("vesa_mount", []):
        if key in cleaned:
            raw_val = str(cleaned.pop(key))
            match = re.search(r'(\d+)\s*[xX*]\s*(\d+)', raw_val)
            if match:
                cleaned["vesa_width_num"], cleaned["vesa_width_unit"] = int(match.group(1)), "mm"
                cleaned["vesa_height_num"], cleaned["vesa_height_unit"] = int(match.group(2)), "mm"
            break

    # 17. Λογικές Μεταβλητές (Booleans)
    cleaned = {k: (True if v == "Ναι" else False if v == "Όχι" else v) for k, v in cleaned.items()}

    # 18. Ακουστικά - Είδος
    for key in MAPPINGS.get("headphone_type", []):
        if key in cleaned:
            cleaned["headphone_type_text"] = cleaned.pop(key)
            break

    # 19. Ακουστικά - Noise Cancellation (ANC)
    for key in MAPPINGS.get("noise_cancellation", []):
        if key in cleaned:
            val = str(cleaned.pop(key)).lower()
            cleaned["has_anc"] = True if ("ναι" in val or "active" in val) else False
            break

    # 21. Ακουστικά - Χρήση
    for key in MAPPINGS.get("use_case", []):
        if key in cleaned:
            cleaned["use_case_text"] = cleaned.pop(key)
            break

    # 22. Desktops - Προτεινόμενη Χρήση
    for key in MAPPINGS.get("desktop_use", []):
        if key in cleaned:
            cleaned["desktop_use_text"] = cleaned.pop(key)
            break

    # 23. Desktops - OS / GPU / RAM_Type / Storage_Type / GPU_Memory
    for key in MAPPINGS.get("os", []):
        if key in cleaned:
            cleaned["os_name"] = cleaned.pop(key)
            break
            
    for key in MAPPINGS.get("ram_type", []):
        if key in cleaned:
            cleaned["ram_type"] = cleaned.pop(key)
            break
            
    for key in MAPPINGS.get("storage_type", []):
        if key in cleaned:
            cleaned["storage_type"] = cleaned.pop(key)
            break
            
    for key in MAPPINGS.get("gpu_memory", []):
        if key in cleaned:
            cleaned["gpu_memory"] = cleaned.pop(key)
            break

    # 25. Desktops - Μέγεθος Θήκης
    case_size = None
    for k in list(cleaned.keys()):
        if k.startswith("Μέγεθος Θήκης"):
            if str(cleaned[k]).lower() == "ναι":
                case_size = k.replace("Μέγεθος Θήκης - ", "").strip()
            cleaned.pop(k)
    if case_size:
        cleaned["case_size_text"] = case_size
        
    # 26. Consoles
    for key in MAPPINGS.get("console_platform", []):
        if key in cleaned:
            cleaned["console_platform"] = cleaned.pop(key)
            break
            
    for key in MAPPINGS.get("console_edition", []):
        if key in cleaned:
            cleaned["console_edition"] = cleaned.pop(key)
            break
            
    for key in MAPPINGS.get("console_portable", []):
        if key in cleaned:
            val = cleaned.pop(key)
            if isinstance(val, bool):
                cleaned["is_portable"] = val
            else:
                cleaned["is_portable"] = True if "ναι" in str(val).lower() else False
            break

    for key in MAPPINGS.get("console_bundle", []):
        if key in cleaned:
            cleaned["console_bundle"] = cleaned.pop(key)
            break

    for key in MAPPINGS.get("cpu_frequency", []):
        if key in cleaned:
            num = extract_number(cleaned.pop(key), as_float=True)
            if num is not None:
                cleaned["cpu_frequency_num"], cleaned["cpu_frequency_unit"] = num, "GHz"
            break

    return cleaned

def clean_all_files():
    """Σαρώνει όλα τα JSON αρχεία του καταλόγου εισόδου, εφαρμόζει τον 
    καθαρισμό στα χαρακτηριστικά (specs) και αφαιρεί τυχόν διπλότυπες εγγραφές (deduplication).
    """
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json')]
    for file_name in files:
        with open(os.path.join(INPUT_DIR, file_name), 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Σφάλμα στο {file_name}: {e}")
                continue

        # Διαγραφή προϊόντων χωρίς τιμή, καθαρισμός τεχνικών χαρακτηριστικών,
        # και αφαίρεση διπλότυπων εγγραφών (deduplication). Κατά τον εντοπισμό διπλοτύπων, 
        # προτιμάται το canonical URL (δηλαδή αυτό που δεν περιέχει χαρακτήρες anchor '#').
        unique_products = {}
        for item in data:
            if item.get('price', 0) > 0: 
                name = item.get('name', '').strip()
                item['specs'] = clean_specs(item.get('specs', {}))
                
                if name not in unique_products or "#" not in item.get('url', ''): 
                    unique_products[name] = item

        output_path = os.path.join(OUTPUT_DIR, f"cleaned_{file_name}")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(list(unique_products.values()), f, ensure_ascii=False, indent=4)
        
        print(f"Καθαρίστηκε: {file_name}")

if __name__ == "__main__":
    clean_all_files()