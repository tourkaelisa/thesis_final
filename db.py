"""Διαχείριση Σχεσιακής Βάσης Δεδομένων (SQLite).
Υλοποιεί τη σύνδεση, τον ορισμό σχήματος (schema), την αρχικοποίηση (seeding)
και την πρόσβαση σε συναλλακτικά δεδομένα (χρήστες, wishlists, μετρικές δημοτικότητας).

Λειτουργεί συμπληρωματικά προς το GraphDB: τα συναλλακτικά δεδομένα 
διατηρούνται εδώ, ενώ τα σημασιολογικά (οντολογία) στο Triplestore.
"""
import sqlite3
import rdflib
from config import DATABASE_PATH


def get_db_connection():
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def init_user_database():
    with get_db_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT,
                password_hash TEXT NOT NULL,
                terms_accepted INTEGER NOT NULL DEFAULT 0,
                role INTEGER NOT NULL DEFAULT 1 CHECK (role IN (1, 2)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS product_popularity (
                product_uri TEXT PRIMARY KEY,
                popularity_score INTEGER NOT NULL DEFAULT 0,
                total_additions INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        existing_cols = [
            r[1] for r in connection.execute("PRAGMA table_info(product_popularity)").fetchall()
        ]
        if "total_additions" not in existing_cols:
            connection.execute(
                "ALTER TABLE product_popularity "
                "ADD COLUMN total_additions INTEGER NOT NULL DEFAULT 0"
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS wishlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_uri TEXT NOT NULL,
                added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, product_uri),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_wishlist_user ON wishlist(user_id)"
        )

def sync_popularity(graph: rdflib.Graph):
    """Συγχρονίζει τις μετρικές δημοτικότητας των προϊόντων της τοπικής βάσης
    με το τρέχον γράφημα (GraphDB) και τις λίστες αγαπημένων (wishlists).

    Υπολογίζει δύο κύριους δείκτες:
    - popularity_score: Ο αριθμός των ενεργών χρηστών που διατηρούν το προϊόν στα αγαπημένα (αυξομειώνεται).
    - total_additions: Ο συνολικός, σωρευτικός αριθμός προσθηκών του προϊόντος (αποκλειστικά αύξουσα συνάρτηση).
    """
    with get_db_connection() as connection:
        results = graph.query(
            """
            PREFIX gr: <http://purl.org/goodrelations/v1#>
            SELECT ?uri WHERE { ?uri gr:name ?name . }
            """
        )
        # Καθαρισμός "ορφανών" εγγραφών: ταυτοποίηση προϊόντων που διαγράφηκαν 
        # από το GraphDB (π.χ. μετά από εκ νέου Data Cleaning)
        valid_uris = [(str(r.uri),) for r in results]
        
        # Καταχώρηση νέων προϊόντων (αν δεν υπάρχουν ήδη)
        connection.executemany(
            "INSERT OR IGNORE INTO product_popularity "
            "(product_uri, popularity_score, total_additions) VALUES (?, 0, 0)",
            valid_uris,
        )
        
        # Αφαίρεση προϊόντων που έχουν πάψει να υφίστανται στο σημασιολογικό γράφημα
        uri_list = "','".join([u[0] for u in valid_uris])
        connection.execute(f"DELETE FROM product_popularity WHERE product_uri NOT IN ('{uri_list}')")

        # Επαναϋπολογισμός του popularity_score (διαγράφει προηγούμενες τιμές 
        # και υπολογίζει με ακρίβεια τις τρέχουσες συσχετίσεις από τον πίνακα wishlist)
        connection.execute("UPDATE product_popularity SET popularity_score = 0")
        connection.execute(
            """
            UPDATE product_popularity SET popularity_score = (
                SELECT COUNT(*) FROM wishlist
                WHERE wishlist.product_uri = product_popularity.product_uri
            )
            """
        )
        # Διασφάλιση ακεραιότητας: Το total_additions πρέπει να είναι 
        # τουλάχιστον ίσο ή μεγαλύτερο από το τρέχον popularity_score
        connection.execute(
            "UPDATE product_popularity SET total_additions = popularity_score "
            "WHERE total_additions < popularity_score"
        )
        print("Synced popularity from wishlist (0 = κανένας στα αγαπημένα).")


def create_user(first_name, last_name, email, phone, password_hash, terms_accepted, role=1) -> int:
    """Δημιουργεί μια νέα εγγραφή χρήστη στη βάση (πίνακας users) 
    και επιστρέφει το μοναδικό αναγνωριστικό (id) που του ανατέθηκε.
    """
    with get_db_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO users (
                first_name, last_name, email, phone, password_hash, terms_accepted, role
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (first_name, last_name, email, phone, password_hash, terms_accepted, role),
        )
        return cursor.lastrowid


def get_user_by_email(email):
    with get_db_connection() as connection:
        return connection.execute(
            """
            SELECT id, first_name, last_name, email, password_hash, role
            FROM users
            WHERE email = ?
            """,
            (email,),
        ).fetchone()


def set_admin_role(email) -> int:
    """Προάγει τον χρήστη σε διαχειριστή (role = 2). Επιστρέφει το πλήθος γραμμών που άλλαξαν."""
    with get_db_connection() as connection:
        result = connection.execute(
            "UPDATE users SET role = 2 WHERE email = ?", (email,)
        )
        return result.rowcount


def get_popularity_map() -> dict:
    """Ανακτά τον πλήρη χάρτη (dictionary) δημοτικότητας.
    Δομή: { product_uri : popularity_score }
    """
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT product_uri, popularity_score FROM product_popularity"
        ).fetchall()
    return {r["product_uri"]: r["popularity_score"] for r in rows}


def get_top_popular_uris(limit: int = 8) -> list:
    """Τα URIs των πιο δημοφιλών προϊόντων συνολικά, σε φθίνουσα δημοτικότητα.

    Επιστρέφει λίστα από (product_uri, popularity_score). Το product_uri
    χρησιμοποιείται ως δεύτερο κριτήριο για σταθερή σειρά όταν τα score ισοβαθμούν."""
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT product_uri, popularity_score FROM product_popularity "
            "ORDER BY popularity_score DESC, product_uri LIMIT ?",
            (limit,),
        ).fetchall()
    return [(r["product_uri"], r["popularity_score"]) for r in rows]


def get_wishlist_uris(user_id) -> list:
    """Επιστρέφει τη λίστα των URIs των προϊόντων που έχει αποθηκεύσει
    ο συγκεκριμένος χρήστης στα αγαπημένα του. Η ταξινόμηση γίνεται χρονολογικά
    (από το πιο πρόσφατο στο παλαιότερο).
    """
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT product_uri FROM wishlist WHERE user_id = ? ORDER BY added_at DESC",
            (user_id,),
        ).fetchall()
    return [r["product_uri"] for r in rows]


def is_wishlisted(user_id, product_uri) -> bool:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id FROM wishlist WHERE user_id = ? AND product_uri = ?",
            (user_id, product_uri),
        ).fetchone()
    return row is not None


def toggle_wishlist(user_id, product_uri):
    """Toggle αγαπημένου. Ενημερώνει δύο μετρητές:
      - popularity_score = πόσοι χρήστες το έχουν τώρα στα αγαπημένα (μειώνεται στην αφαίρεση)
      - total_additions  = σωρευτικές προσθήκες (αυξάνεται μόνο στην προσθήκη, δεν μειώνεται)
    Επιστρέφει (is_wishlisted, popularity)."""
    with get_db_connection() as conn:
        already = conn.execute(
            "SELECT id FROM wishlist WHERE user_id = ? AND product_uri = ?",
            (user_id, product_uri),
        ).fetchone()
        if already:
            conn.execute(
                "DELETE FROM wishlist WHERE user_id = ? AND product_uri = ?",
                (user_id, product_uri),
            )
            wishlisted = False
        else:
            if user_id:
                conn.execute(
                    "INSERT OR IGNORE INTO wishlist (user_id, product_uri) VALUES (?, ?)",
                    (user_id, product_uri),
                )
            wishlisted = True

        # popularity = τρέχον πλήθος χρηστών με το προϊόν στα αγαπημένα
        count = conn.execute(
            "SELECT COUNT(*) FROM wishlist WHERE product_uri = ?", (product_uri,)
        ).fetchone()[0]
        # +1 στις σωρευτικές προσθήκες μόνο όταν όντως προστέθηκε από συνδεδεμένο χρήστη
        added_delta = 1 if (wishlisted and user_id) else 0
        conn.execute(
            """
            INSERT INTO product_popularity (product_uri, popularity_score, total_additions)
            VALUES (?, ?, ?)
            ON CONFLICT(product_uri) DO UPDATE SET
                popularity_score = excluded.popularity_score,
                total_additions = total_additions + ?
            """,
            (product_uri, count, added_delta, added_delta),
        )
    return wishlisted, count


def remove_from_wishlist(user_id, product_uri):
    """Αφαιρεί το προϊόν από τη wishlist και ξαναϋπολογίζει το popularity_score"""
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM wishlist WHERE user_id = ? AND product_uri = ?",
            (user_id, product_uri),
        )
        count = conn.execute(
            "SELECT COUNT(*) FROM wishlist WHERE product_uri = ?", (product_uri,)
        ).fetchone()[0]
        conn.execute(
            "UPDATE product_popularity SET popularity_score = ? WHERE product_uri = ?",
            (count, product_uri),
        )
