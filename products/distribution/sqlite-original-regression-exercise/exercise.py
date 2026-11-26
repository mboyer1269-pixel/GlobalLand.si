import argparse
import json
import sqlite3

# Original fictional equipment-usage exercise built by autonomous AI agents.
# Run python3 exercise.py preaggregate for the passing control.
# Run either competing query to show how the regression cases detect its defect.
QUERIES = {
    'global-join': '''SELECT u.team, u.device, SUM(u.minutes)
        FROM usage AS u JOIN grants AS g ON g.device = u.device
        GROUP BY u.team, u.device ORDER BY u.team, u.device''',
    'distinct-sum': '''SELECT u.team, u.device, SUM(DISTINCT u.minutes)
        FROM usage AS u WHERE EXISTS (SELECT 1 FROM grants AS g
        WHERE g.team = u.team AND g.device = u.device)
        GROUP BY u.team, u.device ORDER BY u.team, u.device''',
    'preaggregate': '''WITH totals AS (SELECT team, device, SUM(minutes) AS minutes
        FROM usage GROUP BY team, device)
        SELECT t.team, t.device, t.minutes FROM totals AS t
        WHERE EXISTS (SELECT 1 FROM grants AS g
        WHERE g.team = t.team AND g.device = t.device)
        ORDER BY t.team, t.device''',
}

# Each fixture gives usage events, grant rows, and independently specified totals.
CASES = [
    ('single grant', [('red', 'D1', 7)], [('red', 'D1')], [('red', 'D1', 7)]),
    ('multiple grants', [('red', 'D1', 7)], [('red', 'D1'), ('red', 'D1')], [('red', 'D1', 7)]),
    ('same-value events', [('red', 'D1', 7), ('red', 'D1', 7)], [('red', 'D1')], [('red', 'D1', 14)]),
    ('same id across teams', [('red', 'D1', 7), ('blue', 'D1', 4)], [('red', 'D1'), ('blue', 'D1')], [('blue', 'D1', 4), ('red', 'D1', 7)]),
    ('absent grants', [('red', 'D1', 7)], [('blue', 'D1')], []),
]

parser = argparse.ArgumentParser(description='Check grant-scoped equipment usage totals against five fictional fixtures.')
parser.add_argument('query', choices=QUERIES)
query = parser.parse_args().query
cases = []
for name, usage, grants, expected in CASES:
    database = sqlite3.connect(':memory:')
    try:
        database.execute('CREATE TABLE usage(team TEXT, device TEXT, minutes INTEGER)')
        database.execute('CREATE TABLE grants(team TEXT, device TEXT)')
        database.executemany('INSERT INTO usage VALUES (?, ?, ?)', usage)
        database.executemany('INSERT INTO grants VALUES (?, ?)', grants)
        actual = database.execute(QUERIES[query]).fetchall()
    finally:
        database.close()
    cases.append({'name': name, 'expected': expected, 'actual': actual, 'match': actual == expected})
failures = [case['name'] for case in cases if not case['match']]
print(json.dumps({'query': query, 'sqlite_version': sqlite3.sqlite_version, 'cases': cases, 'failures': failures}, indent=2))
raise SystemExit(bool(failures))
