# ═══════════════════════════════════════════════════════════════════════════════
#  AuthForte — Dockerfile (backend Flask + Python 3.13)
#  COMMUN Windows + Linux
# ═══════════════════════════════════════════════════════════════════════════════

FROM python:3.13-slim

LABEL maintainer="AuthForte — 3iL Ingénieurs"
LABEL description="Plateforme d'authentification forte MFA"

# ── Dépendances système ────────────────────────────────────────────────────────
# pcscd / libpcsclite : nécessaires pour pyscard (NFC)
# libpcsclite-dev : headers pour compiler pyscard
# gcc / libffi-dev : pour cffi / cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libc6-dev \
        swig \
        libffi-dev \
        libpcsclite-dev \
        pcscd \
        libusb-1.0-0 \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Répertoire de travail ─────────────────────────────────────────────────────
WORKDIR /app

# ── Dépendances Python (couche cacheable) ─────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Code applicatif ───────────────────────────────────────────────────────────
COPY . .
#COPY Backend/   ./Backend/
#COPY Frontend/  ./Frontend/
#COPY static/    ./static/

# ── Healthcheck ───────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# ── Port exposé ───────────────────────────────────────────────────────────────
EXPOSE 5000

# ── Démarrage ─────────────────────────────────────────────────────────────────
# Développement : Flask intégré
# Production : remplacez par gunicorn (voir commentaire)
CMD ["python", "Backend/app.py"]

# CMD pour la production :
# CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "Backend.app:app"]
