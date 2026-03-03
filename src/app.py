"""
src/app.py
----------
Streamlit UI for the Enterprise Knowledge Brain.

Features
--------
* Employee Login via dropdown (no passwords needed in demo mode)
* Access Badge showing role, department, and clearance level
* Real-time streaming chat powered by local LLM
* Source citations panel with relevance scores
* Admin panel for document ingestion
* Audit log viewer
"""

import sys
from pathlib import Path

# Ensure src/ is on the path when run from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from src.database import get_db
from src.rag_pipeline import get_pipeline

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Enterprise Knowledge Brain",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* ── Global reset ─────────────────────────────────────────────── */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ── App background ───────────────────────────────────────────── */
    .stApp {
        background: linear-gradient(160deg, #0f0c29 0%, #141e30 50%, #0d1b3e 100%);
        min-height: 100vh;
    }

    /* ── Sidebar ──────────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1040 0%, #0f1f3d 100%) !important;
        border-right: 1px solid rgba(99, 102, 241, 0.25);
    }
    [data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stSlider label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] small {
        color: #cbd5e1 !important;
    }
    [data-testid="stSidebar"] h1 {
        color: #ffffff !important;
        font-weight: 800 !important;
        font-size: 1.15rem !important;
        letter-spacing: -0.3px;
    }

    /* ── Main content text ────────────────────────────────────────── */
    .stApp p, .stApp li, .stApp span, .stApp label {
        color: #e2e8f0;
    }
    .stApp h1, .stApp h2, .stApp h3 {
        color: #ffffff !important;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    .stApp h2 {
        background: linear-gradient(90deg, #818cf8, #22d3ee);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    /* ── Access Badge ─────────────────────────────────────────────── */
    .badge-container {
        background: linear-gradient(135deg, #4f46e5 0%, #0ea5e9 60%, #06b6d4 100%);
        border-radius: 24px;
        padding: 20px 22px;
        color: #ffffff;
        margin-bottom: 18px;
        box-shadow: 0 8px 32px rgba(79, 70, 229, 0.45),
                    0 2px 8px rgba(0,0,0,0.3);
        border: 1px solid rgba(255,255,255,0.15);
        position: relative;
        overflow: hidden;
    }
    .badge-container::before {
        content: '';
        position: absolute;
        top: -40px; right: -40px;
        width: 120px; height: 120px;
        border-radius: 50%;
        background: rgba(255,255,255,0.08);
    }
    .badge-name {
        font-size: 1.15rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.3px;
        text-shadow: 0 1px 4px rgba(0,0,0,0.2);
    }
    .badge-role {
        font-size: 0.82rem;
        color: rgba(255,255,255,0.88);
        margin-top: 5px;
        font-weight: 500;
        letter-spacing: 0.2px;
    }
    .badge-dept {
        font-size: 0.82rem;
        color: rgba(255,255,255,0.88);
        font-weight: 500;
    }
    .clearance-bar {
        display: flex;
        gap: 6px;
        margin-top: 12px;
        align-items: center;
    }
    .level-dot {
        width: 16px; height: 16px;
        border-radius: 50%;
        background: rgba(255,255,255,0.2);
        border: 2px solid rgba(255,255,255,0.35);
        transition: all 0.2s ease;
    }
    .level-dot.active {
        background: #ffffff;
        border-color: #ffffff;
        box-shadow: 0 0 10px rgba(255,255,255,0.7);
    }

    /* ── Chat messages ────────────────────────────────────────────── */
    [data-testid="stChatMessage"] {
        border-radius: 22px !important;
        padding: 4px 8px !important;
        margin-bottom: 10px !important;
    }

    /* User bubble */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background: linear-gradient(135deg, #312e81 0%, #1e40af 100%) !important;
        border: 1px solid rgba(129, 140, 248, 0.3);
        box-shadow: 0 4px 20px rgba(49, 46, 129, 0.4);
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p {
        color: #ffffff !important;
        font-weight: 500;
    }

    /* Assistant bubble */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        background: rgba(255, 255, 255, 0.04) !important;
        border: 1px solid rgba(99, 102, 241, 0.2);
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        backdrop-filter: blur(10px);
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) p,
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) li {
        color: #e2e8f0 !important;
    }

    /* ── Source cards ─────────────────────────────────────────────── */
    .source-card {
        background: rgba(255, 255, 255, 0.05);
        border-left: 5px solid #6366f1;
        border-radius: 20px;
        padding: 14px 18px;
        margin-bottom: 10px;
        font-size: 0.875rem;
        box-shadow: 0 4px 16px rgba(0,0,0,0.25),
                    inset 0 1px 0 rgba(255,255,255,0.06);
        backdrop-filter: blur(8px);
        border-top: 1px solid rgba(255,255,255,0.07);
        border-right: 1px solid rgba(255,255,255,0.04);
        border-bottom: 1px solid rgba(255,255,255,0.04);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        color: #e2e8f0;
    }
    .source-card:hover {
        transform: translateX(4px);
        box-shadow: 0 6px 24px rgba(99, 102, 241, 0.3);
        border-left-color: #22d3ee;
    }
    .source-card strong {
        color: #ffffff !important;
        font-size: 0.92rem;
        font-weight: 700;
    }
    .source-card small {
        color: #94a3b8 !important;
        font-size: 0.78rem;
    }
    .source-card p {
        color: #cbd5e1 !important;
        font-size: 0.82rem;
        line-height: 1.55;
        margin-top: 8px;
    }
    .source-card summary {
        color: #818cf8 !important;
        font-weight: 600;
        cursor: pointer;
        font-size: 0.82rem;
        margin-top: 8px;
        letter-spacing: 0.2px;
    }
    .source-card summary:hover {
        color: #22d3ee !important;
    }

    /* ── Score badge ──────────────────────────────────────────────── */
    .score-badge {
        display: inline-block;
        background: linear-gradient(90deg, #4f46e5, #0ea5e9);
        color: #ffffff !important;
        border-radius: 30px;
        padding: 3px 10px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.3px;
        box-shadow: 0 2px 8px rgba(79, 70, 229, 0.4);
    }

    /* ── Buttons ──────────────────────────────────────────────────── */
    .stButton > button {
        background: linear-gradient(135deg, #4f46e5 0%, #0ea5e9 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 22px !important;
        font-weight: 700 !important;
        font-size: 0.875rem !important;
        padding: 10px 22px !important;
        letter-spacing: 0.2px;
        box-shadow: 0 4px 16px rgba(79, 70, 229, 0.4) !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 28px rgba(79, 70, 229, 0.6) !important;
        filter: brightness(1.1);
    }
    .stButton > button:active {
        transform: translateY(0px) !important;
    }

    /* ── Suggested question buttons ───────────────────────────────── */
    div[data-testid="column"] .stButton > button {
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(99, 102, 241, 0.4) !important;
        color: #c7d2fe !important;
        font-weight: 500 !important;
        box-shadow: none !important;
        border-radius: 16px !important;
        font-size: 0.82rem !important;
        padding: 10px 14px !important;
        text-align: left !important;
        white-space: normal !important;
        height: auto !important;
        min-height: 56px !important;
    }
    div[data-testid="column"] .stButton > button:hover {
        background: rgba(99, 102, 241, 0.2) !important;
        border-color: #6366f1 !important;
        color: #ffffff !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(99, 102, 241, 0.3) !important;
    }

    /* ── Chat input ───────────────────────────────────────────────── */
    [data-testid="stChatInput"] {
        border-radius: 24px !important;
        background: rgba(255,255,255,0.07) !important;
        border: 1px solid rgba(99, 102, 241, 0.4) !important;
        backdrop-filter: blur(12px);
    }
    [data-testid="stChatInput"]:focus-within {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25) !important;
    }
    [data-testid="stChatInput"] textarea {
        color: #ffffff !important;
        font-size: 0.95rem !important;
    }
    [data-testid="stChatInput"] textarea::placeholder {
        color: #64748b !important;
    }

    /* ── Expander (Sources panel) ─────────────────────────────────── */
    [data-testid="stExpander"] {
        background: rgba(255,255,255,0.03) !important;
        border: 1px solid rgba(99, 102, 241, 0.2) !important;
        border-radius: 20px !important;
        overflow: hidden;
    }
    [data-testid="stExpander"] summary {
        color: #a5b4fc !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        padding: 12px 16px !important;
    }
    [data-testid="stExpander"] summary:hover {
        color: #ffffff !important;
        background: rgba(99, 102, 241, 0.1) !important;
    }

    /* ── Selectbox ────────────────────────────────────────────────── */
    [data-testid="stSidebar"] .stSelectbox > div > div {
        background: rgba(255,255,255,0.07) !important;
        border: 1px solid rgba(99, 102, 241, 0.4) !important;
        border-radius: 16px !important;
        color: #ffffff !important;
    }

    /* ── Spinner / info / warning ─────────────────────────────────── */
    .stSpinner > div {
        border-top-color: #6366f1 !important;
    }
    [data-testid="stAlert"] {
        border-radius: 20px !important;
        border: none !important;
        font-weight: 500;
    }

    /* ── Divider ──────────────────────────────────────────────────── */
    hr {
        border-color: rgba(99, 102, 241, 0.2) !important;
        margin: 12px 0 !important;
    }

    /* ── Scrollbar ────────────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb {
        background: rgba(99, 102, 241, 0.4);
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(99, 102, 241, 0.7);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state init ─────────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "logged_in": False,
        "employee": None,
        "chat_history": [],   # list of {role, content, sources}
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()
db = get_db()

# ── Sidebar: Login & Badge ─────────────────────────────────────────────────────

with st.sidebar:
    st.image(
        "https://img.icons8.com/fluency/96/brain.png",
        width=60,
    )
    st.title("Enterprise Knowledge Brain")
    st.caption("Secure Internal AI Assistant")
    st.divider()

    # --- Employee selector ---
    employees = db.get_all_employees()
    emp_options = {
        f"{e['full_name']} ({e['employee_id']})": e for e in employees
    }
    emp_labels = list(emp_options.keys())

    selected_label = st.selectbox(
        "👤 Employee Login",
        options=["— Select Employee —"] + emp_labels,
        key="selected_employee_label",
    )

    if selected_label != "— Select Employee —":
        emp = emp_options[selected_label]
        st.session_state["employee"] = emp
        st.session_state["logged_in"] = True
    else:
        st.session_state["logged_in"] = False
        st.session_state["employee"] = None

    # --- Access Badge ---
    if st.session_state["logged_in"]:
        emp = st.session_state["employee"]
        sec = emp.get("security_level", 1)
        dots_html = "".join(
            f'<div class="level-dot {"active" if i <= sec else ""}"></div>'
            for i in range(1, 5)
        )
        role_colors = {
            "admin": "🔴", "manager": "🟠", "analyst": "🟡", "employee": "🟢"
        }
        icon = role_colors.get(emp["role"], "⚪")

        st.markdown(
            f"""
            <div class="badge-container">
              <div class="badge-name">🪪 {emp['full_name']}</div>
              <div class="badge-role">{icon} {emp['role'].title()} &nbsp;|&nbsp; ID: {emp['employee_id']}</div>
              <div class="badge-dept">🏢 {emp['department']}</div>
              <div class="clearance-bar">{dots_html}</div>
              <small style="opacity:0.7">Clearance Level {sec}/4</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Accessible departments
        depts = db.get_accessible_departments(emp["role"])
        st.caption(f"**Accessible Departments:** {', '.join(depts)}")

    st.divider()

    # --- Admin Panel ---
    if st.session_state.get("employee") and st.session_state["employee"]["role"] == "admin":
        with st.expander("⚙️ Admin: Ingest Documents", expanded=False):
            uploaded = st.file_uploader(
                "Upload document",
                type=["pdf", "docx", "txt", "xlsx", "md"],
                key="admin_upload",
            )
            ingest_dept = st.selectbox(
                "Department", ["HR", "IT", "Finance", "General"], key="ingest_dept"
            )
            ingest_sec = st.slider(
                "Security Level", 1, 4, 1, key="ingest_sec",
                help="1=Public 2=Internal 3=Confidential 4=Restricted"
            )
            if st.button("🚀 Ingest", use_container_width=True) and uploaded:
                save_dir = Path(__file__).resolve().parent.parent / "documents"
                save_dir.mkdir(exist_ok=True)
                dest = save_dir / uploaded.name
                dest.write_bytes(uploaded.getvalue())
                with st.spinner(f"Ingesting {uploaded.name}…"):
                    pipeline = get_pipeline()
                    result = pipeline.ingest_document(
                        dest, ingest_dept, ingest_sec,
                        requesting_employee=st.session_state["employee"],
                    )
                if result["success"]:
                    st.success(f"✅ {result['chunks']} chunks ingested!")
                else:
                    st.error(f"❌ {result['error']}")

        # Ingest all sample docs button
        with st.expander("📂 Bulk Ingest Sample Docs", expanded=False):
            doc_root = Path(__file__).resolve().parent.parent / "documents"
            dept_map = {
                "hr": ("HR", 2),
                "it": ("IT", 2),
                "finance": ("Finance", 3),
                "general": ("General", 1),
            }
            if st.button("Ingest All Documents in /documents", use_container_width=True):
                pipeline = get_pipeline()
                total = 0
                for folder, (dept, sec) in dept_map.items():
                    d = doc_root / folder
                    if d.exists():
                        with st.spinner(f"Ingesting {dept}…"):
                            results = pipeline.vs.ingest_directory(d, dept, sec)
                            for fname, cnt in results.items():
                                st.write(f"  ✅ `{fname}` → {cnt} chunks")
                                total += cnt
                # Also ingest root-level docs as General
                for fp in doc_root.glob("*.*"):
                    with st.spinner(f"Ingesting {fp.name}…"):
                        r = pipeline.ingest_document(fp, "General", 1)
                        if r["success"]:
                            total += r["chunks"]
                st.success(f"🎉 Total: {total} chunks ingested!")

    # --- Knowledge base stats ---
    with st.expander("📊 Knowledge Base Stats", expanded=False):
        if st.button("Refresh Stats"):
            vs = get_pipeline().vs
            stats = vs.get_collection_stats()
            st.metric("Total Chunks", stats["total_chunks"])
            for dept, cnt in stats.get("departments", {}).items():
                st.write(f"• **{dept}**: {cnt} chunks")

# ── Main: Chat Interface ───────────────────────────────────────────────────────

st.markdown("## 🧠 Enterprise Knowledge Brain")

if not st.session_state["logged_in"]:
    st.info("👈 Please select an employee from the sidebar to begin.")
    st.stop()

employee = st.session_state["employee"]

# Chat history display
chat_container = st.container()
with chat_container:
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            # Show sources for assistant messages
            if msg["role"] == "assistant" and msg.get("sources"):
                with st.expander(
                    f"📚 {len(msg['sources'])} Source(s) Retrieved", expanded=False
                ):
                    for i, src in enumerate(msg["sources"], 1):
                        meta = src.get("metadata", {})
                        score = src.get("relevance_score", 0)
                        st.markdown(
                            f"""<div class="source-card">
                              <strong>[{i}] {meta.get('source', 'Unknown')}</strong>
                              &nbsp;<span class="score-badge">{score:.1%}</span><br/>
                              <small>📁 {meta.get('department', '?')} &nbsp;|&nbsp;
                              🔒 Level {meta.get('security_level', '?')} &nbsp;|&nbsp;
                              📄 Page {meta.get('page', 'N/A')}</small>
                              <details><summary style="cursor:pointer;font-size:0.82rem;margin-top:6px">Show excerpt</summary>
                              <p style="font-size:0.82rem;margin-top:6px">{src['text'][:350]}…</p>
                              </details>
                            </div>""",
                            unsafe_allow_html=True,
                        )

# Suggested questions based on role
if not st.session_state["chat_history"]:
    st.markdown("#### 💡 Suggested Questions")
    dept = employee.get("department", "General")
    suggestions = {
        "HR": [
            "What is the vacation policy?",
            "What are the employee benefits for 2026?",
            "How do I submit a leave request?",
        ],
        "IT": [
            "What are the server security protocols?",
            "How do I connect to the office Wi-Fi?",
            "What is the password policy?",
        ],
        "Finance": [
            "What is the Q1 budget allocation?",
            "How do I submit an expense reimbursement?",
            "What is the approval limit for expenses?",
        ],
        "General": [
            "What is the company mission?",
            "When was the company founded?",
            "What are our core values?",
        ],
    }
    cols = st.columns(3)
    for i, q in enumerate(suggestions.get(dept, suggestions["General"])):
        if cols[i % 3].button(q, use_container_width=True):
            st.session_state["_prefilled_query"] = q
            st.rerun()

# Chat input
prefill = st.session_state.pop("_prefilled_query", "")
user_input = st.chat_input(
    f"Ask a question, {employee['full_name'].split()[0]}…",
    key="chat_input",
) or prefill

if user_input:
    # Append user message
    st.session_state["chat_history"].append(
        {"role": "user", "content": user_input, "sources": []}
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        pipeline = get_pipeline()

        with st.spinner("🧠 กำลังค้นหาคำตอบ..."):
            result = pipeline.query(user_input, employee, stream=False)

        full_response = result.answer

        # แสดงผลแตกต่างกันตาม access_type
        if result.access_type == "no_permission":
            st.warning(full_response)
        elif result.access_type == "no_results":
            st.info(full_response)
        else:
            st.markdown(full_response)

        # แสดง sources เฉพาะเมื่อตอบได้จริงๆ
        if result.sources and result.access_type == "granted":
            with st.expander(
                f"📚 {len(result.sources)} Source(s) Retrieved", expanded=True
            ):
                for i, src in enumerate(result.sources, 1):
                    m = src.get("metadata", {})
                    score = src.get("relevance_score", 0)
                    st.markdown(
                        f"""<div class="source-card">
                          <strong>[{i}] {m.get('source', 'Unknown')}</strong>
                          &nbsp;<span class="score-badge">{score:.1%}</span><br/>
                          <small>📁 {m.get('department', '?')} &nbsp;|&nbsp;
                          🔒 Level {m.get('security_level', '?')} &nbsp;|&nbsp;
                          📄 Page {m.get('page', 'N/A')}</small>
                          <details><summary style="cursor:pointer;font-size:0.82rem;margin-top:6px">Show excerpt</summary>
                          <p style="font-size:0.82rem;margin-top:6px">{src['text'][:350]}…</p>
                          </details>
                        </div>""",
                        unsafe_allow_html=True,
                    )
        else:
            st.caption("_No documents matched your query within your access scope._")

    # Save assistant response
    st.session_state["chat_history"].append(
        {
            "role": "assistant",
            "content": full_response,
            "sources": result.sources,
        }
    )

# Clear chat button
if st.session_state["chat_history"]:
    if st.button("🗑️ Clear Chat", use_container_width=False):
        st.session_state["chat_history"] = []
        st.rerun()