# Dockerfile
FROM python:3.14-slim

WORKDIR /app

# Outil de santé pour le HEALTHCHECK
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Dépendances d'abord (cache Docker)
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Puis le code
COPY . .

RUN chmod +x /app/docker-entrypoint.sh /app/docker-ingest.sh

# Variables d'env (surchargeables)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PDF_CORPUS_PATHS=/app/data

EXPOSE 8000

# Vérification santé automatique
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD curl -fsS http://localhost:8000/health \
    || exit 1

# Entrypoint de préparation
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Démarrage
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
