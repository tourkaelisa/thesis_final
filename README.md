# E-shop (Διπλωματική) — Οδηγίες εκτέλεσης με Docker

Όλη η εφαρμογή (Angular frontend + FastAPI backend + GraphDB triplestore)
σηκώνεται με **μία εντολή**. Δεν χρειάζεται να εγκαταστήσετε Python, Node ή
GraphDB — μόνο το Docker.

## Προαπαιτούμενα

- **Docker Desktop** (Windows/Mac) ή Docker Engine + Compose (Linux)
  → https://www.docker.com/products/docker-desktop/

Τίποτα άλλο.

## Εκτέλεση

Από τον φάκελο του project:

```bash
docker compose up --build
```

Αυτό σηκώνει αυτόματα:

| Service   | Τι είναι                    | Διεύθυνση                |
|-----------|-----------------------------|--------------------------|
| frontend  | Angular (UI)                | http://localhost:4200    |
| backend   | FastAPI (REST + WebSocket)  | http://localhost:8000    |
| graphdb   | GraphDB triplestore         | http://localhost:7200    |

> **Πρώτη φορά:** αργεί λίγο (κατεβαίνουν τα Docker images, χτίζεται το project,
> στήνεται η βάση). Οι επόμενες εκτελέσεις είναι πολύ γρήγορες.

Η βάση (το repository `eshop_thesis` και τα δεδομένα RDF) **στήνεται μόνη της**
την πρώτη φορά — δεν χρειάζεται κανένα χειροκίνητο βήμα.

## Άνοιγμα της εφαρμογής

Μόλις δείτε στα logs ότι το frontend είναι έτοιμο, ανοίξτε:

**http://localhost:4200**

## Τερματισμός

```bash
docker compose down
```

Τα δεδομένα της GraphDB διατηρούνται (Docker volume). Για να σβηστούν εντελώς
και να ξαναστηθεί η βάση από την αρχή:

```bash
docker compose down -v
```

## Έλεγχος ότι όλα δουλεύουν

- **UI:** στο http://localhost:4200, οι κατηγορίες εμφανίζουν προϊόντα.
- **Backend API:** http://localhost:8000/docs (Swagger της FastAPI).
- **GraphDB:** http://localhost:7200 (Workbench· repository: `eshop_thesis`).
- **Στήσιμο βάσης:** `docker compose logs graphdb-init`
  → πρέπει να δείχνει `Ολοκληρώθηκε το import.` ή `υπάρχει ήδη`.

## Δομή

```
.                      Python backend (FastAPI) + Dockerfile
├── fronted/           Angular frontend + Dockerfile (dev) + proxy.conf.json
├── data/              Δεδομένα RDF (.ttl) που φορτώνονται στη GraphDB
├── graphdb/           Αυτόματο στήσιμο GraphDB (repo-config.ttl + init.sh)
└── docker-compose.yml Ορχήστρωση όλων των services
```

## Σημειώσεις (για ανάπτυξη)

- Το frontend τρέχει σε **development mode** με hot reload: αλλαγές στον κώδικα
  του UI φαίνονται αυτόματα, χωρίς rebuild.
- Το backend τρέχει με `--reload`: αλλαγές σε Python φαίνονται αυτόματα.
- Αν προστεθεί **νέα εξάρτηση** (`requirements.txt` ή `package.json`), τρέξτε
  ξανά με `docker compose up --build`.
- Ρυθμίσεις (προαιρετικά): αντιγράψτε `.env.example` σε `.env` για να αλλάξετε
  `JWT_SECRET` / `ADMIN_EMAIL`. Χωρίς `.env` χρησιμοποιούνται dev defaults.
