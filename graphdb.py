"""Πρόσβαση στο GraphDB triplestore μέσω του SPARQL endpoint."""
import requests

from config import GRAPHDB_ENDPOINT


def query_graphdb(sparql_query: str) -> list:
    """Εκτελεί ένα SPARQL ερώτημα στο GraphDB και επιστρέφει τα bindings."""
    response = requests.post(
        GRAPHDB_ENDPOINT,
        data={"query": sparql_query},
        headers={
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("results", {}).get("bindings", [])


def bval(binding: dict, key: str, default=None):
    """Επιστρέφει την τιμή ενός SPARQL binding του GraphDB (ή default αν λείπει)."""
    item = binding.get(key)
    return item.get("value", default) if item else default
