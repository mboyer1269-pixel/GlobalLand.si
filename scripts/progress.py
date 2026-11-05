"""No-progress detector and the public blocker board.

Progress is measured from host evidence, never from agent claims. Between two
successful think turns:
- an OUTCOME is a mission reaching COMPLETED or FAILED (a decision was made) or
  verified REVENUE growing (refunds and the founder's deposit excluded);
- a turn is PRODUCTIVE if it has an outcome or a new product path outside
  products/research/ and products/receipts/.
Rewriting existing files, messages, claims and new research notes are not
progress on their own: they are exactly what an audit loop produces.

Two counters, two alerts, each with a system card on world/blockers.json that
closes by itself when the condition clears:
- `stall_turns` (3) consecutive unproductive turns: the short loop alert;
- `outcome_turns` (12) consecutive turns without an outcome: new files alone
  can no longer hold off the alert, so producing throwaway files does not
  game the detector.
"""
import datetime
import hashlib
import json
import pathlib
import re
import stat

from supervisor import atomic_json

STATE = 'state/private/progress.json'
MAX_FILES = 5000
SYSTEM_CARD = 'SYSTEM-NO-PROGRESS'
OUTCOME_CARD = 'SYSTEM-NO-OUTCOME'


def _setting(config, key, default):
    value = (config.get('progress') or {}).get(key, default)
    return value if type(value) is int and 1 <= value <= 1000 else default


def stall_turns(config):
    return _setting(config, 'stall_turns', 3)


def outcome_turns(config):
    return _setting(config, 'outcome_turns', 12)


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
    return dict(products=products, missions=missions, revenue_cents=bank.get('revenue_cents', 0))


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
    # Cumulative verified REVENUE only: refunds and the founder's deposit are not earned.
    gain = current['revenue_cents'] - previous.get('revenue_cents', current['revenue_cents'])
    outcome = bool(outcomes or gain > 0)
    return dict(productive=outcome or bool(built), outcome=outcome, mission_outcomes=outcomes,
                new_products=built[:20], new_product_count=len(built), new_research_count=len(research),
                rewritten_count=len(rewritten), revenue_gain_cents=max(gain, 0))


def load(root):
    path = pathlib.Path(root) / STATE
    try:
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError()
        if not path.exists(): return {}
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 16 * 1024 * 1024:
            raise ValueError()
        value = json.loads(path.read_text())
        if not isinstance(value, dict): raise ValueError()
        sources = value.get('commercial_seen_sources', [])
        if (not isinstance(sources, list) or len(sources) > 100000
                or any(not isinstance(s, str) or not re.fullmatch(r'[0-9a-f]{64}', s) for s in sources)
                or ('last' in value and not isinstance(value['last'], dict))):
            raise ValueError()
        for key in ('stalled_turns', 'dry_turns', 'commercial_turns', 'turns_without_verified_revenue'):
            count = value.get(key, 0)
            if count is None and key == 'turns_without_verified_revenue': continue
            if type(count) is not int or count < 0: raise ValueError()
        return value
    except (OSError, ValueError, TypeError):
        # A destroyed history cannot establish whether a restored source is new.
        return dict(commercial_history_unavailable=True, turns_without_verified_revenue=None)


def assess(root, world, bank, config):
    """Pure evaluation for the coming turn; nothing is persisted here."""
    state = load(root)
    current = fingerprint(root, world, bank)
    threshold, dry_limit = stall_turns(config), outcome_turns(config)
    if 'last' not in state:
        change = dict(productive=None, outcome=None, baseline=True)
        stalled = dry = 0
    else:
        change = delta(state['last'], current)
        stalled = 0 if change['productive'] else state.get('stalled_turns', 0) + 1
        dry = 0 if change['outcome'] else state.get('dry_turns', 0) + 1
    import commercial
    snapshot = commercial.progress_snapshot(root, config)
    seen = set(state.get('commercial_seen_sources', []))
    sources = set(snapshot['sources'])
    complete = (snapshot['state'] == 'AVAILABLE' and not (seen - sources)
                and not state.get('commercial_history_unavailable'))
    new_feedback = bool(set(snapshot['interpreted_sources']) - seen) if complete else None
    history = seen | sources
    if len(history) > 100000:
        # Retain the previous baseline rather than forgetting old identities.
        complete = False; history = seen; new_feedback = None
    commercial_turns = None
    commercial_baseline = state.get('commercial_baseline', False)
    if complete and not commercial_baseline:
        new_feedback = False
    if complete:
        commercial_turns = (0 if not commercial_baseline or new_feedback
                            else state.get('commercial_turns', 0) + 1)
    prior_revenue_turns = state.get('turns_without_verified_revenue')
    revenue_turns = (0 if 'turns_without_verified_revenue' not in state or change.get('revenue_gain_cents', 0) > 0
                     else None if prior_revenue_turns is None else prior_revenue_turns + 1)
    return dict(current=current, change=change, stalled_turns=stalled, threshold=threshold,
                commercial_turns=commercial_turns, new_commercial_feedback=new_feedback,
                commercial_seen_sources=sorted(history), commercial_baseline=commercial_baseline or complete,
                commercial_history_unavailable=bool(state.get('commercial_history_unavailable')),
                commercial_state=snapshot['state'] if complete or snapshot['state'] != 'AVAILABLE' else 'UNAVAILABLE',
                revenue_turns=revenue_turns, turns_without_verified_revenue=revenue_turns,
                dry_turns=dry, outcome_threshold=dry_limit,
                alert=stalled >= threshold, drought=dry >= dry_limit,
                stalled_since=(state.get('stalled_since') if stalled and state.get('stalled_turns') else None),
                dry_since=(state.get('dry_since') if dry and state.get('dry_turns') else None),
                last_productive_turn=state.get('last_productive_turn'),
                last_outcome_turn=state.get('last_outcome_turn'))


def commit(root, turn, assessment):
    """Persist once per successful turn so retries are never double-counted."""
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    state = load(root)
    if state.get('last_turn') == turn:
        return state
    path = pathlib.Path(root) / STATE
    if (any(p.is_symlink() for p in (path, *path.parents))
            or (path.exists() and (not path.is_file() or path.stat().st_nlink != 1))):
        raise ValueError('Progress storage unavailable')
    stalled = assessment['stalled_turns']
    dry = assessment['dry_turns']
    record = dict(last=assessment['current'], stalled_turns=stalled, threshold=assessment['threshold'],
                  commercial_turns=(assessment['commercial_turns'] if assessment['commercial_turns'] is not None
                                    else state.get('commercial_turns', 0)),
                  commercial_seen_sources=assessment['commercial_seen_sources'],
                  commercial_history_unavailable=assessment['commercial_history_unavailable'],
                  commercial_baseline=assessment['commercial_baseline'],
                  commercial_state=assessment['commercial_state'],
                  turns_without_verified_revenue=assessment['turns_without_verified_revenue'],
                  dry_turns=dry, outcome_threshold=assessment['outcome_threshold'],
                  last_turn=turn, last_turn_at=now,
                  stalled_since=(assessment['stalled_since'] or now) if stalled else None,
                  dry_since=(assessment['dry_since'] or now) if dry else None,
                  last_productive_turn=(turn if assessment['change'].get('productive') else state.get('last_productive_turn')),
                  last_outcome_turn=(turn if assessment['change'].get('outcome') else state.get('last_outcome_turn')),
                  last_change={k: v for k, v in assessment['change'].items()})
    atomic_json(pathlib.Path(root) / STATE, record)
    return record


def for_prompt(assessment):
    """The part of the assessment the brain sees (no hashes)."""
    return dict(stalled_turns=assessment['stalled_turns'], threshold=assessment['threshold'],
                activity_semantics='operational progress; mission conclusions and files are not market or financial evidence',
                commercial_state=assessment['commercial_state'],
                turns_without_new_interpreted_feedback=assessment['commercial_turns'],
                new_interpreted_feedback=assessment['new_commercial_feedback'],
                turns_without_verified_revenue=assessment['turns_without_verified_revenue'],
                turns_without_outcome=assessment['dry_turns'], outcome_threshold=assessment['outcome_threshold'],
                alert=assessment['alert'], drought=assessment['drought'],
                last_productive_turn=assessment['last_productive_turn'],
                last_outcome_turn=assessment['last_outcome_turn'],
                change_since_last_turn=assessment['change'])


ALERT = ('PROGRESS ALERT: {n} consecutive turns produced no completed or failed mission, no new product '
         'outside products/research/ and no verified revenue. Do not repeat audits, access probes or status '
         'messages. This turn must do at least one of: complete a stalled mission with evidence; fail it '
         'with a reason and create a different mission (pivot); build and publish a new product file. If an '
         'external account, credential or capability is missing, record it once with WORLD raise_blocker '
         '(needs_founder true, a stable blocker_id) and continue with work that does not need it.')


DROUGHT = ('OUTCOME ALERT: {n} consecutive turns without a completed or failed mission or verified revenue. '
           'New files no longer count as progress. This turn must close a mission with evidence (complete it, or '
           'fail it with a reason and pivot to a different mission), or put a product in front of real buyers. '
           'Record any missing external capability once with WORLD raise_blocker.')


def prompt_alerts(assessment):
    alerts = []
    if assessment['alert']:
        alerts.append(ALERT.format(n=assessment['stalled_turns']))
    if assessment['drought']:
        alerts.append(DROUGHT.format(n=assessment['dry_turns']))
    return alerts


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
                                 'aucun revenu vérifié. Missions ouvertes : ' + (', '.join(running) or 'aucune') + '.',
                          mission_id=None, expected_gain=None, raised_by='PROGRESS-DETECTOR', reports=stalled,
                          opened_at=state.get('stalled_since'), last_reported_at=state.get('last_turn_at')))
    dry, dry_limit = state.get('dry_turns', 0), state.get('outcome_threshold', 12)
    if dry >= dry_limit:
        cards.append(dict(id=OUTCOME_CARD, status='OPEN', owner='AGENTS', category='PROGRESS',
                          title='%d tours consécutifs sans mission conclue ni revenu vérifié' % dry,
                          detail='De nouveaux fichiers ne suffisent plus : conclure ou abandonner une mission avec preuves, '
                                 'ou mettre un produit devant de vrais acheteurs.',
                          mission_id=None, expected_gain=None, raised_by='PROGRESS-DETECTOR', reports=dry,
                          opened_at=state.get('dry_since'), last_reported_at=state.get('last_turn_at')))
    cards.sort(key=lambda c: (c['owner'] != 'FOUNDER', c['opened_at'] or ''))
    resolved.sort(key=lambda c: c['resolved_at'] or '', reverse=True)
    return dict(founder_actions=sum(1 for c in cards if c['owner'] == 'FOUNDER'), open=cards,
                resolved_recent=resolved[:20],
                progress=dict(stalled_turns=stalled, threshold=threshold, stalled_since=state.get('stalled_since'),
                              activity_semantics='operational',
                              commercial_state=state.get('commercial_state', 'UNAVAILABLE'),
                              turns_without_new_interpreted_feedback=(state.get('commercial_turns')
                                  if state.get('commercial_state') == 'AVAILABLE' else None),
                              turns_without_verified_revenue=state.get('turns_without_verified_revenue'),
                              turns_without_outcome=dry, outcome_threshold=dry_limit, dry_since=state.get('dry_since'),
                              last_outcome_turn=state.get('last_outcome_turn'),
                              last_productive_turn=state.get('last_productive_turn'),
                              last_turn=state.get('last_turn'), last_change=state.get('last_change')))
