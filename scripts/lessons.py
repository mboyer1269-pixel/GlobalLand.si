"""Relevant lessons for the next decision.

Agents in long-running worlds write lessons and then relearn them anyway
(AI Village, 2025). Here lessons are not left in documents for someone to
reread: the controller retrieves the ones relevant to the open missions with
SQLite FTS5 (BM25 ranking) and injects them into every prompt, together with
the most recent failures.
"""
import re
import sqlite3

WORD = re.compile(r'[A-Za-zÀ-ÿ0-9]{3,}')
STOP = frozenset('the and for with that this from into your you are was were have has not but all any can use '
                 'les des une pour avec dans sur par pas que qui est sont aux ces ses son'.split())


def _terms(texts, limit=40):
    seen, out = set(), []
    for text in texts:
        for word in WORD.findall(text or ''):
            w = word.lower()
            if w not in STOP and w not in seen:
                seen.add(w)
                out.append(w)
                if len(out) >= limit:
                    return out
    return out


def _view(lesson):
    return {k: lesson.get(k) for k in ('lesson_id', 'agent_id', 'mission_id', 'outcome', 'text', 'tags')}


def relevant(lessons, missions, limit=8, recent_failures=3):
    """Lessons matching open/running mission goals, plus the latest failures."""
    if not lessons:
        return []
    active = [m for m in missions if m.get('status') in ('OPEN', 'RUNNING')]
    terms = _terms([m.get('goal') for m in active] + [m.get('mission_id', '').replace('-', ' ') for m in active])
    ranked = []
    if terms:
        try:
            db = sqlite3.connect(':memory:')
            db.execute('CREATE VIRTUAL TABLE l USING fts5(text, tags, mission, idx UNINDEXED)')
            db.executemany('INSERT INTO l VALUES(?,?,?,?)',
                           [(x.get('text', ''), ' '.join(x.get('tags') or []), (x.get('mission_id') or '').replace('-', ' '), i)
                            for i, x in enumerate(lessons)])
            query = ' OR '.join('"%s"' % t for t in terms)
            ranked = [row[0] for row in db.execute('SELECT idx FROM l WHERE l MATCH ? ORDER BY bm25(l) LIMIT ?', (query, limit))]
            db.close()
        except sqlite3.OperationalError:
            # No FTS5 in this SQLite build: rank by shared terms instead.
            wanted = set(terms)
            scored = sorted(((len(wanted & set(_terms([x.get('text'), ' '.join(x.get('tags') or []), x.get('mission_id')]))), -i, i)
                             for i, x in enumerate(lessons)), reverse=True)
            ranked = [i for score, _, i in scored if score][:limit]
    failures = [i for i in range(len(lessons) - 1, -1, -1) if lessons[i].get('outcome') == 'FAILED'][:recent_failures]
    chosen = []
    for i in ranked + failures:
        if i not in chosen:
            chosen.append(i)
    return [_view(lessons[i]) for i in chosen]
