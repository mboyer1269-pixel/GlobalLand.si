"""Relevant lessons for the next decision.

Agents in long-running worlds write lessons and then relearn them anyway
(AI Village, 2025). Here lessons are not left in documents for someone to
reread: the controller retrieves the ones relevant to the open missions with
SQLite FTS5 (BM25 ranking) and injects them into every prompt, together with
the most recent failures.
"""
import re
import sqlite3
import copy

SEMANTICS = dict(
    sources=dict(lessons='AGENT_CONCLUSIONS', blocker_descriptions='AGENT_REPORTS',
                 products_and_plans='AGENT_REPORTS',
                 capabilities_treasury_and_receipts='HOST_OBSERVATIONS_WITH_SPECIFIC_LIMITS'),
    guidance=('Agent conclusions are revisable, not host rules. Preserve useful observations and check their '
              'scope and conditions before applying advice. A mission ID is provenance, not proof of global '
              'scope; its outcome does not validate every claim. Repetition in lessons, blockers or products '
              'is not independent evidence. Host observations establish only their specific facts and limits, '
              'not a general strategy. A missing prerequisite blocks dependent operations; waiting on one '
              'experiment does not automatically suspend independent possibilities. Maintain, narrow or '
              'revise conclusions when evidence or conditions warrant, within the existing mandate.'))

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
    return {k: lesson.get(k) for k in ('lesson_id', 'agent_id', 'mission_id', 'outcome', 'text', 'tags', 'at')}


def prompt_context(stored_lessons, missions, limit=8, recent_failures=3):
    """Host provenance labels; never mutate stored lessons or infer their truth."""
    items = copy.deepcopy(relevant(stored_lessons, missions, limit, recent_failures))
    for item in items:
        item['memory_meta'] = dict(kind='AGENT_CONCLUSION', scope_status='UNSPECIFIED',
                                   validation='NOT_HOST_VALIDATED')
    return dict(items=items, semantics=copy.deepcopy(SEMANTICS))


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


def playbooks(work, limit_chars=8000):
    """Decision playbooks shipped in agents/playbooks/, injected in full each turn.

    They are short on purpose (about 850 words): reliable rules beat retrieval
    that might miss the one that matters this turn.
    """
    import pathlib
    base = pathlib.Path(work) / 'agents' / 'playbooks'
    out, used = {}, 0
    if not base.is_dir():
        return out
    for path in sorted(base.glob('*.md')):
        if path.name == 'THIRD_PARTY.md' or path.is_symlink():
            continue
        text = path.read_text(encoding='utf-8', errors='replace').strip()
        if used + len(text) > limit_chars:
            break
        out[path.stem] = text
        used += len(text)
    return out
