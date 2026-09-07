"""SQLite: σύνδεση, σχήμα, seeding και data-access για χρήστες, wishlist και δημοτικότητα.

Εδώ συγκεντρώνεται όλη η πρόσβαση στα μη-σημασιολογικά (συναλλακτικά) δεδομένα,
σε αντιδιαστολή με τα σημασιολογικά δεδομένα των προϊόντων που ζουν στο GraphDB.
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

# συγχρονίζει τη δημοτικότητα με τα πραγματικά αγαπημένα 
# popularity_score = πόσοι χρήστες έχουν το προϊόν στα αγαπημένα (μειώνεται στην αφαίρεση).
# total_additions  = σωρευτικές προσθήκες (δεν μειώνεται).
def sync_popularity(graph: rdflib.Graph):
    with get_db_connection() as connection:
        results = graph.query(
            """
            PREFIX gr: <http://purl.org/goodrelations/v1#>
            SELECT ?uri WHERE { ?uri gr:name ?name . }
            """
        )
        # Διαγραφή παλιών "ορφανών" προϊόντων που έχουν σβηστεί από το GraphDB (π.χ. μετά από data cleaning)
        valid_uris = [(str(r.uri),) for r in results]
        
        # Προσθήκη νέων προϊόντων
        connection.executemany(
            "INSERT OR IGNORE INTO product_popularity "
            "(product_uri, popularity_score, total_additions) VALUES (?, 0, 0)",
            valid_uris,
        )
        
        # Αφαίρεση όσων δεν υπάρχουν πια στο γράφημα
        uri_list = "','".join([u[0] for u in valid_uris])
        connection.execute(f"DELETE FROM product_popularity WHERE product_uri NOT IN ('{uri_list}')")

        # popularity_score = τρέχον πλήθος αγαπημένων (μηδενίζει και παλιές τυχαίες τιμές επειδή στην αρχή είχα βάλει μερικές default).
        connection.execute("UPDATE product_popularity SET popularity_score = 0")
        connection.execute(
            """
            UPDATE product_popularity SET popularity_score = (
                SELECT COUNT(*) FROM wishlist
                WHERE wishlist.product_uri = product_popularity.product_uri
            )
            """
        )
        # total_additions = βάση τουλάχιστον όσα τα τρέχοντα αγαπημένα 
        connection.execute(
            "UPDATE product_popularity SET total_additions = popularity_score "
            "WHERE total_additions < popularity_score"
        )
        print("Synced popularity from wishlist (0 = κανένας στα αγαπημένα).")


# Δημιουργεί χρήστη και επιστρέφει το id του
def create_user(first_name, last_name, email, phone, password_hash, terms_accepted) -> int:
    with get_db_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO users (
                first_name, last_name, email, phone, password_hash, terms_accepted, role
            )
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (first_name, last_name, email, phone, password_hash, terms_accepted),
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


# Δημοτικότητα 
def get_popularity_map() -> dict:
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


# Wishlist
def get_wishlist_uris(user_id) -> list:
    """Τα URIs της wishlist με σειρά προσθήκης (νεότερα πρώτα)."""
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
      - popularity_score = πόσοι χρήστες το έχουν ΤΩΡΑ στα αγαπημένα (μειώνεται στην αφαίρεση)
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
