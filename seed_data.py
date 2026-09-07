import sqlite3
import random
from datetime import datetime, timedelta
from security import hash_password
from db import get_db_connection

# Λίστες ονομάτων για τυχαία δημιουργία
FIRST_NAMES = [
    "Γιώργος", "Κώστας", "Δημήτρης", "Γιάννης", "Νίκος", "Μαρία", "Ελένη", "Κατερίνα", 
    "Βασιλική", "Άννα", "Χρήστος", "Ανδρέας", "Σπύρος", "Σοφία", "Δήμητρα", "Μιχάλης",
    "Παναγιώτης", "Ευαγγελία", "Γεωργία", "Ιωάννα", "Αλέξανδρος", "Σταύρος", "Βασίλης",
    "Ειρήνη", "Αναστασία", "Θεόδωρος", "Μαρίνα", "Χριστίνα", "Άγγελος", "Εμμανουήλ"
]

LAST_NAMES = [
    "Παπαδόπουλος", "Γεωργίου", "Οικονόμου", "Αντωνίου", "Μακρής", "Νικολάου", 
    "Κωνσταντίνου", "Καραμανλής", "Μιχαηλίδης", "Παναγιωτόπουλος", "Δημητρίου",
    "Ρήγας", "Βασιλείου", "Λαμπρόπουλος", "Αθανασίου", "Λέκκας", "Καρράς", 
    "Αναστασίου", "Δούκας", "Μήτρου", "Αλεξόπουλος", "Κοσμάς", "Ιωαννίδης",
    "Μπάρκας", "Αργυρίου", "Διαμαντής", "Ρουσόπουλος", "Φλώρος", "Βλάχος", "Νάκος",
    "Παπαδοπούλου", "Οικονόμου", "Μακρή", "Βασιλείου", "Μιχαηλίδου", "Αλεξοπούλου"
]

def generate_random_date(start_days_ago, end_days_ago):
    now = datetime.now()
    start_date = now - timedelta(days=start_days_ago)
    end_date = now - timedelta(days=end_days_ago)
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates)
    random_date = start_date + timedelta(days=random_number_of_days, 
                                       hours=random.randint(0,23), 
                                       minutes=random.randint(0,59),
                                       seconds=random.randint(0,59))
    return random_date

def seed_database():
    with get_db_connection() as conn:
        print("Διαγραφή παλιών δοκιμαστικών χρηστών (role = 1) και των wishlists τους...")
        # Διαγραφή παλιών wishlists από χρήστες που δεν είναι admin
        conn.execute("DELETE FROM wishlist WHERE user_id IN (SELECT id FROM users WHERE role = 1)")
        # Διαγραφή των απλών χρηστών (όχι admin)
        conn.execute("DELETE FROM users WHERE role = 1")
        
        # Λήψη όλων των product_uris από τον πίνακα product_popularity
        products = conn.execute("SELECT product_uri FROM product_popularity").fetchall()
        product_uris = [p["product_uri"] for p in products]
        
        if not product_uris:
            print("Δεν βρέθηκαν προϊόντα! Βεβαιώσου ότι έχει τρέξει το GraphDB και το db.sync_popularity().")
            return
            
        print(f"Δημιουργία 200 χρηστών με password 'password123'...")
        password = "password123"
        hashed_pw = hash_password(password)
        
        user_ids = []
        # Κατανομή εγγραφών μέσα στις τελευταίες 35 ημέρες
        for i in range(200):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            email = f"user_{i}_{random.randint(1000, 9999)}@example.com"
            phone = f"69{random.randint(10000000, 99999999)}"
            created_at = generate_random_date(35, 0)
            
            cursor = conn.execute(
                """
                INSERT INTO users (first_name, last_name, email, phone, password_hash, terms_accepted, role, created_at)
                VALUES (?, ?, ?, ?, ?, 1, 1, ?)
                """,
                (first, last, email, phone, hashed_pw, created_at.strftime("%Y-%m-%d %H:%M:%S"))
            )
            user_ids.append((cursor.lastrowid, created_at))
            
        print("Δημιουργία τυχαίων αλληλεπιδράσεων (wishlist)...")
        # Επαναφορά όλων των μετρητών popularity_score/total_additions στο 0 για καθαρή εκκίνηση
        conn.execute("UPDATE product_popularity SET popularity_score = 0, total_additions = 0")
        
        wishlist_count = 0
        for uid, user_created_at in user_ids:
            # Κάθε χρήστης προσθέτει από 0 έως 12 προϊόντα στο wishlist
            num_products = random.randint(0, 12)
            if num_products == 0:
                continue
                
            chosen_uris = random.sample(product_uris, num_products)
            
            for uri in chosen_uris:
                # Η ημερομηνία προσθήκης (added_at) πρέπει να είναι *μετά* την ημερομηνία εγγραφής (created_at)
                # και *πριν* από τώρα
                now = datetime.now()
                time_diff = now - user_created_at
                if time_diff.total_seconds() > 0:
                    random_seconds = random.uniform(0, time_diff.total_seconds())
                    added_at = user_created_at + timedelta(seconds=random_seconds)
                else:
                    added_at = now
                    
                conn.execute(
                    "INSERT INTO wishlist (user_id, product_uri, added_at) VALUES (?, ?, ?)",
                    (uid, uri, added_at.strftime("%Y-%m-%d %H:%M:%S"))
                )
                
                # Ενημέρωση στατιστικών (total_additions & popularity_score αυξάνονται, 
                # θεωρούμε ότι δεν τα αφαίρεσαν για να υπάρχει πλούσια δράση)
                conn.execute(
                    """
                    UPDATE product_popularity 
                    SET popularity_score = popularity_score + 1,
                        total_additions = total_additions + 1
                    WHERE product_uri = ?
                    """,
                    (uri,)
                )
                wishlist_count += 1
                
        conn.commit()
        print(f"Ολοκληρώθηκε! Προστέθηκαν 200 χρήστες και {wishlist_count} προσθήκες σε wishlists.")

if __name__ == "__main__":
    seed_database()
