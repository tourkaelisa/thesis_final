"""FastAPI backend: REST endpoints (αυθεντικοποίηση) + WebSocket dispatcher.

Η επιχειρησιακή λογική βρίσκεται στα services (catalog, search, dashboard,
wishlist, recommendations, semantic_search). Εδώ μένει μόνο η ρύθμιση της
εφαρμογής, το startup και η δρομολόγηση των αιτημάτων του WebSocket.
"""
import os
import sqlite3
import traceback

import rdflib
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import catalog
import dashboard
import db
import recommendations
import search
import semantic_search
import wishlist
from config import ADMIN_EMAIL, CATEGORY_CLASSES, DATABASE_PATH, RDF_FILE_PATH
from graphdb import query_graphdb
from security import (
    UserLogin,
    UserRegistration,
    create_token,
    hash_password,
    verify_password,
)

app = FastAPI()

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

    # Ο in-memory γράφος (rdflib) χρησιμοποιείται ΜΟΝΟ στο startup: για το χτίσιμο
    # των μοντέλων συστάσεων και το αρχικό seeding δημοτικότητας. Όλα τα ερωτήματα
    # που εξυπηρετούν τον client πραγματικού χρόνου πηγαίνουν στο GraphDB.
    print("Φόρτωση RDF στη μνήμη (μόνο για μηχανή συστάσεων & seeding)...")
    if os.path.exists(RDF_FILE_PATH):
        rdf_graph = rdflib.Graph()
        rdf_graph.parse(RDF_FILE_PATH, format="turtle")
        print("RDF φορτώθηκε επιτυχώς.")
        recommendations.build_models(rdf_graph)
        print("Όλα τα μοντέλα είναι έτοιμα!")
        db.seed_popularity(rdf_graph)
    else:
        print(f"Σφάλμα: Το αρχείο {RDF_FILE_PATH} δεν βρέθηκε!")

    # Semantic search: φόρτωση μαρκών από το GraphDB (για το NL parsing)
    try:
        semantic_search.load_brands(query_graphdb)
    except Exception as e:
        print(f"[semantic_search] Αποτυχία φόρτωσης μαρκών: {e}")


# ============================================================ REST: Auth ====
@app.post("/api/register", status_code=201)
async def register_user(user: UserRegistration):
    if not user.terms:
        raise HTTPException(status_code=400, detail="Terms must be accepted.")

    normalized_email = user.email.strip().lower()
    if "@" not in normalized_email or "." not in normalized_email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Invalid email.")

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


@app.post("/api/make-admin")
async def make_admin(payload: UserLogin):
    normalized_email = payload.email.strip().lower()
    if db.set_admin_role(normalized_email) == 0:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"message": f"{normalized_email} is now admin (role=2)"}


# ===================================================== WebSocket dispatcher ====
@app.websocket("/ws/shop")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            # 1. Προϊόντα κατηγορίας
            if action == "get_category":
                category = data.get("category")
                if category in CATEGORY_CLASSES:
                    try:
                        products = catalog.get_category_products(category)
                        await websocket.send_json({"type": "CATEGORY_UPDATED", "products": products})
                    except Exception as e:
                        print(f"GraphDB error in get_category: {e}")
                        await websocket.send_json({"type": "CATEGORY_UPDATED", "products": []})

            # 2. Λεπτομέρειες προϊόντος
            elif action == "get_product_details":
                try:
                    details = catalog.get_product_details(data.get("productId"), data.get("userId"))
                    await websocket.send_json({"type": "PRODUCT_DETAILS", "product": details})
                except Exception as e:
                    print(f"Σφάλμα στο get_product_details: {e}")
                    traceback.print_exc()
                    await websocket.send_json({"type": "PRODUCT_DETAILS", "product": {"specs": [], "name": "Σφάλμα Φόρτωσης"}})

            # 3. Δημοφιλέστερα (slideshow)
            elif action == "get_popular_products":
                slides = dashboard.get_popular_slides()
                await websocket.send_json({"type": "POPULAR_PRODUCTS", "slides": slides})

            # 4. Στατιστικά dashboard (admin)
            elif action == "get_dashboard_stats":
                stats = dashboard.get_dashboard_stats()
                await websocket.send_json({"type": "DASHBOARD_STATS", **stats})

            # 5. Wishlist / δημοτικότητα
            elif action == "add_to_wishlist":
                product_uri = data.get("productId")
                user_id = data.get("userId")
                if product_uri:
                    is_wishlisted, popularity = wishlist.toggle(user_id, product_uri)
                    await websocket.send_json({
                        "type": "WISHLIST_UPDATED",
                        "productId": product_uri,
                        "isWishlisted": is_wishlisted,
                        "popularity": popularity,
                    })

            elif action == "get_wishlist":
                user_id = data.get("userId")
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
                user_id = data.get("userId")
                product_uri = data.get("productId")
                if user_id and product_uri:
                    wishlist.remove(user_id, product_uri)
                    await websocket.send_json({"type": "WISHLIST_ITEM_REMOVED", "productId": product_uri})

            # 6. Σημασιολογική αναζήτηση με φίλτρα
            elif action == "search_category":
                category = data.get("category")
                if category not in CATEGORY_CLASSES:
                    await websocket.send_json({"type": "SEARCH_RESULTS", "products": []})
                else:
                    try:
                        products = search.search_category(
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

            # 7. Προτάσεις όμοιων προϊόντων (item-to-item)
            elif action == "get_recommendations":
                try:
                    formatted = recommendations.get_similar_products(data.get("productId"))
                    if formatted is not None:
                        await websocket.send_json({"type": "RECOMMENDATIONS_UPDATED", "products": formatted})
                    else:
                        await websocket.send_json({"type": "ERROR", "message": "Δεν βρέθηκαν προτάσεις."})
                except Exception as e:
                    print(f"Σφάλμα στα recommendations: {e}")

            # 8. Εξατομικευμένες προτάσεις (βάσει wishlist)
            elif action == "get_personalized_recommendations":
                try:
                    user_id = data.get("userId")
                    if not user_id:
                        await websocket.send_json({"type": "PERSONALIZED_RECOMMENDATIONS", "products": []})
                    else:
                        wishlist_uris = db.get_wishlist_uri_set(user_id)
                        if not wishlist_uris:
                            await websocket.send_json({"type": "PERSONALIZED_RECOMMENDATIONS", "products": []})
                        else:
                            products = recommendations.get_personalized_products(wishlist_uris)
                            await websocket.send_json({"type": "PERSONALIZED_RECOMMENDATIONS", "products": products})
                except Exception as e:
                    print(f"Σφάλμα στα personalized recommendations: {e}")
                    await websocket.send_json({"type": "PERSONALIZED_RECOMMENDATIONS", "products": []})

            # 9. Σημασιολογική αναζήτηση φυσικής γλώσσας (NL → SPARQL)
            elif action == "semantic_search":
                query = data.get("query", "")
                try:
                    pop_map = db.get_popularity_map()
                    result = semantic_search.search(
                        query, query_graphdb,
                        popularity_fn=lambda uri: pop_map.get(uri, 0),
                    )
                    await websocket.send_json({
                        "type": "SEMANTIC_RESULTS",
                        "query": query,
                        "interpreted": result["interpreted"],
                        "products": result["products"],
                    })
                except Exception as e:
                    print(f"Σφάλμα στο semantic search: {e}")
                    await websocket.send_json({
                        "type": "SEMANTIC_RESULTS", "query": query,
                        "interpreted": {}, "products": [], "error": str(e),
                    })

    except WebSocketDisconnect:
        print("Η σύνδεση WebSocket έκλεισε από τον browser.")
    except Exception as e:
        print(f"Απροσδόκητο σφάλμα: {e}")
        traceback.print_exc()
