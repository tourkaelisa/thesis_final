#!/bin/sh
# Στήνει αυτόματα τη GraphDB ώστε ο καθηγητής να τρέχει μόνο "docker compose up":
#   1. περιμένει να σηκωθεί η GraphDB
#   2. φτιάχνει το repository "eshop_thesis" (αν δεν υπάρχει ήδη)
#   3. κάνει import το .ttl (μόνο αν το repo είναι άδειο)
# Είναι idempotent: αν τα δεδομένα υπάρχουν ήδη (volume), δεν ξανακάνει τίποτα.

GRAPHDB="http://graphdb:7200"
REPO="eshop_thesis"
TTL="/data/master_eshop_enriched.ttl"

echo "[init] Αναμονή να σηκωθεί η GraphDB..."
until curl -sf "$GRAPHDB/rest/repositories" >/dev/null 2>&1; do
  sleep 3
done
echo "[init] Η GraphDB είναι έτοιμη."

# 1) Δημιουργία repository αν λείπει.
if curl -sf "$GRAPHDB/repositories/$REPO/size" >/dev/null 2>&1; then
  echo "[init] Το repository '$REPO' υπάρχει ήδη."
else
  echo "[init] Δημιουργία repository '$REPO'..."
  # type=text/turtle: ρητά, ώστε η GraphDB να παρσάρει το config ως Turtle.
  HTTP=$(curl -s -o /tmp/create_resp.txt -w "%{http_code}" -X POST \
    "$GRAPHDB/rest/repositories" \
    -F "config=@/repo-config.ttl;type=text/turtle")
  echo "[init] HTTP $HTTP — απάντηση server:"
  cat /tmp/create_resp.txt
  echo ""
  echo "[init] (τέλος απάντησης)"
fi

# 2) Import δεδομένων μόνο αν το repo είναι άδειο.
SIZE=$(curl -sf "$GRAPHDB/repositories/$REPO/size" 2>/dev/null)
case "$SIZE" in
  ''|*[!0-9]*) SIZE=0 ;;
esac

if [ "$SIZE" -gt 0 ]; then
  echo "[init] Το repository έχει ήδη $SIZE triples — παράλειψη import."
else
  echo "[init] Import του $TTL ..."
  curl -s -X POST -H "Content-Type: text/turtle" \
    --data-binary "@$TTL" "$GRAPHDB/repositories/$REPO/statements"
  echo "[init] Ολοκληρώθηκε το import."
fi

echo "[init] Έτοιμο."
