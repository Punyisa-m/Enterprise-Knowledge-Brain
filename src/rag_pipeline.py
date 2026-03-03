"""
src/rag_pipeline.py
-------------------
RAG Orchestrator – ties RBAC, vector retrieval, and LLM together.

Flow
----
1. Validate employee session via RBACDatabase
2. Build ChromaDB RBAC where-filter for the employee's role
3. Query the vector store with the semantic filter
4. Pass retrieved chunks + employee context to the LLM engine
5. Log the query to the audit trail
6. Return structured response with sources
"""

import logging
from dataclasses import dataclass, field
from typing import Generator, Optional

from src.database import RBACDatabase, get_db
from src.vector_store import EnterpriseVectorStore, get_vector_store
from src.llm_engine import OllamaLLMEngine, get_llm_engine

logger = logging.getLogger(__name__)

# ── Response model ─────────────────────────────────────────────────────────────

@dataclass
class RAGResponse:
    answer: str
    sources: list[dict] = field(default_factory=list)
    employee_id: str = ""
    query: str = ""
    total_chunks_retrieved: int = 0
    departments_accessed: list[str] = field(default_factory=list)
    access_granted: bool = True
    access_type: str = "granted"  # "granted" | "no_permission" | "no_results" | "denied"
    error: Optional[str] = None

    def format_sources(self) -> str:
        if not self.sources:
            return "_No sources found in your accessible documents._"
        lines = []
        for i, src in enumerate(self.sources, 1):
            meta = src.get("metadata", {})
            score = src.get("relevance_score", 0)
            lines.append(
                f"**[{i}] {meta.get('source', 'Unknown')}** "
                f"(Dept: {meta.get('department', '?')} | "
                f"Page: {meta.get('page', 'N/A')} | "
                f"Relevance: {score:.1%})"
            )
        return "\n".join(lines)


# ── Pipeline ───────────────────────────────────────────────────────────────────

class RAGPipeline:
    """
    Stateless orchestrator. Each call to `query()` is independent.
    """

    def __init__(
        self,
        db: Optional[RBACDatabase] = None,
        vector_store: Optional[EnterpriseVectorStore] = None,
        llm_engine: Optional[OllamaLLMEngine] = None,
        n_results: int = 5,
        min_relevance: float = 0.40,
    ):
        self.db = db or get_db()
        self.vs = vector_store or get_vector_store()
        self.llm = llm_engine or get_llm_engine()
        self.n_results = n_results
        self.min_relevance = min_relevance

    # ── RBAC guard ─────────────────────────────────────────────────────────────

    def _check_access(self, employee: dict) -> bool:
        return bool(employee) and employee.get("is_active", 0) == 1

    # ── Main query entry point ─────────────────────────────────────────────────

    def query(
        self,
        query_text: str,
        employee: dict,
        stream: bool = False,
    ) -> RAGResponse:
        """
        Full RAG pipeline with RBAC enforcement.
        When stream=True the answer field will contain a generator,
        not a string – handle accordingly in the UI.
        """
        # 1. Access gate
        if not self._check_access(employee):
            self.db.log_query(
                employee.get("employee_id", "unknown"),
                query_text,
                [],
                0,
                access_granted=False,
            )
            return RAGResponse(
                answer="⛔ Access Denied: Your account is not active or not found.",
                query=query_text,
                access_granted=False,
                access_type="denied",
                error="inactive_account",
            )

        # 2. Build RBAC filter
        chroma_filter = self.db.build_chroma_filter(employee)
        logger.debug("RBAC filter for %s: %s", employee["employee_id"], chroma_filter)

        # 3. Vector retrieval
        raw_hits = self.vs.query(
            query_text=query_text,
            chroma_filter=chroma_filter,
            n_results=self.n_results,
        )

        # 4. Apply minimum relevance threshold
        hits = [h for h in raw_hits if h["relevance_score"] >= self.min_relevance]
        departments_accessed = list({h["metadata"].get("department", "Unknown") for h in hits})

        # Detect "no permission" vs "no information"
        # If we got hits before threshold but all from unrelated depts → likely no permission
        accessible_depts = set(self.db.get_accessible_departments(employee["role"]))
        query_seems_restricted = (
            len(hits) == 0
            and len(raw_hits) > 0
            and all(h["relevance_score"] < self.min_relevance for h in raw_hits)
        )

        logger.info(
            "Employee %s | query='%s...' | raw=%d hits | filtered=%d hits",
            employee["employee_id"],
            query_text[:60],
            len(raw_hits),
            len(hits),
        )

        # 5. Generate answer
        if query_seems_restricted:
            # Don't call LLM at all — give a clear permission-denied message
            answer = (
                "🔒 **Access Restricted**\n\n"
                "The information you're looking for exists in the system but is outside "
                "your current access scope. Please contact your manager or the relevant "
                "department if you believe you need access to this information."
            )
            access_type = "no_permission"
            hits = []  # Don't leak any sources
        elif not hits:
            answer = (
                "ℹ️ **No Information Found**\n\n"
                "I could not find any relevant documents for your question within your "
                "accessible knowledge base. Please verify the topic or contact the "
                "relevant department directly."
            )
            access_type = "no_results"
            hits = []
        elif stream:
            answer = self.llm.generate_streaming(
                query=query_text,
                context_chunks=hits,
                employee=employee,
            )
            access_type = "granted"
        else:
            answer = self.llm.generate(
                query=query_text,
                context_chunks=hits,
                employee=employee,
            )
            access_type = "granted"

        # 6. Audit log
        self.db.log_query(
            employee_id=employee["employee_id"],
            query_text=query_text,
            departments_accessed=departments_accessed,
            result_count=len(hits),
            access_granted=True,
        )

        return RAGResponse(
            answer=answer,
            sources=hits,
            employee_id=employee["employee_id"],
            query=query_text,
            total_chunks_retrieved=len(hits),
            departments_accessed=departments_accessed,
            access_granted=True,
            access_type=access_type,
        )

    def query_streaming(
        self,
        query_text: str,
        employee: dict,
    ) -> tuple[Generator, RAGResponse]:
        """
        Returns (token_generator, metadata_response).
        The metadata_response.answer is empty – use the generator for that.
        """
        # Access gate
        if not self._check_access(employee):
            def _denied():
                yield "⛔ Access Denied: Your account is not active."
            return _denied(), RAGResponse(
                answer="", query=query_text, access_granted=False
            )

        chroma_filter = self.db.build_chroma_filter(employee)
        hits = self.vs.query(query_text, chroma_filter, n_results=self.n_results)
        hits = [h for h in hits if h["relevance_score"] >= self.min_relevance]
        departments_accessed = list({h["metadata"].get("department", "?") for h in hits})

        self.db.log_query(
            employee_id=employee["employee_id"],
            query_text=query_text,
            departments_accessed=departments_accessed,
            result_count=len(hits),
        )

        token_gen = self.llm.generate_streaming(
            query=query_text,
            context_chunks=hits,
            employee=employee,
        )

        metadata = RAGResponse(
            answer="",  # filled by streaming consumer
            sources=hits,
            employee_id=employee["employee_id"],
            query=query_text,
            total_chunks_retrieved=len(hits),
            departments_accessed=departments_accessed,
        )

        return token_gen, metadata

    # ── Document ingestion helper ──────────────────────────────────────────────

    def ingest_document(
        self,
        file_path,
        department: str,
        security_level: int,
        requesting_employee: Optional[dict] = None,
    ) -> dict:
        """
        Ingests a document. If requesting_employee is provided,
        verifies they have admin role before proceeding.
        """
        if requesting_employee and requesting_employee.get("role") != "admin":
            return {"success": False, "error": "Only admin employees can ingest documents."}

        from pathlib import Path
        try:
            count = self.vs.ingest_file(Path(file_path), department, security_level)
            return {"success": True, "chunks": count, "file": str(file_path)}
        except Exception as exc:
            logger.error("Ingestion failed: %s", exc)
            return {"success": False, "error": str(exc)}


# Singleton
_pipeline_instance: Optional[RAGPipeline] = None


def get_pipeline() -> RAGPipeline:
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = RAGPipeline()
    return _pipeline_instance