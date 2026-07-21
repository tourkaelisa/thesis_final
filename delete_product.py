"""Πλήρης αφαίρεση προϊόντος από το eshop (GraphDB + TTL + SQLite).

Σβήνει το προϊόν ΚΑΙ τους κόμβους ποσοτικών χαρακτηριστικών του και από τις τρεις
πηγές, ώστε να μην επανεμφανίζεται μετά από restart (μέσω προτάσεων/δημοτικότητας).

Χρήση:
    python delete_product.py --name "Lenovo V15"
    python delete_product.py --uri "http://www.myeshop.gr/product/..."
    python delete_product.py --name "Lenovo V15" --yes      # χωρίς ερώτηση επιβεβαίωσης

Σημείωση: το --name βρίσκει ΟΛΑ τα προϊόντα που περιέχουν το κείμενο στο όνομά τους.
"""
import argparse
import sqlite3

import rdflib
import requests

from config import DATABASE_PATH, GRAPHDB_ENDPOINT, RDF_FILE_PATH
from graphdb import query_graphdb

GR = "http://purl.org/goodrelations/v1#"
QUANT_PROP = rdflib.URIRef(GR + "quantitativeProductOrServiceProperty")
INCLUDES = rdflib.URIRef(GR + "includes")
HAS_PRICE_SPEC = rdflib.URIRef(GR + "hasPriceSpecification")
GRAPHDB_UPDATE_ENDPOINT = GRAPHDB_ENDPOINT + "/statements"


def _escape(text: str) -> str:
    """Ασφαλής εισαγωγή σε SPARQL string literal."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def resolve_products(arg: str, by_name: bool) -> list[tuple[str, str]]:
    """Επιστρέφει λίστα (uri, name) που ταιριάζουν με το όρισμα, ρωτώντας το GraphDB."""
    if by_name:
        filter_clause = f'FILTER(CONTAINS(LCASE(STR(?name)), LCASE("{_escape(arg)}")))'
    else:
        filter_clause = f"FILTER(?uri = <{arg}>)"
    query = f"""
    PREFIX gr: <{GR}>
    SELECT ?uri ?name WHERE {{
        ?uri gr:name ?name .
        {filter_clause}
    }}
    """
    return [(r["uri"]["value"], r["name"]["value"]) for r in query_graphdb(query)]


def delete_from_graphdb(uri: str) -> None:
    """Σβήνει από το GraphDB όλα τα triples του προϊόντος + των κόμβων χαρακτηριστικών."""
    # UNION ώστε κάθε ομάδα να βρίσκεται ανεξάρτητα — δουλεύει ακόμη κι αν το προϊόν
    # έχει ήδη μερικώς διαγραφεί (π.χ. απομένουν ορφανά offer/price).
    update = f"""
    PREFIX gr: <{GR}>
    DELETE {{
      ?node ?np ?no .
      ?offer ?op ?oo .
      ?price ?pp ?po .
      <{uri}> ?p ?o .
    }}
    WHERE {{
      {{
        <{uri}> ?p ?o .
        OPTIONAL {{
          <{uri}> gr:quantitativeProductOrServiceProperty ?node .
          ?node ?np ?no .
        }}
      }}
      UNION
      {{
        ?offer gr:includes <{uri}> .
        ?offer ?op ?oo .
        OPTIONAL {{
          ?offer gr:hasPriceSpecification ?price .
          ?price ?pp ?po .
        }}
      }}
    }}
    """
    response = requests.post(
        GRAPHDB_UPDATE_ENDPOINT,
        data={"update": update},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()


def delete_from_ttl(uri: str) -> int:
    """Σβήνει τα ίδια triples από το αρχείο TTL. Επιστρέφει πλήθος triples που αφαιρέθηκαν."""
    graph = rdflib.Graph()
    graph.parse(RDF_FILE_PATH, format="turtle")

    subject = rdflib.URIRef(uri)
    removed = 0

    def _remove_all(node) -> None:
        nonlocal removed
        for triple in list(graph.triples((node, None, None))):
            graph.remove(triple)
            removed += 1

    # Κόμβοι ποσοτικών χαρακτηριστικών που κρέμονται από το προϊόν.
    for node in list(graph.objects(subject, QUANT_PROP)):
        _remove_all(node)

    # GoodRelations: προσφορά (Offering) που περιλαμβάνει το προϊόν + το PriceSpecification της.
    for offer in list(graph.subjects(INCLUDES, subject)):
        for price in list(graph.objects(offer, HAS_PRICE_SPEC)):
            _remove_all(price)
        _remove_all(offer)

    # Τέλος, όλα τα triples του ίδιου του προϊόντος.
    _remove_all(subject)

    if removed:
        graph.serialize(destination=RDF_FILE_PATH, format="turtle")
    return removed


def delete_from_sqlite(uri: str) -> tuple[int, int]:
    """Καθαρίζει τις αναφορές στο SQLite. Επιστρέφει (γραμμές wishlist, γραμμές popularity)."""
    with sqlite3.connect(DATABASE_PATH) as conn:
        wl = conn.execute("DELETE FROM wishlist WHERE product_uri = ?", (uri,)).rowcount
        pop = conn.execute(
            "DELETE FROM product_popularity WHERE product_uri = ?", (uri,)
        ).rowcount
    return wl, pop


def main() -> None:
    parser = argparse.ArgumentParser(description="Πλήρης αφαίρεση προϊόντος από το eshop.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--uri", help="Ακριβές URI του προϊόντος.")
    group.add_argument("--name", help="Τμήμα του ονόματος (βρίσκει όλα τα προϊόντα που το περιέχουν).")
    parser.add_argument("--yes", action="store_true", help="Παράλειψη της ερώτησης επιβεβαίωσης.")
    args = parser.parse_args()

    arg = args.uri or args.name
    matches = resolve_products(arg, by_name=bool(args.name))

    if not matches:
        print("Δεν βρέθηκε προϊόν που να ταιριάζει.")
        return

    print(f"Βρέθηκαν {len(matches)} προϊόν(τα):")
    for uri, name in matches:
        print(f"  • {name}\n    {uri}")

    if not args.yes:
        answer = input("\nΝα διαγραφούν ΟΡΙΣΤΙΚΑ; (γράψε 'ναι' για επιβεβαίωση): ").strip().lower()
        if answer not in ("ναι", "nai", "yes", "y"):
            print("Ακυρώθηκε.")
            return

    for uri, name in matches:
        delete_from_graphdb(uri)
        ttl_removed = delete_from_ttl(uri)
        wl, pop = delete_from_sqlite(uri)
        print(
            f"[OK] Διαγράφηκε «{name}» "
            f"(GraphDB: ok, TTL: {ttl_removed} triples, "
            f"SQLite: {wl} wishlist + {pop} popularity)"
        )

    print("\nΈτοιμο. Κάνε restart το backend για να ανανεωθούν προτάσεις/δημοτικότητα.")


if __name__ == "__main__":
    main()
