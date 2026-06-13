import json
import os

input_dir = 'data/raw_data'

def find_camera_keys():
    files = [f for f in os.listdir(input_dir) if f.endswith('.json')]
    
    found_keys = set()
    
    for file_name in files:
        # Ψάχνουμε κυρίως στα αρχεία με κινητά/tablets (αν έχουν τέτοιο όνομα)
        if 'mobile' in file_name.lower() or 'kinit' in file_name.lower() or 'tablet' in file_name.lower() or 'smart' in file_name.lower():
            with open(os.path.join(input_dir, file_name), 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Ελέγχουμε τα 5 πρώτα προϊόντα κάθε αρχείου
            for item in data[:5]:
                specs = item.get('specs', {})
                for key, value in specs.items():
                    # Ψάχνουμε λέξεις κλειδιά στα κλειδιά ή στις τιμές
                    if 'Κάμερα' in key or 'Camera' in key or 'Ανάλυση' in key or 'MP' in str(value):
                        found_keys.add(f"Αρχείο: {file_name} -> ΚΛΕΙΔΙ: '{key}' (Παράδειγμα τιμής: '{value}')")

    print("\n🕵️ ΑΠΟΤΕΛΕΣΜΑΤΑ ΑΝΑΖΗΤΗΣΗΣ ΓΙΑ ΚΑΜΕΡΕΣ:\n" + "="*50)
    if found_keys:
        for k in found_keys:
            print(k)
    else:
        print("Δεν βρέθηκε καμία λέξη 'Κάμερα' ή 'MP' στα πρώτα 5 προϊόντα των αρχείων σας!")
    print("="*50 + "\n")

if __name__ == "__main__":
    find_camera_keys()