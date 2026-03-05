#!/bin/sh
# ─────────────────────────────────────────────────────────────────
# Enterprise Knowledge Brain — Docker Entrypoint
# Starts FastAPI (background) then Streamlit (foreground)
# ─────────────────────────────────────────────────────────────────

set -e

echo "🔧 Running first-time DB setup..."
python scripts/setup_db.py || echo "⚠️  DB already exists, skipping seed."

echo "🚀 Starting FastAPI on :8000..."
uvicorn src.api:app --host 0.0.0.0 --port 8000 --workers 1 &

echo "🎨 Starting Streamlit on :8501..."
exec streamlit run src/app.py \
  --server.port 8501 \
  --server.address 0.0.0.0 \
  --server.headless true \
  --server.fileWatcherType none

echo "⏳ Waiting for Ollama..."
until wget -qO- http://ollama:11434/api/tags > /dev/null 2>&1; do
  sleep 3
done
echo "✅ Ollama ready"