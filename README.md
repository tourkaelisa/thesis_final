# E-shop (Διπλωματική) — Οδηγίες εκτέλεσης με Docker

Όλη η εφαρμογή (Angular frontend + FastAPI backend + GraphDB triplestore)
σηκώνεται με **μία εντολή**. Χρειάζεται να εγκαταστήσετε μόνο το Docker.

## Προαπαιτούμενα

- **Docker Desktop** (Windows/Mac) ή Docker Engine + Compose (Linux)
  → https://www.docker.com/products/docker-desktop/

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

## Δοκιμαστικοί Λογαριασμοί (Demo Accounts)

Για την αξιολόγηση της εφαρμογής, έχουν προ-δημιουργηθεί λογαριασμοί με γεμάτα δεδομένα (wishlists) για να δείτε τα στατιστικά σε δράση.

**Λογαριασμός Διαχειριστή (Admin)**
Με αυτόν τον λογαριασμό έχετε πρόσβαση στο **Admin Dashboard** (στατιστικά σε πραγματικό χρόνο, εγκαταλελειμμένα προϊόντα, κλπ).
- **Email:** `elisatourka@gmail.com`
- **Password:** `elisa123`

**Απλός Λογαριασμός Χρήστη (User)**
Μπορείτε φυσικά να κάνετε μια νέα "Εγγραφή" από το UI, αλλά αν θέλετε να συνδεθείτε κατευθείαν ως ένας από τους 200 εικονικούς χρήστες που έχουν ήδη προϊόντα στα αγαπημένα τους, χρησιμοποιήστε:
- **Email:** `user_0_3905@example.com`
- **Password:** `password123`
