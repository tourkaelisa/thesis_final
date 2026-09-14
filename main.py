"""Κεντρικός Διακομιστής (Backend) με χρήση του πλαισίου FastAPI.
Υλοποιεί τα σημεία τερματισμού REST (αυθεντικοποίηση/εγγραφή χρηστών) και ένα κεντρικό
σύστημα δρομολόγησης (dispatcher) μέσω WebSockets για επικοινωνία πραγματικού χρόνου.
"""
import os
import sqlite3
import traceback
import rdflib
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import analytics
import catalog
import db
import filters
import realtime
import recommendations
import search
import wishlist
from config import ADMIN_EMAIL, CATEGORY_CLASSES, DATABASE_PATH, RDF_FILE_PATH
from graphdb import query_graphdb
from security import (
    UserLogin,
    UserRegistration,
    create_token,
    hash_password,
    verify_password,
    verify_token,
)

app = FastAPI()


def authenticated_user_id(data) -> int | None:
    """Εξάγει και επιστρέφει το αναγνωριστικό χρήστη (user_id) από ένα έγκυρο JSON Web Token (JWT).

    Για λόγους ασφαλείας, η ταυτότητα του χρήστη επιβεβαιώνεται αποκλειστικά από 
    την κρυπτογραφική υπογραφή του token, αποτρέποντας απόπειρες πλαστογράφησης 
    μέσω παραποίησης των δεδομένων του client.
    """
    payload = verify_token(data.get("token") or "")
    if not payload:
        return None
    try:
        return int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        return None


def is_admin(data) -> bool:
    """Επαληθεύει εάν ο τρέχων χρήστης διαθέτει δικαιώματα Διαχειριστή (role = 2)."""
    payload = verify_token(data.get("token") or "")
    return bool(payload) and payload.get("role") == 2

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    db.init_user_database()
    try:
        db.set_admin_role(ADMIN_EMAIL)
    except Exception as e:
        print(f"Warning: Could not set admin role: {e}")
    print(f"SQLite users database ready: {DATABASE_PATH}")

    # Σημασιολογικός Γράφος Μνήμης (In-Memory RDF Graph): Φορτώνεται μόνο κατά 
    # την εκκίνηση του συστήματος προκειμένου να κατασκευαστούν τα μοντέλα μηχανικής 
    # μάθησης (Συστήματα Συστάσεων) και να συγχρονιστούν οι αρχικές μετρικές δημοτικότητας.
    # Τα αιτήματα των πελατών σε πραγματικό χρόνο δρομολογούνται απευθείας στο GraphDB.
    print("Φόρτωση RDF στη μνήμη (μόνο για μηχανή συστάσεων & seeding)...")
    if os.path.exists(RDF_FILE_PATH):
        rdf_graph = rdflib.Graph()
        rdf_graph.parse(RDF_FILE_PATH, format="turtle")
        print("RDF φορτώθηκε επιτυχώς.")
        recommendations.build_models(rdf_graph)
        print("Όλα τα μοντέλα είναι έτοιμα!")
        db.sync_popularity(rdf_graph)
    else:
        print(f"Σφάλμα: Το αρχείο {RDF_FILE_PATH} δεν βρέθηκε!")


# ΥΠΗΡΕΣΙΕΣ REST: ΑΥΘΕΝΤΙΚΟΠΟΙΗΣΗ & ΔΙΑΧΕΙΡΙΣΗ ΧΡΗΣΤΩΝ 
@app.post("/api/register", status_code=201)
async def register_user(user: UserRegistration):
    if not user.terms:
        raise HTTPException(status_code=400, detail="Terms must be accepted.")

    normalized_email = user.email  # ήδη επικυρωμένο & κανονικοποιημένο από το schema

    try:
        user_id = db.create_user(
            user.firstName.strip(),
            user.lastName.strip(),
            normalized_email,
            user.phone.strip() if user.phone else None,
            hash_password(user.password),
            1 if user.terms else 0,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email already exists.")

    # Ενημέρωση Πραγματικού Χρόνου (Live Push): Εκπομπή μηνύματος (broadcast) στους 
    # διαχειριστές για την ανανέωση των στατιστικών εγγραφών (dashboard metrics).
    await realtime.hub.broadcast_stats()

    return {
        "id": user_id,
        "firstName": user.firstName.strip(),
        "lastName": user.lastName.strip(),
        "email": normalized_email,
        "role": 1,
        "token": create_token(user_id, 1),
    }


@app.post("/api/login")
async def login_user(credentials: UserLogin):
    normalized_email = credentials.email.strip().lower()
    user = db.get_user_by_email(normalized_email)

    if not user or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return {
        "id": user["id"],
        "firstName": user["first_name"],
        "lastName": user["last_name"],
        "email": user["email"],
        "role": user["role"],
        "token": create_token(user["id"], user["role"]),
    }


# ΔΡΟΜΟΛΟΓΗΤΗΣ WEBSOCKET (REAL-TIME DISPATCHER)
@app.websocket("/ws/shop")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            # 0. Έλεγχος Ασφαλείας Token (Authentication Check): Σε περίπτωση που το token 
            # είναι άκυρο ή ληγμένο, εκπέμπεται ειδικό μήνυμα "AUTH_INVALID" ώστε ο client 
            # να αποσυνδεθεί ομαλά. Αιτήματα χωρίς καθόλου token (ανώνυμοι χρήστες) εξυπηρετούνται κανονικά.
            token = data.get("token")
            if token and not verify_token(token):
                await websocket.send_json({"type": "AUTH_INVALID"})
                continue

            # 1. Ανάκτηση Προϊόντων ανά Κατηγορία (Category Browsing)
            if action == "get_category":
                category = data.get("category")
                if category in CATEGORY_CLASSES:
                    try:
                        products = catalog.get_category_products(category)
                        await websocket.send_json({"type": "CATEGORY_UPDATED", "products": products})
                    except Exception as e:
                        print(f"GraphDB error in get_category: {e}")
                        await websocket.send_json({"type": "CATEGORY_UPDATED", "products": []})

            # 2. Αναλυτικά Στοιχεία Προϊόντος (Product Details)
            elif action == "get_product_details":
                try:
                    details = catalog.get_product_details(data.get("productId"), authenticated_user_id(data))
                    await websocket.send_json({"type": "PRODUCT_DETAILS", "product": details})
                except Exception as e:
                    print(f"Σφάλμα στο get_product_details: {e}")
                    traceback.print_exc()
                    await websocket.send_json({"type": "PRODUCT_DETAILS", "product": {"specs": [], "name": "Σφάλμα Φόρτωσης"}})

            # 3. Κορυφαία σε Δημοτικότητα Προϊόντα (Trending Products)
            elif action == "get_popular_products":
                products = analytics.get_popular_products()
                await websocket.send_json({"type": "POPULAR_PRODUCTS", "products": products})

            # 4. Μετρικές Πίνακα Ελέγχου (Dashboard Analytics - Αποκλειστικά για Διαχειριστές)
            elif action == "get_dashboard_stats":
                if not is_admin(data):
                    await websocket.send_json({"type": "ERROR", "message": "Δεν έχετε δικαίωμα πρόσβασης."})
                else:
                    # Εγγραφή της σύνδεσης (WebSocket) ως διαχειριστή-συνδρομητή (subscriber)
                    # ώστε να λαμβάνει ζωντανά δεδομένα (push notifications) με τις νέες αλλαγές.
                    realtime.hub.register(websocket)
                    stats = analytics.get_dashboard_stats()
                    await websocket.send_json({"type": "DASHBOARD_STATS", **stats})

            # 5. Διαχείριση Λίστας Αγαπημένων & Μετρικών Δημοτικότητας (Wishlist Management)
            elif action == "add_to_wishlist":
                user_id = authenticated_user_id(data)
                product_uri = data.get("productId")
                if not user_id:
                    await websocket.send_json({"type": "ERROR", "message": "Απαιτείται σύνδεση."})
                elif product_uri:
                    is_wishlisted, popularity = wishlist.toggle(user_id, product_uri)
                    await websocket.send_json({
                        "type": "WISHLIST_UPDATED",
                        "productId": product_uri,
                        "isWishlisted": is_wishlisted,
                        "popularity": popularity,
                    })
                    # Live push: τα αγαπημένα άλλαξαν → φρέσκα στατιστικά στους admins.
                    await realtime.hub.broadcast_stats()

            elif action == "get_wishlist":
                user_id = authenticated_user_id(data)
                if not user_id:
                    await websocket.send_json({"type": "WISHLIST_DATA", "products": []})
                else:
                    try:
                        products = wishlist.get_products(user_id)
                        await websocket.send_json({"type": "WISHLIST_DATA", "products": products})
                    except Exception as e:
                        print(f"GraphDB error in get_wishlist: {e}")
                        await websocket.send_json({"type": "WISHLIST_DATA", "products": []})

            elif action == "remove_from_wishlist":
                user_id = authenticated_user_id(data)
                product_uri = data.get("productId")
                if user_id and product_uri:
                    wishlist.remove(user_id, product_uri)
                    await websocket.send_json({"type": "WISHLIST_ITEM_REMOVED", "productId": product_uri})
                    # Live push: η αφαίρεση μεταβάλλει δημοτικότητα/engagement/churn.
                    await realtime.hub.broadcast_stats()

            # 6. Σύνθετη Αναζήτηση με Φίλτρα (Faceted Search)
            elif action == "search_category":
                category = data.get("category")
                if category not in CATEGORY_CLASSES:
                    await websocket.send_json({"type": "SEARCH_RESULTS", "products": []})
                else:
                    try:
                        products = filters.search_category(
                            category,
                            data.get("filters", {}),
                            data.get("propRanges", {}),
                            float(data.get("priceMin", 0)),
                            float(data.get("priceMax", 999999)),
                        )
                        await websocket.send_json({"type": "SEARCH_RESULTS", "products": products})
                    except Exception as e:
                        print(f"GraphDB error: {e}")
                        await websocket.send_json({"type": "SEARCH_RESULTS", "products": [], "error": str(e)})

            # 7. Συστήματα Συστάσεων: Παρόμοια Προϊόντα (Item-Based Recommendations)
            elif action == "get_recommendations":
                try:
                    formatted = recommendations.get_similar_products(data.get("productId"))
                    if formatted is not None:
                        await websocket.send_json({"type": "RECOMMENDATIONS_UPDATED", "products": formatted})
                    else:
                        await websocket.send_json({"type": "ERROR", "message": "Δεν βρέθηκαν προτάσεις."})
                except Exception as e:
                    print(f"Σφάλμα στα recommendations: {e}")

            # 8. Συστήματα Συστάσεων: Εξατομικευμένες Προτάσεις (Personalized Recommendations)
            elif action == "get_personalized_recommendations":
                try:
                    user_id = authenticated_user_id(data)
                    if not user_id:
                        await websocket.send_json({"type": "PERSONALIZED_RECOMMENDATIONS", "products": []})
                    else:
                        wishlist_uris = db.get_wishlist_uris(user_id)
                        if not wishlist_uris:
                            await websocket.send_json({"type": "PERSONALIZED_RECOMMENDATIONS", "products": []})
                        else:
                            products = recommendations.get_personalized_products(wishlist_uris)
                            await websocket.send_json({"type": "PERSONALIZED_RECOMMENDATIONS", "products": products})
                except Exception as e:
                    print(f"Σφάλμα στα personalized recommendations: {e}")
                    await websocket.send_json({"type": "PERSONALIZED_RECOMMENDATIONS", "products": []})

            # 9. Σημασιολογική Αναζήτηση Λέξεων-Κλειδιών (Keyword Search) μέσω SPARQL
            elif action == "keyword_search":
                query = data.get("query", "")
                try:
                    pop_map = db.get_popularity_map()
                    products = search.search(
                        query, query_graphdb,
                        popularity_fn=lambda uri: pop_map.get(uri, 0),
                    )
                    await websocket.send_json({
                        "type": "SEARCH_RESULTS",
                        "query": query,
                        "products": products,
                    })
                except Exception as e:
                    print(f"Σφάλμα στο keyword search: {e}")
                    await websocket.send_json({
                        "type": "SEARCH_RESULTS", "query": query,
                        "products": [], "error": str(e),
                    })

    except WebSocketDisconnect:
        print("Η σύνδεση WebSocket έκλεισε από τον browser.")
    except Exception as e:
        print(f"Απροσδόκητο σφάλμα: {e}")
        traceback.print_exc()
    finally:
        # Αποεγγραφή (Unregister) του WebSocket για αποφυγή διαρροών μνήμης (Memory Leaks)
        realtime.hub.unregister(websocket)
