"""
scripts/setup_db.py
────────────────────
รันครั้งเดียวตอน first setup เพื่อสร้าง admin และ default employees
ปลอดภัยที่จะรันซ้ำ — ถ้า user มีอยู่แล้วจะ skip
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import get_db

db = get_db()

# ── Default employees ──────────────────────────────────────────────
employees = [
    ("EMP001", "Alice Johnson",  "admin",    "IT",      4, "admin123"),
    ("EMP002", "Bob Martinez",   "manager",  "HR",      3, "hr_mgr"),
    ("EMP003", "Carol White",    "manager",  "Finance", 3, "fin_mgr"),
    ("EMP004", "David Kim",      "analyst",  "IT",      2, "it_analyst"),
    ("EMP005", "Eva Brown",      "analyst",  "Finance", 2, "fin_analyst"),
    ("EMP006", "Frank Lee",      "employee", "HR",      1, "hr_emp"),
    ("EMP007", "Grace Chen",     "employee", "General", 1, "gen_emp"),
    ("EMP008", "Henry Wilson",   "manager",  "IT",      3, "it_mgr"),
]

# ── Default permissions ────────────────────────────────────────────
permissions = [
    ("admin",    "HR",      4), ("admin",    "IT",      4),
    ("admin",    "Finance", 4), ("admin",    "General", 4),
    ("manager",  "HR",      3), ("manager",  "IT",      3),
    ("manager",  "Finance", 3), ("manager",  "General", 2),
    ("analyst",  "IT",      2), ("analyst",  "Finance", 2),
    ("analyst",  "HR",      1), ("analyst",  "General", 2),
    ("employee", "HR",      1), ("employee", "IT",      1),
    ("employee", "Finance", 1), ("employee", "General", 1),
]

print("Creating employees...")
for eid, name, role, dept, sec, pwd in employees:
    r = db.create_employee(eid, name, role, dept, sec, pwd)
    status = "✅" if r["success"] else f"⚠️  already exists"
    print(f"  {status}  {eid} — {name} ({role})")

print("\nSetting permissions...")
for role, dept, level in permissions:
    db.set_permission(role, dept, level)
print("  ✅ All permissions set.")

print("\n🎉 Setup complete! Login credentials:")
print("─" * 42)
for eid, name, role, dept, _, pwd in employees:
    print(f"  {name:<20} ID: {eid}  PW: {pwd}")