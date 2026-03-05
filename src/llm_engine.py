"""
src/llm_engine.py
-----------------
Local LLM connector via Ollama (Llama 3.1).

Design principles
-----------------
* System prompt enforces strict context adherence – the model MUST NOT
  answer from training knowledge if the retrieved context doesn't cover it.
* RBAC boundary reminder is injected per-request so the model
  acknowledges the user's clearance level.
* Streaming support for real-time UI updates.
"""

import logging
from typing import Generator, Optional

import ollama

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama3.2"

# ── System prompt template ─────────────────────────────────────────────────────
_SYSTEM_PROMPT_TEMPLATE = """You are the Enterprise Knowledge Brain, a secure internal AI assistant.

## Your Role
You help employees retrieve accurate information from company documents.
You ONLY answer based on the RETRIEVED CONTEXT provided below each question.

## Strict Rules
1. CONTEXT ADHERENCE: If the answer is not explicitly present in the provided context,
   respond with: "I don't have sufficient information in my accessible documents to answer
   this question. Please contact the relevant department directly."

2. RBAC COMPLIANCE: You are responding to an employee with the following access profile:
   - Name: {employee_name}
   - Role: {employee_role}
   - Department: {employee_department}
   - Security Clearance Level: {security_level}/4
   Never reveal, summarize, or hint at information from documents outside this employee's
   clearance scope. If asked about restricted topics, politely decline.

3. CITATIONS: Always end your answer with a "Sources" section listing the document
   names and page numbers from the context you used.

4. ACCURACY: Do not paraphrase or interpret beyond what the documents state.
   Use direct quotes where helpful, surrounded by quotation marks.

5. CONFIDENTIALITY: Never disclose that other documents or higher-clearance information
   exists unless the user already has access to it.

## Response Format
- Use clear, professional language appropriate for a corporate environment.
- Structure long answers with bullet points or numbered lists.
- Keep answers concise unless detail is explicitly requested.
"""

# ── Prompt builder ─────────────────────────────────────────────────────────────

def build_system_prompt(employee: dict) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(
        employee_name=employee.get("full_name", "Employee"),
        employee_role=employee.get("role", "employee").title(),
        employee_department=employee.get("department", "General"),
        security_level=employee.get("security_level", 1),
    )


def build_rag_prompt(query: str, context_chunks: list[dict]) -> str:
    """
    Assembles the user-turn message that includes retrieved context.
    """
    if not context_chunks:
        context_block = "No relevant documents were found in your accessible knowledge base."
    else:
        parts = []
        for i, chunk in enumerate(context_chunks, 1):
            meta = chunk.get("metadata", {})
            score = chunk.get("relevance_score", 0)
            parts.append(
                f"[Document {i}]\n"
                f"Source: {meta.get('source', 'Unknown')}\n"
                f"Department: {meta.get('department', 'Unknown')}\n"
                f"Page: {meta.get('page', 'N/A')}\n"
                f"Relevance Score: {score:.2%}\n"
                f"Content:\n{chunk['text']}\n"
            )
        context_block = "\n---\n".join(parts)

    return (
        f"RETRIEVED CONTEXT:\n"
        f"{'=' * 60}\n"
        f"{context_block}\n"
        f"{'=' * 60}\n\n"
        f"EMPLOYEE QUESTION:\n{query}\n\n"
        f"Remember: Answer ONLY from the retrieved context above."
    )


# ── LLM Engine ─────────────────────────────────────────────────────────────────

class OllamaLLMEngine:
    """
    Wrapper around the Ollama Python client.
    Handles both streaming and non-streaming generation.
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self._verify_connection()

    def _verify_connection(self):
            try:
                models_response = ollama.list()
                # ปรับการดึงชื่อโมเดลให้รองรับ Ollama เวอร์ชันใหม่ (Object-based)
                model_names = []
                
                # ตรวจสอบว่าผลลัพธ์เป็น Object หรือ Dictionary
                if hasattr(models_response, 'models'):
                    model_names = [m.model for m in models_response.models]
                elif isinstance(models_response, dict):
                    model_names = [m.get('name', m.get('model')) for m in models_response.get('models', [])]

                if self.model not in model_names and not any(self.model in name for name in model_names):
                    logger.warning(
                        "Model '%s' not found locally. Available: %s. "
                        "Run: ollama pull %s",
                        self.model,
                        model_names,
                        self.model,
                    )
                else:
                    logger.info("Ollama connected. Model '%s' is available.", self.model)
            except Exception as exc:
                # แก้ไขตรงนี้เพื่อไม่ให้ระบบค้างถ้าแค่หาชื่อโมเดลไม่เจอ
                logger.error("Ollama connection check failed: %s", exc)

    def generate(
        self,
        query: str,
        context_chunks: list[dict],
        employee: dict,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> str:
        """
        Synchronous generation. Returns full response string.
        """
        system_prompt = build_system_prompt(employee)
        user_message = build_rag_prompt(query, context_chunks)

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                    "top_p": 0.9,
                },
            )
            return response["message"]["content"]
        except Exception as exc:
            logger.error("Ollama generation failed: %s", exc)
            return (
                f"⚠️ LLM Error: Could not generate a response. "
                f"Please ensure Ollama is running with `{self.model}` loaded.\n"
                f"Details: {exc}"
            )

    def generate_streaming(
        self,
        query: str,
        context_chunks: list[dict],
        employee: dict,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> Generator[str, None, None]:
        """
        Streaming generation – yields token-by-token for Streamlit.
        """
        system_prompt = build_system_prompt(employee)
        user_message = build_rag_prompt(query, context_chunks)

        try:
            stream = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                stream=True,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            )
            for chunk in stream:
                token = chunk["message"]["content"]
                if token:
                    yield token
        except Exception as exc:
            logger.error("Ollama streaming failed: %s", exc)
            yield (
                f"⚠️ LLM Error: {exc}. "
                f"Please run `ollama serve` and `ollama pull {self.model}`."
            )


# Singleton
_engine_instance: Optional[OllamaLLMEngine] = None


def get_llm_engine(model: str = DEFAULT_MODEL) -> OllamaLLMEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = OllamaLLMEngine(model=model)
    return _engine_instance
