"""Run fictional invoice-total regression cases locally. Made by GlobalLand autonomous AI agents."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

def evaluate(query, case):
    with closing(sqlite3.connect(":memory:")) as db:
        db.execute("CREATE TABLE invoice (id INTEGER PRIMARY KEY, amount INTEGER NOT NULL)")
        db.execute("CREATE TABLE tag (invoice_id INTEGER NOT NULL)")
        db.executemany("INSERT INTO invoice VALUES (?, ?)", case["invoices"])
        db.executemany("INSERT INTO tag VALUES (?)", case["tags"])
        actual = db.execute(query).fetchone()[0]
    expected = case["expected"]
    return {"case": case["case"], "expected": expected, "actual": actual, "passed": actual == expected}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", choices=["exists", "join", "distinct_amount"])
    name = parser.parse_args().query
    suite = json.loads(Path(__file__).with_name("invoice-fixtures.json").read_text(encoding="utf-8"))
    results = [evaluate(suite["queries"][name], case) for case in suite["cases"]]
    print(json.dumps({"sqlite_version": sqlite3.sqlite_version, "query": name, "results": results}, indent=2))
    return int(not all(row["passed"] for row in results))

if __name__ == "__main__":
    raise SystemExit(main())
