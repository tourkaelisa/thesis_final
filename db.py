"""SQLite: σύνδεση, σχήμα, seeding και data-access για χρήστες, wishlist και δημοτικότητα.

Εδώ συγκεντρώνεται όλη η πρόσβαση στα μη-σημασιολογικά (συναλλακτικά) δεδομένα,
σε αντιδιαστολή με τα σημασιολογικά δεδομένα των προϊόντων που ζουν στο GraphDB.
"""
import random
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
                popularity_score INTEGER NOT NULL DEFAULT 0
            )
            """
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


def seed_popularity(graph: rdflib.Graph):
    """Αρχικοποιεί τυχαίες βαθμολογίες δημοτικότητας (μία φορά, στο startup)."""
    with get_db_connection() as connection:
        count = connection.execute("SELECT COUNT(*) FROM product_popularity").fetchone()[0]
        if count > 0:
            return

        results = graph.query(
            """
            PREFIX gr: <http://purl.org/goodrelations/v1#>
            SELECT ?uri WHERE { ?uri gr:name ?name . }
            """
        )

        rows = []
        for r in results:
            uri = str(r.uri)
            roll = random.random()
            if roll < 0.10:
                score = random.randint(200, 500)
            elif roll < 0.30:
                score = random.randint(80, 200)
            else:
                score = random.randint(5, 80)
            rows.append((uri, score))

        connection.executemany(
            "INSERT OR IGNORE INTO product_popularity (product_uri, popularity_score) VALUES (?, ?)",
            rows,
        )
        print(f"Seeded popularity for {len(rows)} products.")


# ---------------------------------------------------------------- Χρήστες ----
def create_user(first_name, last_name, email, phone, password_hash, terms_accepted) -> int:
    """Δημιουργεί χρήστη και επιστρέφει το id του. Μπορεί να ρίξει sqlite3.IntegrityError."""
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


# ----------------------------------------------------------- Δημοτικότητα ----
def get_popularity(product_uri) -> int:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT popularity_score FROM product_popularity WHERE product_uri = ?",
            (product_uri,),
        ).fetchone()
    return row["popularity_score"] if row else 0


def attach_popularity(products: list) -> list:
    """Προσθέτει το πεδίο 'popularity' σε κάθε προϊόν (με κλειδί 'id')."""
    with get_db_connection() as conn:
        for product in products:
            row = conn.execute(
                "SELECT popularity_score FROM product_popularity WHERE product_uri = ?",
                (product["id"],),
            ).fetchone()
            product["popularity"] = row["popularity_score"] if row else 0
    return products


def get_popularity_map() -> dict:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT product_uri, popularity_score FROM product_popularity"
        ).fetchall()
    return {r["product_uri"]: r["popularity_score"] for r in rows}


def get_top_popular(uris: list):
    """Από μια λίστα uris, επιστρέφει τη γραμμή με τη μέγιστη δημοτικότητα (ή None)."""
    with get_db_connection() as conn:
        placeholders = ",".join("?" * len(uris))
        return conn.execute(
            f"SELECT product_uri, popularity_score FROM product_popularity "
            f"WHERE product_uri IN ({placeholders}) "
            f"ORDER BY popularity_score DESC LIMIT 1",
            uris,
        ).fetchone()


# ---------------------------------------------------------------- Wishlist ----
def get_wishlist_uris(user_id) -> list:
    """Τα URIs της wishlist με σειρά προσθήκης (νεότερα πρώτα)."""
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT product_uri FROM wishlist WHERE user_id = ? ORDER BY added_at DESC",
            (user_id,),
        ).fetchall()
    return [r["product_uri"] for r in rows]


def get_wishlist_uri_set(user_id) -> set:
    """Τα URIs της wishlist ως σύνολο (χωρίς σειρά) — για τη μηχανή προτάσεων."""
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT product_uri FROM wishlist WHERE user_id = ?",
            (user_id,),
        ).fetchall()
    return {r["product_uri"] for r in rows}


def is_wishlisted(user_id, product_uri) -> bool:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id FROM wishlist WHERE user_id = ? AND product_uri = ?",
            (user_id, product_uri),
        ).fetchone()
    return row is not None


def toggle_wishlist(user_id, product_uri):
    """Toggle: αν το προϊόν υπάρχει στη wishlist το αφαιρεί· αλλιώς το προσθέτει
    και αυξάνει τη δημοτικότητα. Επιστρέφει (is_wishlisted, popularity)."""
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
            conn.execute(
                """
                INSERT INTO product_popularity (product_uri, popularity_score) VALUES (?, 1)
                ON CONFLICT(product_uri) DO UPDATE SET popularity_score = popularity_score + 1
                """,
                (product_uri,),
            )
            wishlisted = True
        row = conn.execute(
            "SELECT popularity_score FROM product_popularity WHERE product_uri = ?",
            (product_uri,),
        ).fetchone()
    return wishlisted, (row["popularity_score"] if row else 0)


def remove_from_wishlist(user_id, product_uri):
    with get_db_connection() as conn:
        conn.execute(
            "DELETE FROM wishlist WHERE user_id = ? AND product_uri = ?",
            (user_id, product_uri),
        )


# --------------------------------------------------------------- Dashboard ----
def get_dashboard_db_stats():
    """Επιστρέφει (total_users, total_wishlists, total_products, top_rows) από τη SQLite."""
    with get_db_connection() as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_wishlists = conn.execute(
            "SELECT SUM(popularity_score) FROM product_popularity"
        ).fetchone()[0] or 0
        total_products = conn.execute(
            "SELECT COUNT(*) FROM product_popularity"
        ).fetchone()[0]
        top_rows = conn.execute(
            "SELECT product_uri, popularity_score FROM product_popularity "
            "ORDER BY popularity_score DESC LIMIT 10"
        ).fetchall()
    return total_users, total_wishlists, total_products, top_rows
