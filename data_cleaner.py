import json
import os
import re

INPUT_DIR = 'data/raw_data'
OUTPUT_DIR = 'data/cleaned_data'

MAPPINGS = {
    "screen_size": ["Οθόνη - Διαγώνιος", "Οθόνη - Μέγεθος", "Εικόνα - Διαγώνιος", "Οθόνη - Μέγεθος Οθόνης", "Τεχνικά Χαρακτηριστικά - Μέγεθος Οθόνης", "Βασικά Χαρακτηριστικά - Μέγεθος Οθόνης"],
    "ram": ["Μνήμη RAM - Χωρητικότητα Μνήμης", "Μνήμη - RAM", "Επεξεργαστής & Μνήμη - Μνήμη RAM", "Βασικά Χαρακτηριστικά - Μνήμη RAM"],
    "storage": ["Σκληρός Δίσκος - Χωρητικότητα Σκληρού Δίσκου", "Μνήμη - Χωρητικότητα", "Επεξεργαστής & Μνήμη - Χωρητικότητα", "Βασικά Χαρακτηριστικά - Χωρητικότητα"],
    "weight": ["Γενικά Χαρακτηριστικά - Βάρος", "Βασικά Χαρακτηριστικά - Βάρος", "Τεχνικά Χαρακτηριστικά - Βάρος", "Διαστάσεις με Βάση - Βάρος", "Διαστάσεις χωρίς Βάση - Βάρος", "Γενικά - Βάρος"],
    "refresh_rate": ["Οθόνη - Ρυθμός Ανανέωσης", "Εικόνα - Ρυθμός Ανανέωσης"],
    "battery": ["Μπαταρία - Χωρητικότητα", "Χωρητικότητα Μπαταρίας", "Τροφοδοσία - Χωρητικότητα", "Βασικά Χαρακτηριστικά - Χωρητικότητα Μπαταρίας", "Μπαταρία & Φόρτιση - Χωρητικότητα"],
    "screen_resolution": ["Οθόνη - Ανάλυση", "Ανάλυση Οθόνης", "Οθόνη - Ανάλυση Οθόνης", "Εικόνα - Ανάλυση", "Τεχνικά Χαρακτηριστικά - Ανάλυση Οθόνης"]
}

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Βοηθητική συνάρτηση που βρίσκει τον πρώτο αριθμό σε ένα κείμενο. Επιστρέφει float αν as_float=True, αλλιώς int.
def extract_number(text, as_float=False):
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

    # 5. Ρυθμός Ανανέωσης
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
            break

    # 9. Booleans // δεν τα χω φορτωσει ακομα στο graphDB
    cleaned = {k: (True if v == "Ναι" else False if v == "Όχι" else v) for k, v in cleaned.items()}

    return cleaned

# καθαρισμος τον json αρχειων
def clean_all_files():
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.json')]
    for file_name in files:
        with open(os.path.join(INPUT_DIR, file_name), 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Σφάλμα στο {file_name}: {e}")
                continue

        # κρατάμε μόνο προϊόντα με price>0, καθαρισμός των specs, deduplication με βάση το name (όταν υπάρχουν διπλά, προτιμάμε το URL χωρίς # που δείχνει στην κανονική σελίδα του προϊόντος)
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