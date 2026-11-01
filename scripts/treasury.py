"""Local durable CAD-cent accounting. No payment or network capability."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


MAX_CENTS = 2**63 - 1


def _amount(value):
    if type(value) is not int or not 0 <= value <= MAX_CENTS:
        raise ValueError('amount must be bounded nonnegative integer cents')
    return value


def _identity(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 1024:
        raise ValueError('nonempty bounded identity required')
    return value


class Treasury:
    def __init__(self, db_path, verifier=None):
        self.db_path = Path(db_path)
        self.verifier = verifier
        with self._tx() as db:
            schema = '''
                CREATE TABLE IF NOT EXISTS treasury (
                    id INTEGER PRIMARY KEY CHECK(id=1), cash INTEGER NOT NULL DEFAULT 0,
                    positions INTEGER NOT NULL DEFAULT 0, funded INTEGER NOT NULL DEFAULT 0,
                    state TEXT NOT NULL DEFAULT 'UNFUNDED', reason TEXT);
                INSERT OR IGNORE INTO treasury(id) VALUES(1);
                CREATE TABLE IF NOT EXISTS operations (
                    id TEXT PRIMARY KEY, amount INTEGER NOT NULL, request_hash TEXT NOT NULL,
                    agent TEXT NOT NULL, status TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS positions (
                    provider TEXT NOT NULL, account TEXT NOT NULL, asset TEXT NOT NULL,
                    value_cents INTEGER NOT NULL, event_id TEXT NOT NULL,
                    PRIMARY KEY(provider,account,asset));
                CREATE TABLE IF NOT EXISTS events (
                    provider TEXT, account TEXT, event_id TEXT, digest TEXT NOT NULL,
                    body TEXT NOT NULL, action TEXT NOT NULL, operation_id TEXT,
                    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(provider,account,event_id),
                    FOREIGN KEY(operation_id) REFERENCES operations(id));
            '''
            for statement in schema.split(';'):
                if statement.strip():
                    db.execute(statement)
            columns = {row['name'] for row in db.execute('PRAGMA table_info(treasury)')}
            if 'pending_sync' not in columns:
                db.execute('ALTER TABLE treasury ADD COLUMN pending_sync INTEGER NOT NULL DEFAULT 0')
            if 'earned' not in columns:
                # Verified settled revenue may exist before the initial deposit.
                db.execute('ALTER TABLE treasury ADD COLUMN earned INTEGER NOT NULL DEFAULT 0')
            if 'revenue' not in columns:
                # Cumulative verified REVENUE only (refunds and funding excluded).
                db.execute('ALTER TABLE treasury ADD COLUMN revenue INTEGER NOT NULL DEFAULT 0')
            if 'positions_migrated' not in columns:
                # v3 kept one overwritten scalar. Preserve any nonzero legacy value
                # under its own key: it is never silently dropped toward extinction.
                db.execute('ALTER TABLE treasury ADD COLUMN positions_migrated INTEGER NOT NULL DEFAULT 0')
            legacy = db.execute('SELECT positions, positions_migrated FROM treasury WHERE id=1').fetchone()
            if not legacy['positions_migrated']:
                if legacy['positions']:
                    db.execute("INSERT OR IGNORE INTO positions VALUES('legacy','aggregate','',?,'legacy-scalar')", (legacy['positions'],))
                db.execute('UPDATE treasury SET positions_migrated=1 WHERE id=1')

    @contextmanager
    def _tx(self):
        db = sqlite3.connect(str(self.db_path), timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA busy_timeout=30000')
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _view(self, db):
        row = db.execute('SELECT * FROM treasury WHERE id=1').fetchone()
        held = db.execute("SELECT COALESCE(SUM(amount),0) FROM operations WHERE status IN ('HELD','UNKNOWN')").fetchone()[0]
        positions = db.execute('SELECT COALESCE(SUM(value_cents),0) FROM positions').fetchone()[0]
        return dict(state=row['state'], declared_capital_cents=5000,
                    cash_cents=row['cash'], reserved_cents=held,
                    available_cents=row['cash']-held if row['state'] == 'ACTIVE' else 0, funding_verified=bool(row['funded']),
                    revenue_verified=bool(row['earned']), revenue_cents=row['revenue'],
                    position_cents=positions, extinction_reason=row['reason'])

    @staticmethod
    def _capital_verified(view):
        return view['funding_verified'] or view['revenue_verified']

    def snapshot(self):
        with self._tx() as db:
            return self._view(db)

    def _alive(self, db):
        if self._view(db)['state'] == 'EXTINCT':
            raise ValueError('extinction is terminal')

    def _finish(self, db):
        v = self._view(db)
        if v['funding_verified'] and v['state'] != 'EXTINCT' and not db.execute('SELECT pending_sync FROM treasury WHERE id=1').fetchone()[0]:
            if v['cash_cents'] == 0 and v['position_cents'] == 0 and not db.execute("SELECT 1 FROM operations WHERE status IN ('HELD','UNKNOWN')").fetchone():
                db.execute("UPDATE treasury SET state='EXTINCT', reason=CASE WHEN reason IS NULL THEN 'verified owned cash and positions exhausted' ELSE reason || '; verified owned cash and positions exhausted' END WHERE id=1")
        return self._view(db)

    def _evidence(self, db, receipt, kinds, action, op=None):
        if not isinstance(receipt, dict): raise ValueError('receipt required')
        for key in ('provider', 'account', 'event_id'): _identity(receipt.get(key))
        _amount(receipt.get('amount_cents'))
        if receipt.get('currency') != 'CAD' or receipt.get('kind') not in kinds or receipt.get('settled') is not True:
            raise ValueError('invalid settled CAD evidence')
        try:
            body = json.dumps(receipt, sort_keys=True, separators=(',', ':'), allow_nan=False)
        except (TypeError, ValueError):
            raise ValueError('receipt must be JSON evidence') from None
        digest = hashlib.sha256(body.encode()).hexdigest()
        key = tuple(receipt[k] for k in ('provider', 'account', 'event_id'))
        prior = db.execute('SELECT * FROM events WHERE provider=? AND account=? AND event_id=?', key).fetchone()
        if prior:
            if prior['digest'] != digest or prior['action'] != action or prior['operation_id'] != op:
                raise ValueError('event replay changed evidence or use')
            return False
        if self.verifier is None or self.verifier(dict(receipt)) is not True:
            raise ValueError('trusted receipt verification required')
        db.execute('INSERT INTO events(provider,account,event_id,digest,body,action,operation_id) VALUES(?,?,?,?,?,?,?)', (*key, digest, body, action, op))
        return True

    def _apply_account_receipt(self, db, receipt):
        if not isinstance(receipt, dict):
            raise ValueError('receipt required')
        kind = receipt.get('kind')
        if kind == 'FUNDING':
            if self._evidence(db, receipt, {'FUNDING'}, 'FUNDING'):
                if self._view(db)['funding_verified'] or receipt['amount_cents'] != 5000:
                    raise ValueError('initial funding must be exactly 5000 cents once')
                db.execute("UPDATE treasury SET cash=cash+5000, funded=1, state=CASE WHEN state='HALTED' THEN state ELSE 'ACTIVE' END WHERE id=1")
        elif kind in ('REVENUE', 'REFUND'):
            if self._evidence(db, receipt, {'REVENUE', 'REFUND'}, 'CREDIT'):
                v = self._view(db)
                amount = receipt['amount_cents']
                if amount == 0 or v['cash_cents'] + amount > MAX_CENTS:
                    raise ValueError('invalid credit')
                # Settled external revenue is owned capital even before the
                # optional initial deposit. It never implies that deposit.
                db.execute("UPDATE treasury SET cash=cash+?, earned=1, revenue=revenue+?, state=CASE WHEN state='UNFUNDED' THEN 'ACTIVE' ELSE state END WHERE id=1",
                           (amount, amount if receipt['kind'] == 'REVENUE' else 0))
        elif kind == 'POSITIONS':
            if self._evidence(db, receipt, {'POSITIONS'}, 'POSITIONS'):
                v = self._view(db)
                if not self._capital_verified(v): raise ValueError('verified capital required')
                self._set_position(db, receipt)
                after = self._view(db)
                if v['position_cents'] > 0 and after['position_cents'] == 0 and v['cash_cents'] == 0:
                    db.execute("UPDATE treasury SET pending_sync=1, state=CASE WHEN state='HALTED' THEN state ELSE 'RECONCILING' END WHERE id=1")
        else:
            raise ValueError('unsupported account receipt kind')

    def _set_position(self, db, receipt):
        """A POSITIONS receipt values one (provider, account, asset) holding.

        Distinct accounts and assets are summed, never overwritten by each other.
        Without `asset`, the receipt values the whole account; an account is
        valued either as a whole or per asset, never both, to avoid double counting.
        """
        asset = receipt.get('asset', '')
        if not isinstance(asset, str) or len(asset) > 256 or (asset and not asset.strip()):
            raise ValueError('position asset must be a bounded identifier')
        provider, account = receipt['provider'], receipt['account']
        # The migrated v3 scalar was 'the latest reported total'. Any new
        # verified valuation supersedes it, as the old overwrite did.
        db.execute("DELETE FROM positions WHERE provider='legacy' AND account='aggregate' AND event_id='legacy-scalar'")
        other = db.execute("SELECT 1 FROM positions WHERE provider=? AND account=? AND (asset='') != (?='')",
                           (provider, account, asset)).fetchone()
        if other:
            raise ValueError('account positions must be valued either whole or per asset')
        db.execute('INSERT INTO positions VALUES(?,?,?,?,?) ON CONFLICT(provider,account,asset) '
                   'DO UPDATE SET value_cents=excluded.value_cents, event_id=excluded.event_id',
                   (provider, account, asset, receipt['amount_cents'], receipt['event_id']))

    def _account_receipt(self, receipt, kinds):
        if not isinstance(receipt, dict) or receipt.get('kind') not in kinds:
            raise ValueError('unexpected receipt kind')
        with self._tx() as db:
            self._alive(db)
            self._apply_account_receipt(db, receipt)
            return self._finish(db)

    def confirm_funding(self, receipt):
        return self._account_receipt(receipt, {'FUNDING'})

    def sync_receipts(self, receipts, complete=False):
        """Apply account evidence atomically; complete is a trusted adapter assertion.

        A complete sync must represent all current owned cash, executable positions,
        and incoming events. Call only from the installed trusted account adapter.
        """
        if not isinstance(receipts, list) or type(complete) is not bool:
            raise ValueError('receipt list and boolean completeness required')
        if complete and self.verifier is None:
            raise ValueError('trusted account integration required for complete sync')
        with self._tx() as db:
            self._alive(db)
            # Funding is applied first so a single initial account snapshot can
            # contain positions and revenue without imposing provider order.
            ordered = sorted(receipts, key=lambda r: 0 if isinstance(r, dict) and r.get('kind') == 'FUNDING' else 1)
            for receipt in ordered:
                self._apply_account_receipt(db, receipt)
            if complete:
                db.execute("UPDATE treasury SET pending_sync=0, state=CASE WHEN state='RECONCILING' THEN 'ACTIVE' ELSE state END WHERE id=1")
            return self._finish(db)

    def reserve(self, operation_id, max_debit_cents, request_hash, agent_id='DIRECTOR'):
        _identity(operation_id); _identity(request_hash); _identity(agent_id); _amount(max_debit_cents)
        with self._tx() as db:
            self._alive(db)
            previous = db.execute('SELECT * FROM operations WHERE id=?', (operation_id,)).fetchone()
            if previous:
                if (previous['amount'], previous['request_hash'], previous['agent']) != (max_debit_cents, request_hash, agent_id):
                    raise ValueError('operation identity changed')
                return dict(previous, idempotency_key=operation_id)
            v = self._view(db)
            if max_debit_cents and (v['state'] != 'ACTIVE' or not self._capital_verified(v) or max_debit_cents > v['available_cents']):
                raise ValueError('insufficient verified available capital')
            db.execute("INSERT INTO operations VALUES(?,?,?,?,'HELD')", (operation_id, max_debit_cents, request_hash, agent_id))
            return dict(id=operation_id, amount=max_debit_cents, request_hash=request_hash, agent=agent_id, status='HELD', idempotency_key=operation_id)

    def _operation(self, db, operation_id):
        _identity(operation_id)
        row = db.execute('SELECT * FROM operations WHERE id=?', (operation_id,)).fetchone()
        if row is None: raise ValueError('unknown operation')
        return row

    def mark_submitted(self, operation_id):
        with self._tx() as db:
            self._alive(db)
            op = self._operation(db, operation_id)
            if op['status'] not in ('HELD', 'UNKNOWN'): raise ValueError('operation already resolved')
            state = self._view(db)['state']
            if state == 'HALTED' or (op['amount'] and state != 'ACTIVE'): raise ValueError('treasury frozen')
            db.execute("UPDATE operations SET status='UNKNOWN' WHERE id=?", (operation_id,))
            return dict(idempotency_key=operation_id, status='UNKNOWN')

    def settle(self, operation_id, receipt):
        with self._tx() as db:
            op = self._operation(db, operation_id)
            if not self._evidence(db, receipt, {'SPEND'}, 'SPEND', operation_id): return self._view(db)
            self._alive(db)
            if op['status'] != 'UNKNOWN': raise ValueError('operation must be submitted')
            amount = receipt['amount_cents']
            cash = self._view(db)['cash_cents'] - amount
            if not -MAX_CENTS <= cash <= MAX_CENTS: raise ValueError('cash outside accounting range')
            db.execute('UPDATE treasury SET cash=? WHERE id=1', (cash,))
            db.execute("UPDATE operations SET status='SETTLED' WHERE id=?", (operation_id,))
            if amount > op['amount']:
                db.execute("UPDATE treasury SET state='HALTED', reason='verified adapter overcharge' WHERE id=1")
            return self._finish(db)

    def release(self, operation_id, receipt=None):
        with self._tx() as db:
            op = self._operation(db, operation_id)
            if receipt is None:
                if op['amount'] != 0 or op['status'] != 'HELD': raise ValueError('verified cancellation required')
            else:
                if not self._evidence(db, receipt, {'CANCELLED'}, 'CANCELLED', operation_id): return self._view(db)
                if receipt['amount_cents'] != 0: raise ValueError('cancellation must have zero debit')
            self._alive(db)
            if op['status'] not in ('HELD', 'UNKNOWN'): raise ValueError('operation already resolved')
            db.execute("UPDATE operations SET status='RELEASED' WHERE id=?", (operation_id,))
            return self._finish(db)

    def credit(self, receipt):
        return self._account_receipt(receipt, {'REVENUE', 'REFUND'})

    def record_positions(self, receipt):
        return self._account_receipt(receipt, {'POSITIONS'})
