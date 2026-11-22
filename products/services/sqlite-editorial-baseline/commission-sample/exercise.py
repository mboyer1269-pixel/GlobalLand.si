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
