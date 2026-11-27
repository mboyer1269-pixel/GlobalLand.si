import json
from pathlib import Path
import sqlite3

root = Path(__file__).resolve().parent
with sqlite3.connect(":memory:") as db:
    db.executescript((root / "seed.sql").read_text(encoding="utf-8"))
    results = {name: db.execute((root / (name + ".sql")).read_text(encoding="utf-8")).fetchall() for name in ("before", "after")}
print(json.dumps({"sqlite_version": sqlite3.sqlite_version, **results}, indent=2))
