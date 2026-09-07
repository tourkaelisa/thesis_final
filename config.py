#Κεντρικές ρυθμίσεις του backend
import os
import secrets

# Διαδρομές αρχείων / endpoints
RDF_FILE_PATH = "data/master_eshop_enriched.ttl" #τα δεδομένα με την DBpedia διασυνδεση
DATABASE_PATH = "users.db"
# Σε Docker δίνεται μέσω env (service name: graphdb)· τοπικά πέφτει σε localhost.
GRAPHDB_ENDPOINT = os.environ.get(
    "GRAPHDB_ENDPOINT", "http://localhost:7200/repositories/eshop_thesis"
)


# JWT
def _load_jwt_secret() -> str:
    """Σταθερό JWT secret ώστε τα tokens να επιβιώνουν στα restarts.

    Προτεραιότητα: μεταβλητή περιβάλλοντος JWT_SECRET. Αλλιώς, διαβάζεται/
    δημιουργείται ένα τοπικό αρχείο (.jwt_secret) — έτσι κάθε επανεκκίνηση του
    server δεν ακυρώνει τα ήδη εκδομένα tokens (δηλ. δεν «πετάει έξω» τους χρήστες).
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
        pass  # Αν δεν γράφεται, πέφτουμε σε in-memory secret (όπως πριν).
    return new_secret


JWT_SECRET = _load_jwt_secret()
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 2

# Διαχειριστής (προάγεται αυτόματα σε admin στο startup)
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "elisatourka@gmail.com")

# Αντιστοίχιση route κατηγορίας -> κλάση PTO 
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

