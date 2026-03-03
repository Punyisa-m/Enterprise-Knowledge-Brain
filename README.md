# 🧠 Enterprise Knowledge Brain

A production-ready, fully **local** RAG (Retrieval-Augmented Generation) system with **Role-Based Access Control (RBAC)**. Zero cloud dependencies — your data never leaves your machine.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Streamlit UI  (src/app.py)                      │
│   ┌─────────────┐  ┌────────────────────┐  ┌──────────────────────┐    │
│   │ Employee    │  │  Chat Interface    │  │  Source Citations    │    │
│   │ Login+Badge │  │  (streaming)       │  │  + Relevance Scores  │    │
│   └──────┬──────┘  └─────────┬──────────┘  └──────────────────────┘    │
└──────────┼───────────────────┼─────────────────────────────────────────┘
           │                   │
           ▼                   ▼
┌──────────────────────────────────────────────────────────┐
│                  RAG Pipeline  (src/rag_pipeline.py)      │
│   1. RBAC check → 2. Build ChromaDB filter               │
│   3. Vector retrieval → 4. LLM generation                │
│   5. Audit logging                                        │
└──────┬───────────────────┬──────────────────┬────────────┘
       │                   │                  │
       ▼                   ▼                  ▼
┌──────────────┐  ┌────────────────┐  ┌──────────────────┐
│  SQLite RBAC │  │ ChromaDB +     │  │  Ollama          │
│  (database/) │  │ SentenceXfmr   │  │  Llama 3.1       │
│              │  │ (database/     │  │  (local LLM)     │
│  employees   │  │  chroma/)      │  │                  │
│  permissions │  │                │  │  System prompt   │
│  audit_log   │  │  RBAC where-   │  │  enforces RBAC   │
│              │  │  filter        │  │  + context-only  │
└──────────────┘  └────────────────┘  └──────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai) installed and running

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Pull the LLM
```bash
ollama pull llama3.1
```

### 3. Generate sample documents
```bash
python scripts/create_sample_docs.py
```

### 4. Launch the app
```bash
streamlit run src/app.py
```

### 5. Ingest documents
In the sidebar (logged in as Alice Johnson / admin):
- Expand **"Bulk Ingest Sample Docs"**
- Click **"Ingest All Documents in /documents"**

### 6. Start chatting!
Select any employee and ask questions.

---

## RBAC Model

### Security Levels
| Level | Label        | Description                           |
|-------|--------------|---------------------------------------|
| 1     | Public       | Company-wide, all employees           |
| 2     | Internal     | Role-specific internal documents      |
| 3     | Confidential | Manager-level and above               |
| 4     | Restricted   | Admin/executive access only           |

### Roles & Access
| Role     | Own Dept Max Level | Other Dept Max Level |
|----------|--------------------|----------------------|
| admin    | 4 (all depts)      | 4 (all depts)        |
| manager  | 3                  | 2 (General only)     |
| analyst  | 2                  | 1 (General only)     |
| employee | 1                  | 1 (General only)     |

### Demo Employees
| ID     | Name          | Role     | Dept    | Password    |
|--------|---------------|----------|---------|-------------|
| EMP001 | Alice Johnson | admin    | IT      | admin123    |
| EMP002 | Bob Martinez  | manager  | HR      | hr_mgr      |
| EMP003 | Carol White   | manager  | Finance | fin_mgr     |
| EMP004 | David Kim     | analyst  | IT      | it_analyst  |
| EMP005 | Eva Brown     | analyst  | Finance | fin_analyst |
| EMP006 | Frank Lee     | employee | HR      | hr_emp      |
| EMP007 | Grace Chen    | employee | General | gen_emp     |
| EMP008 | Henry Wilson  | manager  | IT      | it_mgr      |

> **UI Demo Mode:** The Streamlit app uses a dropdown (no password) for quick testing. For production, replace with the `db.authenticate()` method.

---

## Project Structure

```
enterprise-knowledge-brain/
├── src/
│   ├── __init__.py
│   ├── app.py              # Streamlit UI
│   ├── database.py         # SQLite RBAC engine
│   ├── vector_store.py     # ChromaDB + embeddings + Universal Ingestor
│   ├── llm_engine.py       # Ollama/Llama 3.1 connector
│   └── rag_pipeline.py     # Orchestrator
├── scripts/
│   └── create_sample_docs.py  # Sample document generator
├── documents/
│   ├── hr/                 # HR department docs
│   ├── it/                 # IT department docs
│   ├── finance/            # Finance department docs
│   └── general/            # Company-wide docs
├── database/
│   ├── rbac.db             # SQLite (auto-created)
│   └── chroma/             # ChromaDB vectors (auto-created)
└── requirements.txt
```

---

## Sample Documents

| File | Department | Security Level | Format |
|------|-----------|----------------|--------|
| vacation_policy.txt | HR | 2 (Internal) | TXT |
| employee_benefits_2026.docx | HR | 2 (Internal) | DOCX |
| server_security_protocols.pdf | IT | 3 (Confidential) | PDF |
| wifi_access_guide.txt | IT | 1 (Public) | TXT |
| q1_budget_allocation.xlsx | Finance | 3 (Confidential) | XLSX |
| expense_reimbursement_rules.pdf | Finance | 2 (Internal) | PDF |
| company_history_and_mission.md | General | 1 (Public) | MD |

---

## Key Design Decisions

### Memory-Safe Ingestion
All document loaders use `lazy_load()` which yields one page/element at a time, preventing `MemoryError` on large files. Chunks are upserted to ChromaDB in configurable batches (default: 50).

### RBAC Enforcement
The ChromaDB `where` filter is built from the employee's role and permissions table — never from user input. The filter uses `$or` conditions covering every (department × security_level) combination the employee is entitled to see.

### Context-Only LLM
The system prompt instructs Llama 3.1 to answer **only** from retrieved context. If no context covers the question, it returns a polite "I don't have sufficient information" response rather than hallucinating from training data.

### Audit Trail
Every query (including denied ones) is written to the `audit_log` SQLite table with: employee ID, query text, departments accessed, result count, and timestamp.

---

## Configuration

Edit constants at the top of each module:

| Module | Constant | Default | Description |
|--------|----------|---------|-------------|
| `vector_store.py` | `EMBED_MODEL_NAME` | `all-MiniLM-L6-v2` | Local embedding model |
| `llm_engine.py` | `DEFAULT_MODEL` | `llama3.1` | Ollama model name |
| `rag_pipeline.py` | `n_results` | `5` | Chunks retrieved per query |
| `rag_pipeline.py` | `min_relevance` | `0.30` | Minimum cosine similarity |

---

## Production Hardening Checklist

- [ ] Replace dropdown login with proper password authentication using `db.authenticate()`
- [ ] Add HTTPS (reverse proxy: nginx + certbot)
- [ ] Enable Streamlit authentication (`st.secrets`)
- [ ] Set `CHROMA_DIR` to a persistent volume in containerized deployments
- [ ] Configure log rotation for the audit trail
- [ ] Add rate limiting to the query endpoint
- [ ] Replace `all-MiniLM-L6-v2` with a domain-specific embedding model for better retrieval
- [ ] Consider `llama3.1:70b` for higher-quality answers (requires 48GB+ RAM)
