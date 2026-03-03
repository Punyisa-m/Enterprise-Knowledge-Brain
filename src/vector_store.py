"""
src/vector_store.py
-------------------
ChromaDB vector store with local sentence-transformer embeddings.

Key design decisions
--------------------
* Uses `lazy_load` on all LangChain loaders so individual pages / rows
  are yielded one-at-a-time — prevents MemoryError on large files.
* Metadata schema enforced: every chunk carries `department`,
  `security_level`, `source`, `file_type`, and `chunk_index`.
* Embedding model runs fully locally via sentence-transformers.
"""

import logging
import gc
from pathlib import Path
from typing import Generator, Optional

import chromadb
from chromadb.config import Settings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = _ROOT / "database" / "chroma"
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

COLLECTION_NAME = "enterprise_knowledge"

# ── Embedding model (local, no API key) ───────────────────────────────────────
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"   # 22 MB – fast & accurate enough for enterprise RAG


class LocalEmbeddingFunction(chromadb.EmbeddingFunction):
    """
    Thin wrapper so ChromaDB can call our sentence-transformer directly.
    """

    def __init__(self, model_name: str = EMBED_MODEL_NAME):
        self._model = SentenceTransformer(model_name)

    def __call__(self, input: list[str]) -> list[list[float]]:  # type: ignore[override]
        return self._model.encode(input, show_progress_bar=False).tolist()


# ── Splitter ───────────────────────────────────────────────────────────────────
_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=120,
    length_function=len,
    separators=["\n\n", "\n", ". ", " ", ""],
)


# ── Universal Ingestor ─────────────────────────────────────────────────────────

class UniversalIngestor:
    """
    Loads PDF / DOCX / TXT / XLSX / MD files using LangChain loaders.
    Uses lazy_load() to stream pages one-at-a-time and avoid MemoryErrors.
    """

    def _loader_for(self, path: Path):
        ext = path.suffix.lower()
        if ext == ".pdf":
            from langchain_community.document_loaders import PyPDFLoader
            return PyPDFLoader(str(path))
        elif ext == ".docx":
            from langchain_community.document_loaders import Docx2txtLoader
            return Docx2txtLoader(str(path))
        elif ext in (".txt", ".md"):
            from langchain_community.document_loaders import TextLoader
            return TextLoader(str(path), encoding="utf-8")
        elif ext in (".xlsx", ".xls"):
            from langchain_community.document_loaders import UnstructuredExcelLoader
            return UnstructuredExcelLoader(str(path), mode="elements")
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    def lazy_chunks(
        self,
        path: Path,
        department: str,
        security_level: int,
    ) -> Generator[dict, None, None]:
        """
        Yields individual chunk dicts: {text, metadata}
        Streams pages to keep memory footprint minimal.
        """
        loader = self._loader_for(path)
        chunk_index = 0

        for doc in loader.lazy_load():          # ← lazy, not load()
            splits = _SPLITTER.split_text(doc.page_content)
            for split in splits:
                if not split.strip():
                    continue
                yield {
                    "text": split,
                    "metadata": {
                        "source": path.name,
                        "file_path": str(path),
                        "file_type": path.suffix.lower().lstrip("."),
                        "department": department,
                        "security_level": security_level,
                        "chunk_index": chunk_index,
                        # Carry page number if the loader provides it
                        "page": doc.metadata.get("page", 0),
                    },
                }
                chunk_index += 1

            # Encourage GC between pages for large PDFs
            del splits
            gc.collect()


# ── Vector Store wrapper ───────────────────────────────────────────────────────

class EnterpriseVectorStore:
    """
    Persistent ChromaDB collection with RBAC-aware querying.
    """

    def __init__(self):
        self._embedding_fn = LocalEmbeddingFunction()
        self._client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        self._ingestor = UniversalIngestor()
        logger.info(
            "VectorStore ready. Collection '%s' has %d documents.",
            COLLECTION_NAME,
            self._collection.count(),
        )

    # ── Ingestion ──────────────────────────────────────────────────────────────

    def ingest_file(
        self,
        path: Path,
        department: str,
        security_level: int,
        batch_size: int = 50,
    ) -> int:
        """
        Ingests a single file into the collection.
        Returns number of chunks added.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # Remove stale chunks for this file to allow re-ingestion
        try:
            self._collection.delete(where={"source": {"$eq": path.name}})
        except Exception:
            pass

        texts, metadatas, ids = [], [], []
        total = 0

        for chunk in self._ingestor.lazy_chunks(path, department, security_level):
            chunk_id = f"{path.stem}__{department}__chunk{chunk['metadata']['chunk_index']}"
            texts.append(chunk["text"])
            metadatas.append(chunk["metadata"])
            ids.append(chunk_id)

            if len(texts) >= batch_size:
                self._collection.upsert(documents=texts, metadatas=metadatas, ids=ids)
                total += len(texts)
                texts, metadatas, ids = [], [], []
                gc.collect()

        if texts:
            self._collection.upsert(documents=texts, metadatas=metadatas, ids=ids)
            total += len(texts)

        logger.info("Ingested '%s' → %d chunks (dept=%s, sec=%d)", path.name, total, department, security_level)
        return total

    def ingest_directory(
        self,
        directory: Path,
        department: str,
        security_level: int,
    ) -> dict[str, int]:
        """
        Recursively ingest all supported files in a directory.
        Returns {filename: chunk_count}.
        """
        supported = {".pdf", ".docx", ".txt", ".xlsx", ".md"}
        results = {}
        for fp in Path(directory).rglob("*"):
            if fp.suffix.lower() in supported:
                try:
                    results[fp.name] = self.ingest_file(fp, department, security_level)
                except Exception as exc:
                    logger.error("Failed to ingest '%s': %s", fp.name, exc)
        return results

    # ── Retrieval ──────────────────────────────────────────────────────────────

    def query(
        self,
        query_text: str,
        chroma_filter: dict,
        n_results: int = 5,
    ) -> list[dict]:
        """
        Semantic search with RBAC where-filter.
        Returns list of result dicts with text, metadata, and distance.
        """
        try:
            results = self._collection.query(
                query_texts=[query_text],
                n_results=min(n_results, max(self._collection.count(), 1)),
                where=chroma_filter,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.error("ChromaDB query failed: %s", exc)
            return []

        hits = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, dists):
            hits.append(
                {
                    "text": doc,
                    "metadata": meta,
                    "distance": dist,
                    "relevance_score": round(1 - dist, 4),   # cosine → similarity
                }
            )

        # Sort by relevance descending
        hits.sort(key=lambda x: x["relevance_score"], reverse=True)
        return hits

    def get_collection_stats(self) -> dict:
        total = self._collection.count()
        # Sample a handful to get department breakdown
        if total == 0:
            return {"total_chunks": 0, "departments": {}}
        sample = self._collection.get(limit=total, include=["metadatas"])
        dept_counts: dict[str, int] = {}
        for m in sample["metadatas"]:
            dept = m.get("department", "Unknown")
            dept_counts[dept] = dept_counts.get(dept, 0) + 1
        return {"total_chunks": total, "departments": dept_counts}


# Singleton
_vs_instance: Optional[EnterpriseVectorStore] = None


def get_vector_store() -> EnterpriseVectorStore:
    global _vs_instance
    if _vs_instance is None:
        _vs_instance = EnterpriseVectorStore()
    return _vs_instance
