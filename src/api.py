"""
src/api.py  — FastAPI AI Backend
----------------------------------
Endpoints
---------
GET  /health          — system health check
POST /query           — non-streaming RAG query
POST /query/stream    — Server-Sent Events streaming RAG query
POST /ingest          — upload + ingest a document (admin only)
GET  /stats           — vector store + DB stats
DELETE /document/{name} — remove a document from the vector store
"""

from __future__ import annotations

import gc
import json
import time
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.database import get_db
from src.rag_pipeline import RAGPipeline, get_pipeline
from src.vector_store import get_vector_store

# ── Logging setup ──────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
logger.add(
    _ROOT / "logs" / "api.log",
    rotation="10 MB",
    retention="7 days",
    compression="gz",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
)

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Enterprise Knowledge Brain API",
    version="2.0.0",
    description="Local RAG API with RBAC — runs fully on-premise",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Streamlit UI same-machine origin
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Pydantic schemas ───────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    employee_id: str

class QueryResponse(BaseModel):
    answer: str
    sources: list[dict]
    access_type: str
    departments_accessed: list[str]
    total_chunks: int
    latency_ms: float

class HealthResponse(BaseModel):
    status: str
    db_employees: int
    db_permissions: int
    vector_chunks: int
    ollama_ok: bool
    uptime_s: float

_START_TIME = time.time()


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health():
    """
    Lightweight health check — Streamlit sidebar calls this on load.
    Checks DB, ChromaDB, and Ollama reachability without heavy ops.
    """
    db    = get_db()
    stats = db.get_stats()
    vs    = get_vector_store()
    vs_stats = vs.get_collection_stats()

    # Test Ollama connectivity (cheap — just list models)
    ollama_ok = False
    try:
        import ollama as _ollama
        _ollama.list()
        ollama_ok = True
    except Exception:
        pass

    return HealthResponse(
        status="ok" if ollama_ok else "degraded",
        db_employees=stats["employees"],
        db_permissions=stats["permissions"],
        vector_chunks=vs_stats["total_chunks"],
        ollama_ok=ollama_ok,
        uptime_s=round(time.time() - _START_TIME, 1),
    )


# ── Non-streaming query ────────────────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse, tags=["RAG"])
def query(req: QueryRequest):
    t0 = time.time()
    db = get_db()

    employee = db.get_employee(req.employee_id)
    if not employee or not employee.get("is_active"):
        raise HTTPException(status_code=403, detail="Employee not found or inactive.")

    pipeline = get_pipeline()
    result   = pipeline.query(req.query, employee, stream=False)

    latency  = round((time.time() - t0) * 1000, 1)
    logger.info(
        "QUERY | emp={} | access_type={} | chunks={} | latency={}ms | q={}",
        req.employee_id, result.access_type, result.total_chunks_retrieved,
        latency, req.query[:80],
    )

    return QueryResponse(
        answer=result.answer,
        sources=result.sources,
        access_type=result.access_type,
        departments_accessed=result.departments_accessed,
        total_chunks=result.total_chunks_retrieved,
        latency_ms=latency,
    )


# ── Streaming query (SSE) ──────────────────────────────────────────────────────

@app.post("/query/stream", tags=["RAG"])
async def query_stream(req: QueryRequest):
    """
    Server-Sent Events endpoint.
    Yields events:
      data: {"token": "word"}          ← LLM tokens
      data: {"sources": [...]}         ← final metadata
      data: {"done": true}             ← end of stream
    """
    db       = get_db()
    employee = db.get_employee(req.employee_id)

    if not employee or not employee.get("is_active"):
        raise HTTPException(status_code=403, detail="Forbidden")

    pipeline = get_pipeline()

    async def event_generator():
        try:
            chroma_filter = db.build_chroma_filter(employee)
            vs   = get_vector_store()
            hits = vs.query(req.query, chroma_filter, n_results=5)
            hits = [h for h in hits if h["relevance_score"] >= 0.40]

            # Permission / no-result fast paths
            if not hits:
                msg = (
                    "🔒 Access Restricted — information exists but is outside your clearance."
                    if vs.query(req.query, {"department": {"$in": ["HR","IT","Finance","General"]}}, 3)
                    else "ℹ️ No relevant information found in your accessible documents."
                )
                yield {"data": json.dumps({"token": msg})}
                yield {"data": json.dumps({"done": True, "sources": []})}
                return

            # Stream tokens from Ollama
            from src.llm_engine import get_llm_engine
            engine = get_llm_engine()
            for token in engine.generate_streaming(req.query, hits, employee):
                yield {"data": json.dumps({"token": token})}
                gc.collect()   # nudge GC between tokens on 8 GB machines

            # Send sources as final event
            yield {"data": json.dumps({"sources": hits, "done": True})}

            # Audit log
            depts = list({h["metadata"].get("department","?") for h in hits})
            db.log_query(employee["employee_id"], req.query, depts, len(hits))

        except GeneratorExit:
            pass
        except Exception as exc:
            logger.error("Stream error: {}", exc)
            yield {"data": json.dumps({"token": f"\n\n⚠️ Error: {exc}", "done": True})}

    return EventSourceResponse(event_generator())


# ── Document ingestion ─────────────────────────────────────────────────────────

@app.post("/ingest", tags=["Admin"])
async def ingest_document(
    file:           UploadFile = File(...),
    department:     str        = Form(...),
    security_level: int        = Form(...),
    employee_id:    str        = Form(...),
):
    """Admin-only: upload and ingest a document into ChromaDB."""
    db       = get_db()
    employee = db.get_employee(employee_id)

    if not employee or employee.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required.")

    doc_dir = Path(__file__).resolve().parent.parent / "documents"
    doc_dir.mkdir(exist_ok=True)
    dest = doc_dir / file.filename

    content = await file.read()
    dest.write_bytes(content)

    try:
        vs    = get_vector_store()
        count = vs.ingest_file(dest, department, security_level)
        logger.info("Ingested '{}' → {} chunks (dept={}, sec={})",
                    file.filename, count, department, security_level)
        return {"success": True, "file": file.filename, "chunks": count}
    except Exception as exc:
        logger.error("Ingest failed for '{}': {}", file.filename, exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Delete document ────────────────────────────────────────────────────────────

@app.delete("/document/{filename}", tags=["Admin"])
def delete_document(filename: str, employee_id: str):
    db       = get_db()
    employee = db.get_employee(employee_id)
    if not employee or employee.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required.")

    vs = get_vector_store()
    try:
        vs._collection.delete(where={"source": {"$eq": filename}})
        logger.warning("Deleted document '{}' from vector store by {}", filename, employee_id)
        return {"success": True, "deleted": filename}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Stats ──────────────────────────────────────────────────────────────────────

@app.get("/stats", tags=["System"])
def stats():
    db    = get_db()
    vs    = get_vector_store()
    return {
        "database": db.get_stats(),
        "vector_store": vs.get_collection_stats(),
    }


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1,          # Keep 1 worker to avoid duplicating the embedding model in RAM
    )