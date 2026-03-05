# ─────────────────────────────────────────────────────────────────
# Enterprise Knowledge Brain — Dockerfile
# Base: python:3.11-slim  (~130 MB vs ~1 GB for full python image)
# ─────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ── System deps ───────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libmagic1 \
        poppler-utils \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps (layer cache — only rebuilds if requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Source code ───────────────────────────────────────────────────
COPY src/                    ./src/
COPY scripts/                ./scripts/
COPY docker-entrypoint.sh    .

# ── Runtime dirs (documents + database mounted via docker-compose volume)
RUN mkdir -p database logs documents/hr documents/it documents/finance documents/general \
    && chmod +x docker-entrypoint.sh

# ── Ports: 8000 = FastAPI | 8501 = Streamlit ──────────────────────
EXPOSE 8000 8501

ENTRYPOINT ["./docker-entrypoint.sh"]