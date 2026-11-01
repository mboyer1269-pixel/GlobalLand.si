"""No-progress detector and the public blocker board.

Progress is measured from host evidence, never from agent claims. Between two
successful think turns, a turn is productive when at least one of these holds:
- a mission reached COMPLETED or FAILED (a decision was made);
- a new product path appeared outside products/research/ and products/receipts/;
- verified bank cash grew beyond the initial deposit (net cash gain).
Rewriting existing files, messages, claims and new research notes are not
progress on their own: they are exactly what an audit loop produces.

After `stall_turns` consecutive unproductive turns the brain receives a
progress alert and a system card opens on world/blockers.json. It closes by
itself on the next productive turn.
"""
import datetime
import hashlib
import json
import pathlib

from supervisor import atomic_json

STATE = 'state/private/progress.json'
MAX_FILES = 5000
SYSTEM_CARD = 'SYSTEM-NO-PROGRESS'


def stall_turns(config):
    value = (config.get('progress') or {}).get('stall_turns', 3)
    return value if type(value) is int and 1 <= value <= 100 else 3


def fingerprint(root, world, bank):
    """Observable state: product hashes, mission statuses and verified cash."""
    products = {}
    base = pathlib.Path(root) / 'work' / 'products'
    if base.exists():
        for path in sorted(base.rglob('*')):
            if len(products) >= MAX_FILES:
                break
            if path.is_file() and not path.is_symlink() and 'receipts' not in path.relative_to(base).parts:
                products[str(path.relative_to(base.parent))] = hashlib.sha256(path.read_bytes()).hexdigest()
    missions = {m['mission_id']: m['status'] for m in world.get('missions', [])}
    return dict(products=products, missions=missions, cash_cents=bank.get('cash_cents', 0),
                funding_verified=bool(bank.get('funding_verified')))


def delta(previous, current):
    """What changed between two fingerprints, and whether it counts as progress."""
    old_products, new_products = previous.get('products', {}), current['products']
    added = sorted(set(new_products) - set(old_products))
    built = [p for p in added if not p.startswith('products/research/')]
    research = [p for p in added if p.startswith('products/research/')]
    rewritten = sorted(p for p in set(new_products) & set(old_products) if new_products[p] != old_products[p])
    old_missions = previous.get('missions', {})
    outcomes = sorted(m for m, status in current['missions'].items()
                      if status in ('COMPLETED', 'FAILED') and old_missions.get(m) != status)
    gain = current['cash_cents'] - previous.get('cash_cents', current['cash_cents'])
    if current['funding_verified'] and not previous.get('funding_verified', current['funding_verified']):
        gain -= 5000  # the founder's deposit is not something the agents earned
    productive = bool(outcomes or built or gain > 0)
    return dict(productive=productive, mission_outcomes=outcomes, new_products=built[:20],
                new_product_count=len(built), new_research_count=len(research),
                rewritten_count=len(rewritten), net_cash_gain_cents=max(gain, 0))


def load(root):
    path = pathlib.Path(root) / STATE
    return json.loads(path.read_text()) if path.exists() else {}


def assess(root, world, bank, config):
    """Pure evaluation for the coming turn; nothing is persisted here."""
    state = load(root)
    current = fingerprint(root, world, bank)
    threshold = stall_turns(config)
    if 'last' not in state:
        change = dict(productive=None, baseline=True)
        stalled = 0
    else:
        change = delta(state['last'], current)
        stalled = 0 if change['productive'] else state.get('stalled_turns', 0) + 1
    return dict(current=current, change=change, stalled_turns=stalled, threshold=threshold,
                alert=stalled >= threshold,
                stalled_since=(state.get('stalled_since') if stalled and state.get('stalled_turns') else None),
                last_productive_turn=state.get('last_productive_turn'))


def commit(root, turn, assessment):
    """Persist once per successful turn so retries are never double-counted."""
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    state = load(root)
    stalled = assessment['stalled_turns']
    record = dict(last=assessment['current'], stalled_turns=stalled, threshold=assessment['threshold'],
                  last_turn=turn, last_turn_at=now,
                  stalled_since=(assessment['stalled_since'] or now) if stalled else None,
                  last_productive_turn=(turn if assessment['change'].get('productive') else state.get('last_productive_turn')),
                  last_change={k: v for k, v in assessment['change'].items()})
    atomic_json(pathlib.Path(root) / STATE, record)
    return record


def for_prompt(assessment):
    """The part of the assessment the brain sees (no hashes)."""
    return dict(stalled_turns=assessment['stalled_turns'], threshold=assessment['threshold'],
                alert=assessment['alert'], last_productive_turn=assessment['last_productive_turn'],
                change_since_last_turn=assessment['change'])


ALERT = ('PROGRESS ALERT: {n} consecutive turns produced no completed or failed mission, no new product '
         'outside products/research/ and no net cash gain. Do not repeat audits, access probes or status '
         'messages. This turn must do at least one of: complete a stalled mission with evidence; fail it '
         'with a reason and create a different mission (pivot); build and publish a new product file. If an '
         'external account, credential or capability is missing, record it once with WORLD raise_blocker '
         '(needs_founder true, a stable blocker_id) and continue with work that does not need it.')


def _iso(value):
    if value is None:
        return None
    return datetime.datetime.fromtimestamp(value, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def board(root, world):
    """world/blockers.json: the one place the founder needs to look."""
    state = load(root)
    cards, resolved = [], []
    for b in world.get('blockers', []):
        card = dict(id=b['blocker_id'], status=b['status'], owner='FOUNDER' if b['needs_founder'] else 'AGENTS',
                    category=b['category'], title=b['title'], detail=b['detail'], mission_id=b.get('mission_id'),
                    expected_gain=b.get('expected_gain'), raised_by=b['raised_by'], reports=b['reports'],
                    opened_at=_iso(b['opened_at']), last_reported_at=_iso(b.get('last_reported_at')))
        if b['status'] == 'OPEN':
            cards.append(card)
        else:
            resolved.append(dict(card, resolution=b.get('resolution'), resolved_by=b.get('resolved_by'),
                                 resolved_at=_iso(b.get('resolved_at'))))
    stalled, threshold = state.get('stalled_turns', 0), state.get('threshold', 3)
    if stalled >= threshold:
        running = sorted(m['mission_id'] for m in world.get('missions', []) if m['status'] in ('OPEN', 'RUNNING'))
        cards.append(dict(id=SYSTEM_CARD, status='OPEN', owner='AGENTS', category='PROGRESS',
                          title='%d tours consécutifs sans résultat vérifiable' % stalled,
                          detail='Aucune mission terminée ou abandonnée, aucun nouveau produit hors products/research/, '
                                 'aucun gain de trésorerie. Missions ouvertes : ' + (', '.join(running) or 'aucune') + '.',
                          mission_id=None, expected_gain=None, raised_by='PROGRESS-DETECTOR', reports=stalled,
                          opened_at=state.get('stalled_since'), last_reported_at=state.get('last_turn_at')))
    cards.sort(key=lambda c: (c['owner'] != 'FOUNDER', c['opened_at'] or ''))
    resolved.sort(key=lambda c: c['resolved_at'] or '', reverse=True)
    return dict(founder_actions=sum(1 for c in cards if c['owner'] == 'FOUNDER'), open=cards,
                resolved_recent=resolved[:20],
                progress=dict(stalled_turns=stalled, threshold=threshold, stalled_since=state.get('stalled_since'),
                              last_productive_turn=state.get('last_productive_turn'),
                              last_turn=state.get('last_turn'), last_change=state.get('last_change')))
