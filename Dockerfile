# Backend: FastAPI (main:app) σερβίρεται μέσω uvicorn στο port 8000.
FROM python:3.12-slim

# Καθαρότερα logs + κανένα .pyc στο image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Πρώτα μόνο το requirements.txt ώστε το pip layer να μπαίνει στο cache
# και να μην ξαναγίνεται install σε κάθε αλλαγή κώδικα.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ο υπόλοιπος κώδικας (το .dockerignore κρατάει έξω venv/__pycache__/fronted κ.λπ.)
COPY . .

EXPOSE 8000

# Η εντολή εκκίνησης που προκύπτει από το main.py (app = FastAPI()).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
