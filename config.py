"""Κεντρικές ρυθμίσεις του backend."""
import os
import secrets

# Διαδρομές αρχείων / endpoints
RDF_FILE_PATH = "master_eshop_fixed.ttl"
DATABASE_PATH = "users.db"
GRAPHDB_ENDPOINT = "http://localhost:7200/repositories/eshop_thesis"

# JWT
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

# Διαχειριστής (προάγεται αυτόματα σε admin στο startup)
ADMIN_EMAIL = "elisatourka@gmail.com"

# Αντιστοίχιση route κατηγορίας -> κλάση PTO (όπως χρησιμοποιείται στα SPARQL)
CATEGORY_CLASSES = {
    "laptops": "pto:Laptop",
    "mobiles": "pto:Smartphone",
    "tablets": "pto:Tablet_computer",
    "tvs": "pto:Television_set",
    "smartwatches": "pto:Smartwatch",
}

# Ετικέτες κατηγοριών (για slideshow & dashboard)
CATEGORY_LABELS = {
    "laptops": "Laptops",
    "mobiles": "Mobiles",
    "tablets": "Tablets",
    "tvs": "Τηλεοράσεις",
    "smartwatches": "Smartwatches",
}
