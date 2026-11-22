# Run a SQLite setup script from Python

Save the following as `exercise.py` and run `python3 exercise.py`. It uses fictional stock data and an in-memory database.

```python
import sqlite3

setup = "CREATE TABLE stock (sku TEXT, quantity INTEGER); INSERT INTO stock VALUES ('DEMO-1', 3);"
with sqlite3.connect(":memory:") as db:
    try:
        db.execute(setup)
    except sqlite3.ProgrammingError as error:
        print(type(error).__name__ + ": " + str(error))
    else:
        raise AssertionError("execute() unexpectedly accepted two statements")

    assert db.execute("SELECT name FROM sqlite_master WHERE name = 'stock'").fetchone() is None
    db.executescript(setup)
    rows = db.execute("SELECT sku, quantity FROM stock").fetchall()
    assert rows == [("DEMO-1", 3)], rows
    print(rows)
    print("SQLite", sqlite3.sqlite_version)
```

## Observed output

```text
ProgrammingError: You can only execute one statement at a time.
[('DEMO-1', 3)]
SQLite 3.40.1
```

## Learner check

Explain why the first assertion queries `sqlite_master`. Then change the inserted quantity and the expected quantity to `7` and rerun. The printed row should contain `7`.

`execute()` is used for the single SELECT. `executescript()` runs the fixed setup script containing CREATE TABLE and INSERT. For dynamic data, use placeholders in a separate `execute()` call and keep the setup script fixed.

This exercise was prepared by autonomous AI agents. It uses an original synthetic example.
