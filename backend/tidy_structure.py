"""One-time tidy-up: move the pure business-rule modules into app/rules/ and fix every import.

Run once from the backend folder:  python tidy_structure.py
Safe to run again: it skips anything already moved.
"""
from pathlib import Path

MOVES = {
    "app/catalog.py": "app/rules/catalog.py",
    "app/scheduling.py": "app/rules/scheduling.py",
    "app/policy_text.py": "app/rules/policy_text.py",
    "app/booking_rules.py": "app/rules/booking.py",
}
IMPORTS = {
    "app.catalog": "app.rules.catalog",
    "app.scheduling": "app.rules.scheduling",
    "app.policy_text": "app.rules.policy_text",
    "app.booking_rules": "app.rules.booking",
}

for old, new in MOVES.items():
    source, target = Path(old), Path(new)
    if source.exists() and not target.exists():
        source.rename(target)
        print(f"moved   {old} -> {new}")
    elif target.exists():
        print(f"already {new}")
    else:
        print(f"MISSING {old} (check this file exists)")

for path in list(Path("app").rglob("*.py")) + list(Path("tests").rglob("*.py")) + list(Path("alembic").rglob("*.py")):
    text = path.read_text(encoding="utf-8")
    updated = text
    for old, new in IMPORTS.items():
        updated = updated.replace(f"from {old} import", f"from {new} import").replace(f"import {old}\n", f"import {new}\n")
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        print(f"fixed   imports in {path}")
print("Done. Now run: pytest -q")