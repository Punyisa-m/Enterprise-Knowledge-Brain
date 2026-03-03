"""
src/database.py
---------------
SQLite-backed RBAC engine for the Enterprise Knowledge Brain.

Tables
------
employees   – identity store (id, name, role, department, security_level)
permissions – department × security_level access map per role
audit_log   – every query attempt is recorded for compliance
"""

import sqlite3
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Path resolution ────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _ROOT / "database" / "rbac.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


# ── Schema DDL ─────────────────────────────────────────────────────────────────
_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS employees (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     TEXT    UNIQUE NOT NULL,   -- e.g. "EMP001"
    full_name       TEXT    NOT NULL,
    role            TEXT    NOT NULL,          -- admin | manager | analyst | employee
    department      TEXT    NOT NULL,          -- HR | IT | Finance | General
    security_level  INTEGER NOT NULL DEFAULT 1, -- 1=public 2=internal 3=confidential 4=restricted
    password_hash   TEXT    NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS permissions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    role            TEXT    NOT NULL,
    department      TEXT    NOT NULL,          -- department this role can access
    max_security_level INTEGER NOT NULL DEFAULT 1,
    UNIQUE(role, department)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     TEXT    NOT NULL,
    query_text      TEXT    NOT NULL,
    departments_accessed TEXT,
    result_count    INTEGER DEFAULT 0,
    access_granted  INTEGER NOT NULL DEFAULT 1,
    timestamp       TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

# ── Seed data ──────────────────────────────────────────────────────────────────
_SEED_EMPLOYEES = [
    # employee_id, full_name, role, department, security_level, password
    ("EMP001", "Alice Johnson",   "admin",    "IT",      4, "admin123"),
    ("EMP002", "Bob Martinez",    "manager",  "HR",      3, "hr_mgr"),
    ("EMP003", "Carol White",     "manager",  "Finance", 3, "fin_mgr"),
    ("EMP004", "David Kim",       "analyst",  "IT",      2, "it_analyst"),
    ("EMP005", "Eva Brown",       "analyst",  "Finance", 2, "fin_analyst"),
    ("EMP006", "Frank Lee",       "employee", "HR",      1, "hr_emp"),
    ("EMP007", "Grace Chen",      "employee", "General", 1, "gen_emp"),
    ("EMP008", "Henry Wilson",    "manager",  "IT",      3, "it_mgr"),
]

# role → {department: max_security_level}
_SEED_PERMISSIONS = [
    # admin can access everything at the highest level
    ("admin",    "HR",      4),
    ("admin",    "IT",      4),
    ("admin",    "Finance", 4),
    ("admin",    "General", 4),
    # managers can access their own dept (confidential) + General
    ("manager",  "HR",      3),
    ("manager",  "IT",      3),
    ("manager",  "Finance", 3),
    ("manager",  "General", 2),
    # analysts – internal access to own dept + General public
    ("analyst",  "HR",      1),
    ("analyst",  "IT",      2),
    ("analyst",  "Finance", 2),
    ("analyst",  "General", 2),
    # employees – public only in own dept + General
    ("employee", "HR",      1),
    ("employee", "IT",      1),
    ("employee", "Finance", 1),
    ("employee", "General", 1),
]


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ── Public API ─────────────────────────────────────────────────────────────────

class RBACDatabase:
    """Thread-safe wrapper around the SQLite RBAC store."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = str(db_path)
        self._init_db()

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            # Only seed once
            cur = conn.execute("SELECT COUNT(*) FROM employees")
            if cur.fetchone()[0] == 0:
                self._seed(conn)
                logger.info("Database seeded with default employees and permissions.")

    def _seed(self, conn: sqlite3.Connection):
        conn.executemany(
            """INSERT OR IGNORE INTO employees
               (employee_id, full_name, role, department, security_level, password_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (eid, name, role, dept, sec, _hash_password(pwd))
                for eid, name, role, dept, sec, pwd in _SEED_EMPLOYEES
            ],
        )
        conn.executemany(
            "INSERT OR IGNORE INTO permissions (role, department, max_security_level) VALUES (?, ?, ?)",
            _SEED_PERMISSIONS,
        )

    # ── Authentication ─────────────────────────────────────────────────────────

    def authenticate(self, employee_id: str, password: str) -> Optional[dict]:
        """
        Returns employee dict on success, None on failure.
        """
        pw_hash = _hash_password(password)
        with self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM employees
                   WHERE employee_id = ? AND password_hash = ? AND is_active = 1""",
                (employee_id, pw_hash),
            ).fetchone()
        return dict(row) if row else None

    def get_employee(self, employee_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM employees WHERE employee_id = ? AND is_active = 1",
                (employee_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_all_employees(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT employee_id, full_name, role, department, security_level, is_active FROM employees WHERE is_active=1 ORDER BY full_name"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Permission checks ──────────────────────────────────────────────────────

    def get_accessible_departments(self, role: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT department FROM permissions WHERE role = ?", (role,)
            ).fetchall()
        return [r["department"] for r in rows]

    def get_max_security_level(self, role: str, department: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT max_security_level FROM permissions WHERE role=? AND department=?",
                (role, department),
            ).fetchone()
        return row["max_security_level"] if row else 0

    def can_access(self, employee: dict, department: str, security_level: int) -> bool:
        """
        Returns True if the employee's role grants them access to
        `department` documents at the given `security_level`.
        """
        max_level = self.get_max_security_level(employee["role"], department)
        return max_level >= security_level

    def build_chroma_filter(self, employee: dict) -> dict:
        """
        Build a ChromaDB `where` filter dict that enforces RBAC.
        Returns an $or clause covering every (dept, security_level) combo
        the employee is allowed to see.
        """
        conditions = []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT department, max_security_level FROM permissions WHERE role=?",
                (employee["role"],),
            ).fetchall()

        for row in rows:
            dept = row["department"]
            max_sec = row["max_security_level"]
            for sec in range(1, max_sec + 1):
                conditions.append(
                    {
                        "$and": [
                            {"department": {"$eq": dept}},
                            {"security_level": {"$eq": sec}},
                        ]
                    }
                )

        if not conditions:
            # No access at all – return impossible filter
            return {"department": {"$eq": "__NO_ACCESS__"}}

        return {"$or": conditions} if len(conditions) > 1 else conditions[0]

    # ── Audit logging ──────────────────────────────────────────────────────────

    def log_query(
        self,
        employee_id: str,
        query_text: str,
        departments_accessed: list[str],
        result_count: int,
        access_granted: bool = True,
    ):
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO audit_log
                   (employee_id, query_text, departments_accessed, result_count, access_granted)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    employee_id,
                    query_text,
                    ",".join(departments_accessed),
                    result_count,
                    int(access_granted),
                ),
            )

    def get_audit_log(self, employee_id: Optional[str] = None, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            if employee_id:
                rows = conn.execute(
                    "SELECT * FROM audit_log WHERE employee_id=? ORDER BY timestamp DESC LIMIT ?",
                    (employee_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
                ).fetchall()
        return [dict(r) for r in rows]


# Singleton
_db_instance: Optional[RBACDatabase] = None


def get_db() -> RBACDatabase:
    global _db_instance
    if _db_instance is None:
        _db_instance = RBACDatabase()
    return _db_instance