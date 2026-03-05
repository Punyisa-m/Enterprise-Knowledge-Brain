"""
src/database.py  (v2 — Production-Ready)
-----------------------------------------
SQLite RBAC engine.  Zero hard-coded seed data.
All employees, roles, and permissions managed via CRUD methods
that the Streamlit admin UI calls directly.

Tables
------
employees   – identity store
roles       – role definitions + max_security_level per dept
permissions – role × department access map
audit_log   – immutable query history
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Optional

from loguru import logger

# ── Path ───────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _ROOT / "database" / "rbac.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ── Schema ─────────────────────────────────────────────────────────────────────
_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS employees (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     TEXT    UNIQUE NOT NULL,
    full_name       TEXT    NOT NULL,
    role            TEXT    NOT NULL,
    department      TEXT    NOT NULL,
    security_level  INTEGER NOT NULL DEFAULT 1,
    password_hash   TEXT    NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS permissions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    role                TEXT    NOT NULL,
    department          TEXT    NOT NULL,
    max_security_level  INTEGER NOT NULL DEFAULT 1,
    UNIQUE(role, department)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id          TEXT    NOT NULL,
    query_text           TEXT    NOT NULL,
    departments_accessed TEXT,
    result_count         INTEGER DEFAULT 0,
    access_granted       INTEGER NOT NULL DEFAULT 1,
    timestamp            TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

DEPARTMENTS = ["HR", "IT", "Finance", "General"]
ROLES       = ["admin", "manager", "analyst", "employee"]


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


class RBACDatabase:
    """Thread-safe SQLite RBAC store with full CRUD."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = str(db_path)
        self._init_db()

    # ── Connection ─────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
        logger.info("Database initialised at {}", self.db_path)

    # ══════════════════════════════════════════════════════════════════════════
    # EMPLOYEE CRUD
    # ══════════════════════════════════════════════════════════════════════════

    def create_employee(
        self,
        employee_id: str,
        full_name: str,
        role: str,
        department: str,
        security_level: int,
        password: str,
    ) -> dict:
        """Create a new employee. Returns the created row or raises on duplicate."""
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO employees
                       (employee_id, full_name, role, department, security_level, password_hash)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (employee_id, full_name, role, department, security_level, _hash(password)),
                )
            logger.info("Created employee {}", employee_id)
            return {"success": True, "employee_id": employee_id}
        except sqlite3.IntegrityError:
            return {"success": False, "error": f"Employee ID '{employee_id}' already exists."}

    def get_all_employees(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT employee_id, full_name, role, department,
                          security_level, is_active, created_at
                   FROM employees ORDER BY full_name"""
            ).fetchall()
        return [dict(r) for r in rows]

    def get_employee(self, employee_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM employees WHERE employee_id = ?", (employee_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_employee(
        self,
        employee_id: str,
        full_name: str,
        role: str,
        department: str,
        security_level: int,
        is_active: bool,
        new_password: Optional[str] = None,
    ) -> dict:
        """Update employee fields. Only updates password if new_password is provided."""
        try:
            with self._connect() as conn:
                if new_password:
                    conn.execute(
                        """UPDATE employees SET full_name=?, role=?, department=?,
                           security_level=?, is_active=?, password_hash=?
                           WHERE employee_id=?""",
                        (full_name, role, department, security_level,
                         int(is_active), _hash(new_password), employee_id),
                    )
                else:
                    conn.execute(
                        """UPDATE employees SET full_name=?, role=?, department=?,
                           security_level=?, is_active=?
                           WHERE employee_id=?""",
                        (full_name, role, department, security_level,
                         int(is_active), employee_id),
                    )
            logger.info("Updated employee {}", employee_id)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_employee(self, employee_id: str) -> dict:
        """Hard delete. Consider setting is_active=0 for production."""
        with self._connect() as conn:
            conn.execute("DELETE FROM employees WHERE employee_id=?", (employee_id,))
        logger.warning("Deleted employee {}", employee_id)
        return {"success": True}

    def authenticate(self, employee_id: str, password: str) -> Optional[dict]:
        pw_hash = _hash(password)
        with self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM employees
                   WHERE employee_id=? AND password_hash=? AND is_active=1""",
                (employee_id, pw_hash),
            ).fetchone()
        return dict(row) if row else None

    # ══════════════════════════════════════════════════════════════════════════
    # PERMISSION CRUD
    # ══════════════════════════════════════════════════════════════════════════

    def set_permission(self, role: str, department: str, max_security_level: int) -> dict:
        """Upsert a permission row."""
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO permissions (role, department, max_security_level)
                       VALUES (?, ?, ?)
                       ON CONFLICT(role, department)
                       DO UPDATE SET max_security_level=excluded.max_security_level""",
                    (role, department, max_security_level),
                )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_permission(self, role: str, department: str) -> dict:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM permissions WHERE role=? AND department=?", (role, department)
            )
        return {"success": True}

    def get_all_permissions(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, department, max_security_level FROM permissions ORDER BY role, department"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_accessible_departments(self, role: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT department FROM permissions WHERE role=?", (role,)
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
        return self.get_max_security_level(employee["role"], department) >= security_level

    # ── ChromaDB filter builder ────────────────────────────────────────────────

    def build_chroma_filter(self, employee: dict) -> dict:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT department, max_security_level FROM permissions WHERE role=?",
                (employee["role"],),
            ).fetchall()
        if not rows:
            return {"department": {"$eq": "__NO_ACCESS__"}}
        depts   = [r["department"] for r in rows]
        max_sec = max(r["max_security_level"] for r in rows)
        return {
            "$and": [
                {"department":     {"$in": depts}},
                {"security_level": {"$lte": max_sec}},
            ]
        }

    # ══════════════════════════════════════════════════════════════════════════
    # AUDIT LOG (append-only)
    # ══════════════════════════════════════════════════════════════════════════

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
                (employee_id, query_text, ",".join(departments_accessed),
                 result_count, int(access_granted)),
            )

    def get_audit_log(self, employee_id: Optional[str] = None, limit: int = 100) -> list[dict]:
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

    def get_stats(self) -> dict:
        with self._connect() as conn:
            emp_count  = conn.execute("SELECT COUNT(*) FROM employees WHERE is_active=1").fetchone()[0]
            perm_count = conn.execute("SELECT COUNT(*) FROM permissions").fetchone()[0]
            log_count  = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        return {"employees": emp_count, "permissions": perm_count, "audit_entries": log_count}


# ── Singleton ──────────────────────────────────────────────────────────────────
_db_instance: Optional[RBACDatabase] = None

def get_db() -> RBACDatabase:
    global _db_instance
    if _db_instance is None:
        _db_instance = RBACDatabase()
    return _db_instance