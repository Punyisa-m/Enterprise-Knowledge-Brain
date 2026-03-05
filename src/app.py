"""
src/app.py  ·  Enterprise Knowledge Brain  ·  v3.0
────────────────────────────────────────────────────
Dark Violet Glass aesthetic · Gemini-style chat · RBAC-gated navigation
All AI calls proxied through FastAPI at localhost:8000
"""

from __future__ import annotations
import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import streamlit as st
from src.database import get_db, DEPARTMENTS, ROLES
import pandas as pd

API_BASE = "http://localhost:8000"

# ══════════════════════════════════════════════════════════════════
# PAGE CONFIG  (must be first Streamlit call)
# ══════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Knowledge Brain",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════
# CSS  –  Dark Violet Glass + Gemini Chat
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ══ 0. TOKENS ════════════════════════════════════════════════════════════════ */
:root {
  /* Dark canvas layers */
  --bg-deep:    #08080e;
  --bg-base:    #0d0d1a;
  --bg-raised:  #12121f;
  --bg-float:   #181828;

  /* Glass surfaces */
  --sf:     rgba(255,255,255,0.04);
  --sf-md:  rgba(255,255,255,0.07);
  --sf-hi:  rgba(255,255,255,0.10);

  /* Borders */
  --bdr:        rgba(255,255,255,0.07);
  --bdr-hi:     rgba(255,255,255,0.13);
  --bdr-accent: rgba(139,92,246,0.45);

  /* Text (light on dark) */
  --ink:    #eeeef5;
  --ink-2:  #9898b4;
  --ink-3:  #5a5a72;

  /* Accent palette */
  --violet:  #8b5cf6;
  --indigo:  #6366f1;
  --sky:     #38bdf8;
  --cyan:    #22d3ee;
  --emerald: #10b981;
  --rose:    #f43f5e;
  --amber:   #f59e0b;

  /* Gradients */
  --g-brand:   linear-gradient(135deg,#8b5cf6 0%,#6366f1 50%,#38bdf8 100%);
  --g-violet:  linear-gradient(135deg,#8b5cf6 0%,#a78bfa 100%);
  --g-sky:     linear-gradient(135deg,#6366f1 0%,#38bdf8 100%);
  --g-emerald: linear-gradient(135deg,#059669 0%,#10b981 100%);
  --g-rose:    linear-gradient(135deg,#be123c 0%,#f43f5e 100%);
  --g-amber:   linear-gradient(135deg,#b45309 0%,#f59e0b 100%);

  /* Bento tile tints */
  --t-violet:  rgba(139,92,246,0.11);
  --t-indigo:  rgba(99,102,241,0.11);
  --t-sky:     rgba(56,189,248,0.09);
  --t-emerald: rgba(16,185,129,0.10);
  --t-rose:    rgba(244,63,94,0.10);
  --t-amber:   rgba(245,158,11,0.10);

  /* Radius */
  --r-xl:24px; --r-lg:18px; --r-md:14px; --r-sm:9px;

  /* Shadows */
  --sh-xs:  0 1px 4px rgba(0,0,0,0.60);
  --sh-sm:  0 2px 12px rgba(0,0,0,0.55), 0 0 0 1px var(--bdr);
  --sh-md:  0 8px 32px rgba(0,0,0,0.65), 0 0 0 1px var(--bdr-hi);
  --sh-lg:  0 20px 64px rgba(0,0,0,0.75),0 0 0 1px var(--bdr-hi);
  --sh-glow:0 0 0 1px var(--bdr-accent), 0 8px 32px rgba(139,92,246,0.22);

  --blur: blur(22px) saturate(180%);
}

/* ══ 1. RESET ═════════════════════════════════════════════════════════════════ */
*{box-sizing:border-box;-webkit-font-smoothing:antialiased;}
html,body,[class*="css"]{
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Inter","Segoe UI",sans-serif;
}
p,li,span,label,td,th,h1,h2,h3,h4,h5,h6,small,strong,em,summary,caption{
  color:var(--ink);
}
#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important;}
[data-testid="stAppViewBlockContainer"]{padding:0!important;max-width:100%!important;}

/* ══ 2. APP BACKGROUND ════════════════════════════════════════════════════════ */
.stApp{
  background:
    radial-gradient(ellipse 80% 55% at 10%  5%, rgba(139,92,246,0.14) 0%,transparent 52%),
    radial-gradient(ellipse 65% 50% at 90% 90%, rgba(56,189,248,0.10)  0%,transparent 52%),
    radial-gradient(ellipse 55% 40% at 55% 45%, rgba(99,102,241,0.07)  0%,transparent 48%),
    var(--bg-base);
  min-height:100vh;
}

/* ══ 3. SIDEBAR ═══════════════════════════════════════════════════════════════ */
[data-testid="stSidebar"]{
  background:rgba(12,12,22,0.92)!important;
  backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);
  border-right:1px solid var(--bdr-hi)!important;
  box-shadow:var(--sh-md);
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] div{color:var(--ink)!important;}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3{color:var(--ink)!important;font-weight:800!important;}

/* ══ 4. INPUTS ════════════════════════════════════════════════════════════════ */
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] > div > div,
[data-testid="stTextArea"] textarea{
  background:var(--bg-raised)!important;
  border:1px solid var(--bdr-hi)!important;
  border-radius:var(--r-md)!important;
  color:var(--ink)!important;
  font-size:0.95rem!important;
  box-shadow:var(--sh-xs)!important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus{
  border-color:var(--violet)!important;
  box-shadow:0 0 0 3px rgba(139,92,246,0.18)!important;
  outline:none!important;
}
[data-testid="stTextInput"] label,
[data-testid="stSelectbox"] label,
[data-testid="stTextArea"] label{
  color:var(--ink-2)!important;font-size:0.84rem!important;font-weight:600!important;
}
[data-testid="stSelectbox"] ul,
[data-testid="stSelectbox"] li{
  background:var(--bg-float)!important;color:var(--ink)!important;
}

/* ══ 5. BUTTONS ═══════════════════════════════════════════════════════════════ */
.stButton>button{
  background:var(--g-brand)!important;
  color:#ffffff!important;
  border:none!important;border-radius:var(--r-md)!important;
  font-weight:700!important;font-size:0.92rem!important;padding:11px 26px!important;
  box-shadow:0 4px 18px rgba(139,92,246,0.35)!important;
  transition:all .18s ease!important;letter-spacing:0.1px;
}
.stButton>button:hover{
  transform:translateY(-1px)!important;
  box-shadow:0 8px 30px rgba(139,92,246,0.48)!important;
  filter:brightness(1.08);
}
.stButton>button:active{transform:translateY(0)!important;}
div[data-testid="column"] .stButton>button{
  background:var(--sf-md)!important;
  color:var(--ink)!important;
  border:1px solid var(--bdr-hi)!important;
  box-shadow:var(--sh-xs)!important;font-weight:600!important;
}
div[data-testid="column"] .stButton>button:hover{
  background:var(--t-violet)!important;
  border-color:var(--bdr-accent)!important;
  box-shadow:var(--sh-glow)!important;
}

/* ══ 6. BENTO TILES ═══════════════════════════════════════════════════════════ */
.bento{
  border-radius:var(--r-xl);
  border:1px solid var(--bdr-hi);
  padding:22px 24px;
  box-shadow:var(--sh-sm);
  backdrop-filter:blur(12px);
  transition:box-shadow .2s ease, transform .2s ease, border-color .2s ease;
}
.bento:hover{
  box-shadow:var(--sh-glow);
  transform:translateY(-2px);
  border-color:var(--bdr-accent);
}
.b-violet  {background:var(--t-violet);}
.b-indigo  {background:var(--t-indigo);}
.b-sky     {background:var(--t-sky);}
.b-emerald {background:var(--t-emerald);}
.b-rose    {background:var(--t-rose);}
.b-amber   {background:var(--t-amber);}
.b-base    {background:var(--bg-raised);}
.b-float   {background:var(--bg-float);}

.bval{font-size:2.3rem;font-weight:800;color:var(--ink);letter-spacing:-2px;line-height:1;}
.blbl{font-size:.72rem;font-weight:700;color:var(--ink-3);
      text-transform:uppercase;letter-spacing:.8px;margin-top:5px;}

.bico{
  width:42px;height:42px;border-radius:13px;
  display:inline-flex;align-items:center;justify-content:center;
  font-size:1.4rem;margin-bottom:10px;
}
.ic-v{background:rgba(139,92,246,.18);border:1px solid rgba(139,92,246,.25);}
.ic-i{background:rgba(99,102,241,.18); border:1px solid rgba(99,102,241,.25);}
.ic-s{background:rgba(56,189,248,.15); border:1px solid rgba(56,189,248,.22);}
.ic-e{background:rgba(16,185,129,.15); border:1px solid rgba(16,185,129,.22);}
.ic-r{background:rgba(244,63,94,.15);  border:1px solid rgba(244,63,94,.22);}
.ic-a{background:rgba(245,158,11,.15); border:1px solid rgba(245,158,11,.22);}

/* ══ 7. CHAT BUBBLES ══════════════════════════════════════════════════════════ */
[data-testid="stChatMessage"]{
  background:transparent!important;border:none!important;
  padding:5px 0!important;box-shadow:none!important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) > div:last-child{
  background:var(--g-brand)!important;
  border-radius:22px 22px 6px 22px!important;
  padding:14px 18px!important;max-width:72%;margin-left:auto;
  box-shadow:0 4px 20px rgba(139,92,246,0.30);
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) li{color:#fff!important;}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) > div:last-child{
  background:var(--bg-float)!important;
  border:1px solid var(--bdr-hi)!important;
  border-radius:6px 22px 22px 22px!important;
  padding:16px 20px!important;max-width:82%;
  box-shadow:var(--sh-sm);
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) p,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) li,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) strong,
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) span{
  color:var(--ink)!important;
}
[data-testid="stChatMessage"] pre{
  background:rgba(0,0,0,0.40)!important;
  border:1px solid var(--bdr-hi)!important;
  border-radius:12px!important;padding:14px 16px!important;font-size:.84rem!important;
}
[data-testid="stChatMessage"] code{
  background:rgba(139,92,246,0.15)!important;
  color:#c4b5fd!important;
  border-radius:6px!important;padding:2px 6px!important;font-size:.87em!important;
}

/* ══ 8. CHAT INPUT ════════════════════════════════════════════════════════════ */
[data-testid="stChatInput"]{
  background:var(--bg-float)!important;
  border:1px solid var(--bdr-hi)!important;
  border-radius:22px!important;
  box-shadow:var(--sh-md)!important;
}
[data-testid="stChatInput"]:focus-within{
  border-color:var(--violet)!important;
  box-shadow:0 0 0 3px rgba(139,92,246,0.15),var(--sh-md)!important;
}
[data-testid="stChatInput"] textarea{
  color:var(--ink)!important;font-size:.97rem!important;
  background:transparent!important;border:none!important;
}
[data-testid="stChatInput"] textarea::placeholder{color:var(--ink-3)!important;}

/* ══ 9. SOURCE CARDS ══════════════════════════════════════════════════════════ */
.src-card{
  background:var(--bg-float);
  border:1px solid var(--bdr-hi);
  border-left:4px solid var(--violet);
  border-radius:var(--r-lg);
  padding:14px 18px;margin-bottom:10px;
  box-shadow:var(--sh-sm);
  transition:transform .15s, box-shadow .15s, border-left-color .15s;
}
.src-card:hover{
  transform:translateX(4px);
  border-left-color:var(--sky);
  box-shadow:var(--sh-glow);
}
.src-card strong{color:var(--ink)!important;font-size:.9rem;}
.src-card small {color:var(--ink-3)!important;font-size:.78rem;}
.src-card p     {color:var(--ink-2)!important;font-size:.83rem;line-height:1.55;margin-top:8px;}
.src-card summary{color:var(--violet)!important;font-weight:600;font-size:.82rem;cursor:pointer;margin-top:8px;}

.score-pill{
  display:inline-block;
  background:rgba(139,92,246,0.15);
  color:#c4b5fd!important;
  border:1px solid rgba(139,92,246,0.30);
  border-radius:30px;padding:2px 10px;font-size:.74rem;font-weight:700;
}

/* ══ 10. SIDEBAR BADGE ════════════════════════════════════════════════════════ */
.badge{
  background:var(--g-brand);
  border-radius:var(--r-lg);
  padding:18px 22px;
  box-shadow:0 8px 30px rgba(139,92,246,0.35);
  margin-bottom:16px;position:relative;overflow:hidden;
}
.badge::before{
  content:'';position:absolute;top:-28px;right:-28px;
  width:90px;height:90px;border-radius:50%;background:rgba(255,255,255,0.10);
}
.badge-name{font-size:1rem;font-weight:800;color:#fff;}
.badge-meta{font-size:.8rem;color:rgba(255,255,255,0.78);margin-top:4px;}
.badge-dots{display:flex;gap:5px;margin-top:10px;}
.dot{width:13px;height:13px;border-radius:50%;background:rgba(255,255,255,0.22);border:1.5px solid rgba(255,255,255,0.40);}
.dot.on{background:#fff;border-color:#fff;box-shadow:0 0 9px rgba(255,255,255,0.65);}

/* ══ 11. STATUS PILLS ═════════════════════════════════════════════════════════ */
.pill-ok  {display:inline-block;background:rgba(16,185,129,0.15);color:#6ee7b7!important;border-radius:20px;padding:3px 11px;font-size:.78rem;font-weight:700;border:1px solid rgba(16,185,129,0.30);}
.pill-err {display:inline-block;background:rgba(244,63,94,0.15); color:#fda4af!important;border-radius:20px;padding:3px 11px;font-size:.78rem;font-weight:700;border:1px solid rgba(244,63,94,0.30);}
.pill-warn{display:inline-block;background:rgba(245,158,11,0.15);color:#fcd34d!important;border-radius:20px;padding:3px 11px;font-size:.78rem;font-weight:700;border:1px solid rgba(245,158,11,0.30);}

/* ══ 12. EXPANDER / DATAFRAME / ALERT ════════════════════════════════════════ */
[data-testid="stExpander"]{
  background:var(--bg-float)!important;
  border:1px solid var(--bdr-hi)!important;
  border-radius:var(--r-lg)!important;
  box-shadow:var(--sh-sm)!important;
}
[data-testid="stExpander"] summary{color:var(--ink)!important;font-weight:600!important;}
[data-testid="stDataFrame"]{border-radius:var(--r-lg)!important;overflow:hidden;box-shadow:var(--sh-sm)!important;}
[data-testid="stAlert"]{border-radius:var(--r-lg)!important;border:1px solid var(--bdr-hi)!important;}

/* ══ 13. LOGIN CARD ═══════════════════════════════════════════════════════════ */
.login-card{
  width:100%;max-width:420px;
  background:rgba(18,18,32,0.92);
  backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);
  border-radius:var(--r-xl);border:1px solid var(--bdr-hi);
  box-shadow:var(--sh-lg);padding:44px 48px 40px;text-align:center;
}
.login-logo{
  width:68px;height:68px;border-radius:20px;background:var(--g-brand);
  display:inline-flex;align-items:center;justify-content:center;
  font-size:2.1rem;margin-bottom:20px;
  box-shadow:0 8px 30px rgba(139,92,246,0.40);
}
.login-title{font-size:1.6rem;font-weight:800;color:var(--ink);letter-spacing:-0.5px;margin-bottom:4px;}
.login-sub  {font-size:.88rem;color:var(--ink-3);margin-bottom:28px;}

/* ══ 14. METRIC CARDS ════════════════════════════════════════════════════════ */
.metric-card{
  background:var(--bg-float);border-radius:var(--r-md);
  border:1px solid var(--bdr-hi);box-shadow:var(--sh-sm);
  padding:20px 22px;text-align:center;
}
.metric-val{font-size:2rem;font-weight:800;color:var(--violet);letter-spacing:-1px;}
.metric-lbl{font-size:0.8rem;color:var(--ink-3);font-weight:600;margin-top:2px;text-transform:uppercase;letter-spacing:0.5px;}

/* ══ 15. PAGE TITLES / DIVIDERS ═══════════════════════════════════════════════ */
.page-title{font-size:1.65rem;font-weight:800;color:var(--ink);letter-spacing:-.6px;margin-bottom:4px;}
.page-sub  {font-size:.9rem;color:var(--ink-3);margin-bottom:22px;}
hr{border:none!important;border-top:1px solid var(--bdr-hi)!important;margin:16px 0!important;}

/* ══ 16. SCROLLBAR ════════════════════════════════════════════════════════════ */
::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-track{background:var(--bg-raised);}
::-webkit-scrollbar-thumb{background:rgba(139,92,246,0.35);border-radius:10px;}
::-webkit-scrollbar-thumb:hover{background:rgba(139,92,246,0.60);}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════
_DEFAULTS = {
    "authed": False, "employee": None,
    "chat_history": [], "login_error": "",
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

db = get_db()

# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════
def api_get(path, timeout=8.0):
    try: return httpx.get(f"{API_BASE}{path}", timeout=timeout).json()
    except: return None

def api_post(path, payload, timeout=120.0):
    try: return httpx.post(f"{API_BASE}{path}", json=payload, timeout=timeout).json()
    except Exception as e: return {"error": str(e)}

def role_icon(role):
    return {"admin":"◆","manager":"▲","analyst":"●","employee":"○"}.get(role,"○")

def source_html(src, idx):
    m = src.get("metadata", {}); score = src.get("relevance_score", 0)
    return (
        f'<div class="src-card">'
        f'<strong>[{idx}] {m.get("source","Unknown")}</strong>'
        f'&nbsp;<span class="score-pill">{score:.0%}</span><br/>'
        f'<small>{m.get("department","?")} · Level {m.get("security_level","?")} · Page {m.get("page","N/A")}</small>'
        f'<details><summary>Show excerpt</summary><p>{src.get("text","")[:320]}…</p></details>'
        f'</div>'
    )

def stream_from_api(query, employee_id):
    """SSE streaming generator for st.write_stream."""
    collected = []
    try:
        with httpx.stream("POST", f"{API_BASE}/query/stream",
                          json={"query": query, "employee_id": employee_id},
                          timeout=120.0) as resp:
            for line in resp.iter_lines():
                if not line.startswith("data:"): continue
                raw = line[5:].strip()
                if not raw: continue
                try:
                    evt = json.loads(raw)
                except Exception:
                    continue
                if "token" in evt: yield evt["token"]
                if "sources" in evt: collected.extend(evt["sources"])
    except Exception:
        r = api_post("/query", {"query": query, "employee_id": employee_id})
        if r:
            yield r.get("answer", "No response.")
            collected.extend(r.get("sources", []))
    st.session_state["_last_sources"] = collected


# ══════════════════════════════════════════════════════════════════
# LOGIN WALL
# ══════════════════════════════════════════════════════════════════
if not st.session_state["authed"]:
    st.markdown("<style>[data-testid='stSidebar']{display:none!important;}</style>",
                unsafe_allow_html=True)

    st.markdown("""
    <div style="display:flex;justify-content:center;align-items:center;min-height:88vh;">
      <div class="login-card">
        <div class="login-logo">🧠</div>
        <div class="login-title">Knowledge Brain</div>
        <div class="login-sub">Enterprise AI Portal · Sign in to continue</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        employees = db.get_all_employees()
        emp_map   = {f"{e['full_name']} — {e['employee_id']}": e
                     for e in employees if e.get("is_active", 1)}

        sel = st.selectbox("Account", [""] + list(emp_map.keys()),
                           label_visibility="collapsed",
                           placeholder="Select your account…")
        pwd = st.text_input("Password", type="password",
                            label_visibility="collapsed", placeholder="Password")

        if st.session_state["login_error"]:
            st.markdown(
                f'<p style="color:#f43f5e;font-size:0.85rem;text-align:center">'
                f'{st.session_state["login_error"]}</p>',
                unsafe_allow_html=True)

        if st.button("Sign In", use_container_width=True):
            if not sel:
                st.session_state["login_error"] = "Please select an account."
            elif not pwd:
                st.session_state["login_error"] = "Please enter your password."
            else:
                auth = db.authenticate(emp_map[sel]["employee_id"], pwd)
                if auth:
                    st.session_state.update(authed=True, employee=auth, login_error="")
                    st.rerun()
                else:
                    st.session_state["login_error"] = "Incorrect password. Please try again."
                    st.rerun()
    st.stop()


# ══════════════════════════════════════════════════════════════════
# AUTHENTICATED — SIDEBAR
# ══════════════════════════════════════════════════════════════════
employee = st.session_state["employee"]
is_admin = employee["role"] == "admin"
is_mgr   = employee["role"] in ("admin", "manager")

with st.sidebar:
    st.markdown(
        '<p style="font-size:1.05rem;font-weight:800;letter-spacing:-0.3px;margin-bottom:0;color:var(--ink)">🧠 Knowledge Brain</p>'
        '<p style="font-size:0.78rem;color:var(--ink-3);margin-top:0">Enterprise AI Portal</p>',
        unsafe_allow_html=True)
    st.divider()

    # Badge
    sec  = employee.get("security_level", 1)
    dots = "".join(f'<div class="dot {"on" if i<=sec else ""}"></div>' for i in range(1,5))
    st.markdown(
        f'<div class="badge">'
        f'<div class="badge-name">{role_icon(employee["role"])} {employee["full_name"]}</div>'
        f'<div class="badge-meta">{employee["role"].title()} · {employee["department"]} · {employee["employee_id"]}</div>'
        f'<div class="badge-dots">{dots}</div>'
        f'<small style="opacity:0.8;color:#fff">Clearance Level {sec}/4</small>'
        f'</div>', unsafe_allow_html=True)

    # Role-gated navigation
    st.markdown('<p style="font-size:0.72rem;font-weight:700;color:var(--ink-3);letter-spacing:0.8px;text-transform:uppercase;margin-bottom:6px">Navigation</p>', unsafe_allow_html=True)
    pages      = (["Chat","Dashboard","User Management","Permissions","Documents","Audit Log"] if is_admin
                  else ["Chat","Audit Log"] if is_mgr
                  else ["Chat"])
    page_icons = {
        "Chat":"💬  Chat", "Dashboard":"◈  Dashboard",
        "User Management":"◉  Users", "Permissions":"◈  Permissions",
        "Documents":"◎  Documents", "Audit Log":"◌  Audit Log",
    }
    nav  = st.radio("nav", [page_icons[p] for p in pages], label_visibility="collapsed")
    page = next(p for p in pages if page_icons[p] == nav)

    st.divider()
    health = api_get("/health")
    if health:
        ok = health.get("ollama_ok", False)
        st.markdown(
            f'<span class="{"pill-ok" if ok else "pill-err"}">{"System Online" if ok else "LLM Offline"}</span>'
            f'<p style="font-size:0.75rem;color:var(--ink-3);margin-top:6px">'
            f'{health.get("vector_chunks",0)} chunks · {health.get("db_employees",0)} users</p>',
            unsafe_allow_html=True)
    else:
        st.markdown('<span class="pill-err">API Offline</span>', unsafe_allow_html=True)
        st.caption("`uvicorn src.api:app --port 8000`")

    st.divider()
    if st.button("Sign Out", use_container_width=True):
        for k in _DEFAULTS: st.session_state[k] = _DEFAULTS[k]
        st.rerun()


# ══════════════════════════════════════════════════════════════════
# PAGE: CHAT
# ══════════════════════════════════════════════════════════════════
if page == "Chat":
    hr = time.localtime().tm_hour
    greet = "morning" if 5<=hr<12 else "afternoon" if 12<=hr<18 else "evening"
    st.markdown(
        f'<p class="page-title">Good {greet}, {employee["full_name"].split()[0]}</p>'
        f'<p class="page-sub">Ask me anything from your accessible knowledge base.</p>',
        unsafe_allow_html=True)

    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("sources"):
                with st.expander(f"Sources ({len(msg['sources'])})"):
                    for i, s in enumerate(msg["sources"], 1):
                        st.markdown(source_html(s, i), unsafe_allow_html=True)

    if not st.session_state["chat_history"]:
        suggestions = {
            "HR":      ["What is the vacation policy?","What are the 2026 benefits?","How do I submit leave?"],
            "IT":      ["What are the server security rules?","How do I connect to Wi-Fi?","How does VPN work?"],
            "Finance": ["What is the Q1 budget?","How do I claim expenses?","What are the approval limits?"],
            "General": ["What is the company mission?","When was the company founded?","Who are the executives?"],
        }
        qs = suggestions.get(employee.get("department","General"), suggestions["General"])
        cols = st.columns(3)
        for i, q in enumerate(qs):
            if cols[i].button(q, use_container_width=True):
                st.session_state["_prefill"] = q; st.rerun()

    prefill    = st.session_state.pop("_prefill", "")
    user_input = st.chat_input("Message Knowledge Brain…") or prefill

    if user_input:
        st.session_state["chat_history"].append({"role":"user","content":user_input,"sources":[]})
        with st.chat_message("user"):
            st.markdown(user_input)

        st.session_state["_last_sources"] = []
        with st.chat_message("assistant"):
            response = st.write_stream(stream_from_api(user_input, employee["employee_id"]))

        sources = st.session_state.get("_last_sources", [])
        if sources:
            with st.expander(f"Sources — {len(sources)} document(s)", expanded=True):
                for i, s in enumerate(sources, 1):
                    st.markdown(source_html(s, i), unsafe_allow_html=True)

        st.session_state["chat_history"].append(
            {"role":"assistant","content":response or "","sources":sources})

    if st.session_state["chat_history"]:
        if st.button("Clear conversation"):
            st.session_state["chat_history"] = []; st.rerun()


# ══════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════════
elif page == "Dashboard":
    if not is_admin: st.error("Admin access required."); st.stop()
    st.markdown('<p class="page-title">Dashboard</p><p class="page-sub">System overview at a glance.</p>', unsafe_allow_html=True)

    stats = api_get("/stats") or {}
    db_s  = stats.get("database", {}); vs_s = stats.get("vector_store", {})
    health = api_get("/health") or {}

    m1,m2,m3,m4 = st.columns(4)
    for col, val, lbl in [
        (m1, db_s.get("employees","—"),     "Active Users"),
        (m2, vs_s.get("total_chunks","—"),  "Vector Chunks"),
        (m3, db_s.get("audit_entries","—"), "Audit Entries"),
        (m4, db_s.get("permissions","—"),   "Permissions"),
    ]:
        col.markdown(f'<div class="metric-card"><div class="metric-val">{val}</div><div class="metric-lbl">{lbl}</div></div>', unsafe_allow_html=True)

    st.markdown("")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Knowledge Base by Department**")
        depts = vs_s.get("departments", {})
        if depts:
            st.dataframe(pd.DataFrame(depts.items(), columns=["Department","Chunks"]), use_container_width=True, hide_index=True)
        else:
            st.info("No documents ingested yet.")
    with c2:
        st.markdown("**System Health**")
        ok = health.get("ollama_ok", False)
        for label, status, cls in [
            ("Ollama LLM",  "Online" if ok else "Offline", "pill-ok" if ok else "pill-err"),
            ("FastAPI",     "Online",  "pill-ok"),
            ("SQLite DB",   "Online",  "pill-ok"),
            ("ChromaDB",    "Online" if depts else "Empty", "pill-ok" if depts else "pill-warn"),
            ("Uptime",      f'{health.get("uptime_s","?"):.0f}s', "pill-ok"),
        ]:
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--bdr)">'
                f'<span style="font-weight:500;font-size:0.9rem;color:var(--ink)">{label}</span>'
                f'<span class="{cls}">{status}</span></div>',
                unsafe_allow_html=True)

    st.markdown(""); st.markdown("**Recent Activity**")
    logs = db.get_audit_log(limit=8)
    if logs:
        df = pd.DataFrame(logs)[["timestamp","employee_id","query_text","result_count","access_granted"]]
        df.columns = ["Time","Employee","Query","Results","Granted"]
        df["Granted"] = df["Granted"].map({1:"✓",0:"✗"})
        df["Query"]   = df["Query"].str[:60] + "…"
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No activity yet.")


# ══════════════════════════════════════════════════════════════════
# PAGE: USER MANAGEMENT
# ══════════════════════════════════════════════════════════════════
elif page == "User Management":
    if not is_admin: st.error("Admin access required."); st.stop()
    st.markdown('<p class="page-title">User Management</p><p class="page-sub">Create, edit, and deactivate accounts.</p>', unsafe_allow_html=True)

    with st.expander("Create New Employee"):
        c1,c2 = st.columns(2)
        n_id   = c1.text_input("Employee ID", placeholder="EMP009")
        n_name = c2.text_input("Full Name",   placeholder="Jane Smith")
        n_role = c1.selectbox("Role", ROLES, key="cr_r")
        n_dept = c2.selectbox("Department", DEPARTMENTS, key="cr_d")
        n_sec  = c1.slider("Security Level", 1, 4, 1, key="cr_s")
        n_pwd  = c2.text_input("Password", type="password", key="cr_p")
        if st.button("Create Employee"):
            if all([n_id, n_name, n_pwd]):
                r = db.create_employee(n_id, n_name, n_role, n_dept, n_sec, n_pwd)
                st.success("Created.") if r["success"] else st.error(r["error"]); st.rerun()
            else: st.warning("Fill all fields.")

    all_emps = db.get_all_employees()
    if all_emps:
        df = pd.DataFrame(all_emps)[["employee_id","full_name","role","department","security_level","is_active"]]
        df.columns = ["ID","Name","Role","Dept","Level","Active"]
        df["Active"] = df["Active"].map({1:"Yes",0:"No"})
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("**Edit Employee**")
    sel_id = st.selectbox("Select", [e["employee_id"] for e in all_emps], key="sel_e")
    if sel_id:
        row = db.get_employee(sel_id); c1,c2 = st.columns(2)
        e_name   = c1.text_input("Name",  value=row["full_name"], key="e_nm")
        e_role   = c2.selectbox("Role",   ROLES, index=ROLES.index(row["role"]) if row["role"] in ROLES else 0, key="e_rl")
        e_dept   = c1.selectbox("Dept",   DEPARTMENTS, index=DEPARTMENTS.index(row["department"]) if row["department"] in DEPARTMENTS else 0, key="e_dp")
        e_sec    = c2.slider("Level",     1, 4, int(row["security_level"]), key="e_sc")
        e_active = c1.checkbox("Active",  value=bool(row["is_active"]), key="e_ac")
        e_pwd    = c2.text_input("New Password (blank = keep)", type="password", key="e_pw")
        ca,cd,_  = st.columns([1,1,5])
        if ca.button("Update"):
            r = db.update_employee(sel_id, e_name, e_role, e_dept, e_sec, e_active, e_pwd or None)
            st.success("Updated.") if r["success"] else st.error(r["error"]); st.rerun()
        if cd.button("Delete"):
            db.delete_employee(sel_id); st.warning(f"Deleted {sel_id}."); st.rerun()


# ══════════════════════════════════════════════════════════════════
# PAGE: PERMISSIONS
# ══════════════════════════════════════════════════════════════════
elif page == "Permissions":
    if not is_admin: st.error("Admin access required."); st.stop()
    st.markdown('<p class="page-title">Permissions</p><p class="page-sub">Role × Department access matrix.</p>', unsafe_allow_html=True)

    perms = db.get_all_permissions()
    if perms:
        pdf = pd.DataFrame(perms); pdf.columns = ["Role","Department","Max Level"]
        st.dataframe(pdf, use_container_width=True, hide_index=True)

    c1,c2,c3 = st.columns(3)
    p_role = c1.selectbox("Role",       ROLES,       key="p_r")
    p_dept = c2.selectbox("Department", DEPARTMENTS, key="p_d")
    p_sec  = c3.slider("Max Level", 1, 4, 1,         key="p_s")
    cs,cd,_ = st.columns([1,1,5])
    if cs.button("Set"):   db.set_permission(p_role,p_dept,p_sec); st.success("Updated."); st.rerun()
    if cd.button("Remove"):db.delete_permission(p_role,p_dept);     st.warning("Removed."); st.rerun()
    st.divider()
    if st.button("Apply Default Permissions"):
        for r,d,s in [
            ("admin","HR",4),("admin","IT",4),("admin","Finance",4),("admin","General",4),
            ("manager","HR",3),("manager","IT",3),("manager","Finance",3),("manager","General",2),
            ("analyst","IT",2),("analyst","Finance",2),("analyst","HR",1),("analyst","General",2),
            ("employee","HR",1),("employee","IT",1),("employee","Finance",1),("employee","General",1),
        ]: db.set_permission(r,d,s)
        st.success("Default permissions applied."); st.rerun()


# ══════════════════════════════════════════════════════════════════
# PAGE: DOCUMENTS
# ══════════════════════════════════════════════════════════════════
elif page == "Documents":
    if not is_admin: st.error("Admin access required."); st.stop()
    st.markdown('<p class="page-title">Documents</p><p class="page-sub">Upload and manage the knowledge base.</p>', unsafe_allow_html=True)

    uploaded = st.file_uploader("Upload document", type=["pdf","docx","txt","xlsx","md"])
    c1,c2    = st.columns(2)
    d_dept   = c1.selectbox("Department", DEPARTMENTS, key="d_dp")
    d_sec    = c2.slider("Security Level", 1, 4, 1, key="d_sc")
    if st.button("Ingest Document") and uploaded:
        with st.spinner(f"Ingesting {uploaded.name}…"):
            try:
                r = httpx.post(f"{API_BASE}/ingest",
                    data={"department":d_dept,"security_level":d_sec,"employee_id":employee["employee_id"]},
                    files={"file":(uploaded.name,uploaded.getvalue())},timeout=120)
                res = r.json()
                st.success(f"Ingested {res['chunks']} chunks.") if res.get("success") else st.error(res.get("detail","Error"))
            except Exception as e: st.error(str(e))

    st.divider()
    if st.button("Bulk Ingest All Sample Documents"):
        from src.vector_store import get_vector_store
        vs = get_vector_store(); total = 0
        doc_root = Path(__file__).resolve().parent.parent / "documents"
        for folder,(dept,sec) in {"hr":("HR",2),"it":("IT",2),"finance":("Finance",3),"general":("General",1)}.items():
            d = doc_root / folder
            if d.exists():
                with st.spinner(f"Ingesting {dept}…"):
                    for fname,cnt in vs.ingest_directory(d,dept,sec).items():
                        st.write(f"{fname} → {cnt} chunks"); total += cnt
        st.success(f"Total: {total} chunks ingested.")

    st.divider()
    stats = api_get("/stats") or {}
    vs_s  = stats.get("vector_store", {})
    st.metric("Total Chunks", vs_s.get("total_chunks", 0))
    for dept, cnt in vs_s.get("departments", {}).items():
        st.write(f"**{dept}** — {cnt} chunks")


# ══════════════════════════════════════════════════════════════════
# PAGE: AUDIT LOG
# ══════════════════════════════════════════════════════════════════
elif page == "Audit Log":
    if not is_mgr: st.error("Manager or Admin access required."); st.stop()
    st.markdown('<p class="page-title">Audit Log</p><p class="page-sub">Every query — who asked what, when.</p>', unsafe_allow_html=True)

    logs = db.get_audit_log(limit=200)
    if logs:
        df = pd.DataFrame(logs)[["timestamp","employee_id","query_text","departments_accessed","result_count","access_granted"]]
        df.columns = ["Time","Employee","Query","Departments","Results","Granted"]
        df["Granted"] = df["Granted"].map({1:"Yes",0:"No"})
        df["Query"]   = df["Query"].str[:80] + "…"
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No audit entries yet.")