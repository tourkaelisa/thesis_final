"""Κεντρικό Αρχείο Ρυθμίσεων (Configuration) του Backend της εφαρμογής."""
import os
import secrets

# Βασικές διαδρομές αρχείων και endpoints
RDF_FILE_PATH = "data/master_eshop_enriched.ttl"  # Τοπικό αρχείο δεδομένων RDF (συμπεριλαμβάνει τις διασυνδέσεις με την DBpedia)
DATABASE_PATH = "users.db"

# URL του GraphDB. Σε περιβάλλον Docker αντλείται από τις μεταβλητές περιβάλλοντος (env), 
# διαφορετικά χρησιμοποιείται η προεπιλεγμένη τοπική διεύθυνση (localhost).
GRAPHDB_ENDPOINT = os.environ.get(
    "GRAPHDB_ENDPOINT", "http://localhost:7200/repositories/eshop_thesis"
)

# Παράμετροι Αυθεντικοποίησης μέσω JSON Web Token (JWT)
def _load_jwt_secret() -> str:
    """Ανακτά ή δημιουργεί ένα σταθερό μυστικό κλειδί (JWT secret) 
    ώστε τα tokens των χρηστών να παραμένουν έγκυρα μεταξύ των επανεκκινήσεων του διακομιστή.

    Ροή Εκτέλεσης:
    1. Έλεγχος για μεταβλητή περιβάλλοντος JWT_SECRET.
    2. Εάν απουσιάζει, διαβάζεται (ή δημιουργείται) το τοπικό αρχείο '.jwt_secret'.
    Αυτή η προσέγγιση διασφαλίζει ότι μια επανεκκίνηση του server δεν αποσυνδέει (kick out) 
    τους ήδη συνδεδεμένους χρήστες.
    """
    env = os.environ.get("JWT_SECRET")
    if env:
        return env

    secret_file = os.path.join(os.path.dirname(__file__), ".jwt_secret")
    try:
        with open(secret_file, "r", encoding="utf-8") as f:
            existing = f.read().strip()
            if existing:
                return existing
    except FileNotFoundError:
        pass

    new_secret = secrets.token_hex(32)
    try:
        with open(secret_file, "w", encoding="utf-8") as f:
            f.write(new_secret)
    except OSError:
        pass  # Αν δεν γράφεται, πέφτουμε σε in-memory secret
    return new_secret


JWT_SECRET = _load_jwt_secret()
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 2

# Προεπιλεγμένο email Διαχειριστή. Κατά την εκκίνηση του συστήματος, 
# ο συγκεκριμένος λογαριασμός προάγεται αυτόματα σε ρόλο Admin (role=2).
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "elisatourka@gmail.com")

# Αντιστοίχιση μεταξύ των εσωτερικών ονομασιών (routes) των κατηγοριών του Frontend 
# και των αντίστοιχων σημασιολογικών κλάσεων της Οντολογίας Προϊόντων (Product Ontology)
CATEGORY_CLASSES = {
    "laptops": "pto:Laptop",
    "mobiles": "pto:Smartphone",
    "tablets": "pto:Tablet_computer",
    "tvs": "pto:Television_set",
    "smartwatches": "pto:Smartwatch",
    "desktops": "pto:Desktop_computer",
    "headphones": "pto:Headphones",
    "consoles": "pto:Game_console",
    "monitors": "pto:Computer_monitor",
}

