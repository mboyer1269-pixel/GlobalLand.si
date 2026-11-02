"""Persistent virtual agents and GLC. This module never handles real currency."""
import contextlib
import hashlib
import json
import re
import secrets
import sqlite3
import time


class World:
    def __init__(self, db_path, clock=None):
        self.path = str(db_path)
        self.clock = clock or time.time
        with self._connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS world (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, digest TEXT NOT NULL, result TEXT NOT NULL);
            ''')
            db.execute('INSERT OR IGNORE INTO world VALUES (1, ?)', (json.dumps(dict(
                state='ACTIVE', agents=[], missions=[], messages=[], events=[],
                policy=dict(maintenance_glc=1, interest_basis_points=500), cycles=[])),))

    @contextlib.contextmanager
    def _connect(self):
        # Always closed: the supervisor is long-lived across many operations.
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    def _text(value, name, limit=4000):
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError('Invalid ' + name)
        return value

    @classmethod
    def _id(cls, value):
        cls._text(value, 'ID', 128)
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]*', value):
            raise ValueError('Unsafe ID')
        return value

    @staticmethod
    def _integer(value, limit=10**12):
        if type(value) is not int or not 0 <= value <= limit:
            raise ValueError('Expected bounded nonnegative integer')
        return value

    @staticmethod
    def _find(items, key, value):
        found = next((x for x in items if x[key] == value), None)
        if found is None:
            raise ValueError('Unknown ' + key)
        return found

    # Bounded state: world/status.json must stay far below the 1 MiB
    # publication limit, or every publication (and so the world) would stop.
    MAX_EVENTS, MAX_MESSAGES, MAX_CLOSED_MISSIONS, MAX_AGENTS = 2000, 100, 200, 100

    def _event(self, s, kind, **data):
        s['events'].append(dict(type=kind, timestamp=self.clock(), **data))
        del s['events'][:-self.MAX_EVENTS]

    def _compact(self, s):
        del s['messages'][:-self.MAX_MESSAGES]
        closed = [m for m in s['missions'] if m['status'] in ('COMPLETED', 'FAILED')]
        for old in closed[:max(0, len(closed) - self.MAX_CLOSED_MISSIONS)]:
            s['missions'].remove(old)
            # A dropped ID is never reused: history and lessons keep pointing at one mission.
            s.setdefault('retired_missions', []).append(old['mission_id'])
        del s.setdefault('retired_missions', [])[:-20000]
        del s['cycles'][:-1000]

    def _agent(self, s, agent_id, active=False):
        a = self._find(s['agents'], 'agent_id', self._id(agent_id))
        if active and a['status'] != 'ACTIVE':
            raise ValueError('Agent disabled')
        return a

    def _register(self, s, agent_id, role):
        self._id(agent_id)
        self._text(role, 'role', 500)
        if any(a['agent_id'] == agent_id for a in s['agents']):
            raise ValueError('Agent already exists')
        if len(s['agents']) >= self.MAX_AGENTS:
            raise ValueError('Too many agents; liquidate or reuse existing ones')
        a = dict(agent_id=agent_id, role=role, wallet_glc=100, debt_glc=100, status='ACTIVE')
        s['agents'].append(a)
        self._event(s, 'GLC_ISSUANCE', agent_id=agent_id, amount=100, reason='initial loan')
        self._event(s, 'GLC_LOAN', agent_id=agent_id, amount=100)
        return a

    def bootstrap(self):
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                s = json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
                if s['state'] != 'EXTINCT' and not s.get('bootstrapped'):
                    for role in ['DIRECTOR', 'RESEARCHER', 'BUILDER', 'ACQUISITION', 'AUDITOR']:
                        if not any(a['agent_id'] == role for a in s['agents']):
                            self._register(s, role, role)
                    if not any(m['mission_id'] == 'WORLD-FIRST-REVENUE' for m in s['missions']):
                        self._dispatch(s, dict(op='create_mission', mission_id='WORLD-FIRST-REVENUE',
                            goal='Choose any global Internet activity and produce evidence-backed revenue; explore all markets and strategies freely.'))
                    s['bootstrapped'] = True
                    db.execute('UPDATE world SET data=? WHERE id=1', (json.dumps(s),))
                db.commit()
            except Exception:
                db.rollback()
                raise
        return self.snapshot()

    def snapshot(self):
        with self._connect() as db:
            s = json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
        view = {k: (v[-100:] if k == 'events' else v[-50:] if k in ('reviews', 'messages') else v) for k, v in s.items()
                if k not in ('cycles', 'bootstrapped', 'lessons', 'lesson_seq', 'retired_missions')}
        # Lessons are retrieved by relevance for prompts, not dumped wholesale.
        view['lesson_count'] = len(s.get('lessons', []))
        return view

    def apply(self, operation_id, args):
        self._id(operation_id)
        if type(args) is not dict:
            raise ValueError('Arguments must be an object')
        try:
            encoded = json.dumps(args, sort_keys=True, separators=(',', ':'), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError('Arguments must be JSON-safe') from exc
        if len(encoded) > 50000:
            raise ValueError('Arguments too large')
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                old = db.execute('SELECT digest,result FROM operations WHERE id=?', (operation_id,)).fetchone()
                if old:
                    if old[0] != digest:
                        raise ValueError('Operation ID is bound to different arguments')
                    db.commit()
                    return json.loads(old[1])
                s = json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
                if s['state'] == 'EXTINCT':
                    raise ValueError('World is extinct')
                result = self._dispatch(s, args)
                self._compact(s)
                # Freeze result before later operations can mutate the same object.
                result_json = json.dumps(result)
                db.execute('UPDATE world SET data=? WHERE id=1', (json.dumps(s),))
                db.execute('INSERT INTO operations VALUES (?,?,?)', (operation_id, digest, result_json))
                db.commit()
                return json.loads(result_json)
            except Exception:
                db.rollback()
                raise

    def _dispatch(self, s, a):
        fields = {
            'register_agent': ({'agent_id', 'role'}, set()),
            'create_mission': ({'mission_id', 'goal'}, {'agent_id', 'parent_id', 'priority'}),
            'claim_mission': ({'mission_id', 'agent_id'}, {'lease_seconds'}),
            'complete_mission': ({'mission_id', 'agent_id', 'lease_token', 'evidence'}, {'lesson'}),
            'fail_mission': ({'mission_id', 'agent_id', 'lease_token', 'reason'}, {'lesson'}),
            'record_lesson': ({'agent_id', 'lesson'}, {'mission_id', 'tags'}),
            'review': ({'reviewer', 'subject', 'digest', 'verdict'}, {'notes', 'host_turn', 'host_provider'}),
            'message': ({'from_agent', 'to_agent', 'body'}, set()),
            'transfer_glc': ({'from_agent', 'to_agent', 'amount'}, set()),
            'reward_glc': ({'agent_id', 'amount', 'evidence'}, set()),
            'set_policy': ({'maintenance_glc', 'interest_basis_points'}, set()),
            'cycle': ({'cycle_id'}, set()), 'extinguish': ({'reason'}, set()),
            'raise_blocker': ({'blocker_id', 'agent_id', 'title', 'category', 'needs_founder', 'detail'}, {'mission_id', 'expected_gain'}),
            'resolve_blocker': ({'blocker_id', 'agent_id', 'resolution'}, set())}
        op = a.get('op')
        if not isinstance(op, str) or op not in fields:
            raise ValueError('Unknown operation')
        required, optional = fields[op]
        if not required <= a.keys() or a.keys() - required - optional - {'op'}:
            raise ValueError('Invalid operation fields')
        if op == 'register_agent':
            return self._register(s, a['agent_id'], a['role'])
        if op == 'create_mission':
            mid = self._id(a['mission_id'])
            if any(m['mission_id'] == mid for m in s['missions']) or mid in s.get('retired_missions', []):
                raise ValueError('Mission already exists')
            self._text(a['goal'], 'goal', 10000)
            if a.get('parent_id') is not None:
                self._find(s['missions'], 'mission_id', self._id(a['parent_id']))
            if a.get('agent_id') is not None:
                self._agent(s, a['agent_id'], True)
            m = dict(mission_id=mid, goal=a['goal'], parent_id=a.get('parent_id'),
                     agent_id=a.get('agent_id'), priority=self._integer(a.get('priority', 0), 10000),
                     status='OPEN', lease_token=None, lease_expires_at=None, evidence=[])
            s['missions'].append(m)
            self._event(s, 'MISSION_CREATED', mission_id=mid)
            return m
        if op in ('claim_mission', 'complete_mission', 'fail_mission'):
            m = self._find(s['missions'], 'mission_id', self._id(a['mission_id']))
            self._agent(s, a['agent_id'], True)
            now = self.clock()
            if op == 'claim_mission':
                seconds = self._integer(a.get('lease_seconds', 300), 3600)
                if seconds == 0 or m['status'] not in ('OPEN', 'RUNNING') or (m['lease_token'] and m['lease_expires_at'] > now):
                    raise ValueError('Mission unavailable')
                m.update(agent_id=a['agent_id'], status='RUNNING', lease_token=secrets.token_urlsafe(24), lease_expires_at=now + seconds)
            else:
                self._text(a['lease_token'], 'lease token', 128)
                if m['status'] != 'RUNNING' or m['agent_id'] != a['agent_id'] or m['lease_token'] != a['lease_token'] or m['lease_expires_at'] <= now:
                    raise ValueError('Invalid or expired lease')
                if op == 'complete_mission':
                    m['evidence'] = self._evidence(a['evidence'])
                    m['status'] = 'COMPLETED'
                else:
                    m['reason'] = self._text(a['reason'], 'reason')
                    m['status'] = 'FAILED'
                m.update(lease_token=None, lease_expires_at=None)
                if a.get('lesson') is not None:
                    self._lesson(s, a['agent_id'], a['lesson'], m['mission_id'], [], m['status'])
            self._event(s, op.upper(), mission_id=m['mission_id'], agent_id=a['agent_id'])
            return m
        if op == 'message':
            self._agent(s, a['from_agent'], True)
            self._agent(s, a['to_agent'])
            msg = dict(from_agent=a['from_agent'], to_agent=a['to_agent'], body=self._text(a['body'], 'body', 10000), timestamp=self.clock())
            s['messages'].append(msg)
            self._event(s, 'MESSAGE', from_agent=a['from_agent'], to_agent=a['to_agent'])
            return msg
        if op == 'transfer_glc':
            src = self._agent(s, a['from_agent'], True)
            dst = self._agent(s, a['to_agent'], True)
            amount = self._integer(a['amount'])
            if src is dst or src['wallet_glc'] < amount:
                raise ValueError('Invalid transfer or insufficient GLC')
            src['wallet_glc'] -= amount
            dst['wallet_glc'] += amount
            self._event(s, 'GLC_TRANSFER', from_agent=a['from_agent'], to_agent=a['to_agent'], amount=amount)
            return dict(transferred_glc=amount)
        if op == 'reward_glc':
            agent = self._agent(s, a['agent_id'], True)
            amount = self._integer(a['amount'])
            evidence = self._evidence(a['evidence'])
            agent['wallet_glc'] += amount
            self._event(s, 'GLC_ISSUANCE', agent_id=a['agent_id'], amount=amount, reason='virtual reward', evidence=evidence)
            return dict(issued_glc=amount)
        if op == 'set_policy':
            s['policy'] = {k: self._integer(a[k], 10000) for k in ('maintenance_glc', 'interest_basis_points')}
            self._event(s, 'POLICY_CHANGED', **s['policy'])
            return s['policy']
        if op == 'cycle':
            cid = self._id(a['cycle_id'])
            if cid in s['cycles']:
                return dict(cycle_id=cid, applied=False)
            for agent in s['agents']:
                if agent['status'] != 'ACTIVE':
                    continue
                interest = (agent['debt_glc'] * s['policy']['interest_basis_points'] + 9999) // 10000
                maintenance = min(agent['wallet_glc'], s['policy']['maintenance_glc'])
                agent['debt_glc'] += interest
                agent['wallet_glc'] -= maintenance
                self._event(s, 'GLC_CYCLE', agent_id=agent['agent_id'], interest_glc=interest, maintenance_glc=maintenance)
                if agent['wallet_glc'] == 0:
                    agent['status'] = 'DISABLED'
                    for m in s['missions']:
                        if m['agent_id'] == agent['agent_id'] and m['status'] in ('OPEN', 'RUNNING'):
                            m.update(agent_id=None, status='OPEN', lease_token=None, lease_expires_at=None)
                    self._event(s, 'AGENT_DISABLED', agent_id=agent['agent_id'])
            s['cycles'].append(cid)
            return dict(cycle_id=cid, applied=True)
        if op == 'review':
            # Producer and auditor are never the same agent: the host checks the
            # author against the reviewer where a review gates an effect.
            if a.get('host_provider') == 'FOUNDER':
                if a['reviewer'] != 'FOUNDER':
                    raise ValueError('Invalid founder review')
            else:
                self._agent(s, a['reviewer'], True)
            if not isinstance(a['subject'], str) or not re.fullmatch(r'(actor|site|mission):[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}', a['subject']):
                raise ValueError('Invalid review subject')
            if not isinstance(a['digest'], str) or not re.fullmatch(r'[0-9a-f]{64}', a['digest']):
                raise ValueError('Invalid review digest')
            if a['verdict'] not in ('APPROVE', 'NEEDS_WORK'):
                raise ValueError('Invalid review verdict')
            reviews = s.setdefault('reviews', [])
            review = dict(reviewer=a['reviewer'], subject=a['subject'], digest=a['digest'], verdict=a['verdict'],
                          notes=self._text(a['notes'], 'notes', 2000) if a.get('notes') is not None else None,
                          host_turn=a.get('host_turn'), host_provider=a.get('host_provider'),
                          at=self.clock(), seq=len(reviews) and reviews[-1]['seq'] + 1 or 1)
            reviews.append(review)
            del reviews[:-500]
            self._event(s, 'REVIEW_RECORDED', reviewer=a['reviewer'], subject=a['subject'], verdict=a['verdict'])
            return review
        if op == 'record_lesson':
            self._agent(s, a['agent_id'], True)
            mission = None
            if a.get('mission_id') is not None:
                mission = self._find(s['missions'], 'mission_id', self._id(a['mission_id']))['mission_id']
            return self._lesson(s, a['agent_id'], a['lesson'], mission, a.get('tags') or [], None)
        if op == 'raise_blocker':
            return self._raise_blocker(s, a)
        if op == 'resolve_blocker':
            blockers = s.setdefault('blockers', [])
            self._agent(s, a['agent_id'], True)
            b = self._find(blockers, 'blocker_id', self._id(a['blocker_id']))
            if b['status'] != 'OPEN':
                raise ValueError('Blocker already resolved')
            b.update(status='RESOLVED', resolution=self._text(a['resolution'], 'resolution', 2000),
                     resolved_by=a['agent_id'], resolved_at=self.clock())
            self._event(s, 'BLOCKER_RESOLVED', blocker_id=b['blocker_id'], agent_id=a['agent_id'])
            return b
        if op == 'extinguish':
            reason = self._text(a['reason'], 'reason')
            s['state'] = 'EXTINCT'
            self._event(s, 'WORLD_EXTINCT', reason=reason)
            return dict(state='EXTINCT', reason=reason)

    MAX_LESSONS = 300

    def _lesson(self, s, agent_id, text, mission_id, tags, outcome):
        """Durable learning; the controller injects relevant lessons into prompts."""
        if type(tags) is not list or len(tags) > 8:
            raise ValueError('Invalid tags')
        tags = [self._text(t, 'tag', 40) for t in tags]
        lessons = s.setdefault('lessons', [])
        s['lesson_seq'] = s.get('lesson_seq', 0) + 1
        lesson = dict(lesson_id='L%d' % s['lesson_seq'], agent_id=agent_id, mission_id=mission_id,
                      outcome=outcome, text=self._text(text, 'lesson', 1000), tags=tags, at=self.clock())
        lessons.append(lesson)
        del lessons[:-self.MAX_LESSONS]
        self._event(s, 'LESSON_RECORDED', lesson_id=lesson['lesson_id'], agent_id=agent_id)
        return lesson

    def reviews(self):
        with self._connect() as db:
            s = json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
        return s.get('reviews', [])

    def lessons(self):
        with self._connect() as db:
            s = json.loads(db.execute('SELECT data FROM world WHERE id=1').fetchone()[0])
        return s.get('lessons', [])

    BLOCKER_CATEGORIES = ('ACCOUNT', 'CREDENTIAL', 'IDENTITY', 'PAYMENT', 'DECISION', 'CAPABILITY', 'OTHER')

    def _raise_blocker(self, s, a):
        """Record once what prevents progress; repeated reports update the card."""
        blockers = s.setdefault('blockers', [])
        self._agent(s, a['agent_id'], True)
        bid = self._id(a['blocker_id'])
        if a['category'] not in self.BLOCKER_CATEGORIES:
            raise ValueError('Invalid blocker category')
        if type(a['needs_founder']) is not bool:
            raise ValueError('needs_founder must be boolean')
        fields = dict(title=self._text(a['title'], 'title', 200), category=a['category'],
                      needs_founder=a['needs_founder'], detail=self._text(a['detail'], 'detail', 2000),
                      mission_id=None, expected_gain=None)
        if a.get('mission_id') is not None:
            fields['mission_id'] = self._find(s['missions'], 'mission_id', self._id(a['mission_id']))['mission_id']
        if a.get('expected_gain') is not None:
            fields['expected_gain'] = self._text(a['expected_gain'], 'expected gain', 500)
        now = self.clock()
        b = next((x for x in blockers if x['blocker_id'] == bid), None)
        if b is None:
            if sum(1 for x in blockers if x['status'] == 'OPEN') >= 50:
                raise ValueError('Too many open blockers; resolve or merge existing ones')
            b = dict(blocker_id=bid, status='OPEN', raised_by=a['agent_id'], opened_at=now, reports=0)
            blockers.append(b)
            # Keep every open card; forget the oldest resolved ones beyond 200.
            resolved = [x for x in blockers if x['status'] != 'OPEN']
            for old in resolved[:max(0, len(blockers) - 200)]:
                blockers.remove(old)
        elif b['status'] != 'OPEN':
            b.update(status='OPEN', opened_at=now, reports=0)
            for key in ('resolution', 'resolved_by', 'resolved_at'):
                b.pop(key, None)
        b.update(fields, last_reported_by=a['agent_id'], last_reported_at=now, reports=b['reports'] + 1)
        self._event(s, 'BLOCKER_RAISED', blocker_id=bid, agent_id=a['agent_id'])
        return b

    def _evidence(self, evidence):
        if type(evidence) is not list or not 1 <= len(evidence) <= 100:
            raise ValueError('Evidence references required')
        return [self._text(item, 'evidence reference', 4000) for item in evidence]
