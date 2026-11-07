"""Local durable CAD-cent accounting. No payment or network capability."""
import hashlib
import json
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


MAX_CENTS = 2**63 - 1
JOURNAL_FIELDS = ('known_funding_cents', 'known_revenue_credits_cents',
                  'known_spend_debits_cents', 'known_expense_refunds_cents',
                  'known_customer_reversals_cents')


def unavailable_journal():
    return dict(state='UNAVAILABLE', history_coverage=None, coverage_reason='HISTORY_UNAVAILABLE',
                **dict.fromkeys(JOURNAL_FIELDS))


def _amount(value):
    if type(value) is not int or not 0 <= value <= MAX_CENTS:
        raise ValueError('amount must be bounded nonnegative integer cents')
    return value


def _identity(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 1024:
        raise ValueError('nonempty bounded identity required')
    return value


class Treasury:
    def __init__(self, db_path, verifier=None, clock=None):
        self.db_path = Path(db_path)
        self.verifier = verifier
        self.clock = clock or time.time
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
                CREATE TABLE IF NOT EXISTS credits (
                    provider TEXT NOT NULL, account TEXT NOT NULL, event_id TEXT NOT NULL,
                    amount INTEGER NOT NULL, available_at INTEGER NOT NULL,
                    PRIMARY KEY(provider,account,event_id));
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
            if 'attested' not in columns:
                # Revenue proven by the founder's attestation rather than by an
                # automated provider check: reported separately, never hidden.
                db.execute('ALTER TABLE treasury ADD COLUMN attested INTEGER NOT NULL DEFAULT 0')
            if 'reserve_floor' not in columns:
                # Owned cash never committed: covers customer refunds/disputes a
                # merchant of record could otherwise claim from the founder.
                db.execute('ALTER TABLE treasury ADD COLUMN reserve_floor INTEGER NOT NULL DEFAULT 0')
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
        now = int(self.clock())
        maturing, next_at = db.execute('SELECT COALESCE(SUM(amount),0), MIN(available_at) FROM credits WHERE available_at > ? AND amount > 0', (now,)).fetchone()
        floor = row['reserve_floor']
        # Owned but not yet spendable: revenue still inside its refund window or
        # unpaid by the provider, plus the configured reserve floor.
        spendable = row['cash'] - held - maturing - floor
        return dict(state=row['state'], declared_capital_cents=5000,
                    cash_cents=row['cash'], reserved_cents=held,
                    available_cents=max(spendable, 0) if row['state'] == 'ACTIVE' else 0, funding_verified=bool(row['funded']),
                    revenue_verified=bool(row['earned']), revenue_cents=row['revenue'],
                    founder_attested_revenue_cents=row['attested'],
                    maturing_cents=maturing, next_maturity_at=next_at, reserve_floor_cents=floor,
                    position_cents=positions, extinction_reason=row['reason'])

    @staticmethod
    def _capital_verified(view):
        return view['funding_verified'] or view['revenue_verified']

    def snapshot(self):
        with self._tx() as db:
            return self._view(db)

    def economic_snapshot(self):
        """Known admitted flows, commitments and authority from one read-only view.

        Consistent history is never proof of completeness: older databases have
        no genesis marker. Optional history errors cannot change cash authority.
        """
        db = sqlite3.connect(self.db_path.resolve().as_uri() + '?mode=ro', uri=True,
                             timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute('BEGIN')
            snapshot = self._view(db)  # Authoritative failures still propagate.
            journal = unavailable_journal()
            commitments = dict(state='UNAVAILABLE', held_cents=None, unknown_cents=None)
            try:
                operations = {}
                held = unknown = 0
                for row in db.execute('SELECT id,amount,status FROM operations'):
                    _identity(row['id']); _amount(row['amount'])
                    if row['status'] not in ('HELD', 'UNKNOWN', 'SETTLED', 'RELEASED'):
                        raise ValueError('invalid operation status')
                    operations[row['id']] = row
                    if row['status'] == 'HELD': held += row['amount']
                    if row['status'] == 'UNKNOWN': unknown += row['amount']
                commitments = dict(state='AVAILABLE', held_cents=held, unknown_cents=unknown)
                journal = self._economic_journal(db, snapshot, operations)
            except (sqlite3.Error, ValueError, TypeError, KeyError, OverflowError, RecursionError):
                # Never publish private bodies or free-form exception details.
                pass
            return dict(snapshot=snapshot, journal=journal, commitments=commitments)
        finally:
            db.close()

    @staticmethod
    def _economic_journal(db, snapshot, operations):
        totals = dict.fromkeys(JOURNAL_FIELDS, 0)
        kinds = {'FUNDING': ('FUNDING', JOURNAL_FIELDS[0]),
                 'REVENUE': ('CREDIT', JOURNAL_FIELDS[1]),
                 'SPEND': ('SPEND', JOURNAL_FIELDS[2]),
                 'REFUND': ('CREDIT', JOURNAL_FIELDS[3]),
                 'REVERSAL': ('DEBIT', JOURNAL_FIELDS[4]),
                 'POSITIONS': ('POSITIONS', None), 'CANCELLED': ('CANCELLED', None)}
        resolved = set()
        for row in db.execute('SELECT provider,account,event_id,digest,body,action,operation_id FROM events'):
            receipt = json.loads(row['body'])
            if not isinstance(receipt, dict):
                raise ValueError('invalid history receipt')
            for key in ('provider', 'account', 'event_id'):
                if _identity(receipt.get(key)) != row[key]:
                    raise ValueError('history identity mismatch')
            amount = _amount(receipt.get('amount_cents'))
            kind = receipt.get('kind')
            if (not isinstance(kind, str) or kind not in kinds or receipt.get('currency') != 'CAD'
                    or receipt.get('settled') is not True or row['action'] != kinds[kind][0]):
                raise ValueError('invalid history kind or action')
            body = json.dumps(receipt, sort_keys=True, separators=(',', ':'), allow_nan=False)
            if hashlib.sha256(body.encode()).hexdigest() != row['digest']:
                raise ValueError('history digest mismatch')
            if ((kind == 'FUNDING' and amount != 5000)
                    or (kind in ('REVENUE', 'REFUND', 'REVERSAL') and amount == 0)
                    or (kind == 'CANCELLED' and amount != 0)):
                raise ValueError('invalid history amount')
            op = row['operation_id']
            if kind in ('SPEND', 'CANCELLED'):
                _identity(op)
                status = 'SETTLED' if kind == 'SPEND' else 'RELEASED'
                if op not in operations or operations[op]['status'] != status or op in resolved:
                    raise ValueError('history operation mismatch')
                resolved.add(op)
            elif op is not None:
                raise ValueError('unexpected history operation')
            field = kinds[kind][1]
            if field is not None:
                totals[field] += amount  # Lifetime totals may exceed SQLite int64.
        funding, revenue, spend, refunds, reversals = (totals[field] for field in JOURNAL_FIELDS)
        incomplete = ((snapshot['funding_verified'] and funding == 0)
                      or any(op['status'] == 'SETTLED' and key not in resolved for key, op in operations.items())
                      or funding + revenue + refunds - spend - reversals != snapshot['cash_cents'])
        return dict(state='AVAILABLE', history_coverage='INCOMPLETE' if incomplete else 'UNKNOWN',
                    coverage_reason='KNOWN_HISTORY_INCOMPLETE' if incomplete else 'NO_COMPLETENESS_MARKER', **totals)

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
        self._payout_settlement(db, receipt)
        self._bank_settlement(db, receipt)
        prior = db.execute('SELECT * FROM events WHERE provider=? AND account=? AND event_id=?', key).fetchone()
        if prior:
            if prior['digest'] != digest or prior['action'] != action or prior['operation_id'] != op:
                raise ValueError('event replay changed evidence or use')
            return False
        if self.verifier is None or self.verifier(dict(receipt)) is not True:
            raise ValueError('trusted receipt verification required')
        db.execute('INSERT INTO events(provider,account,event_id,digest,body,action,operation_id) VALUES(?,?,?,?,?,?,?)', (*key, digest, body, action, op))
        return True

    @staticmethod
    def _payout_settlement(db, receipt):
        """One founder-attested transfer, independent of its invoice assignment.

        Legacy receipts already contain the canonical reference digest. Inspect
        them inside the credit transaction rather than rewriting their IDs or
        evidence. A second invoice assignment requires explicit reconciliation;
        rejecting it also keeps that invoice from being falsely marked PAID.
        """
        if (receipt['provider'], receipt['account'], receipt.get('kind'), receipt.get('attestation')) != (
                'apify', 'payouts', 'REVENUE', 'FOUNDER'):
            return
        reference = receipt.get('reference_sha256')
        if not isinstance(reference, str) or not re.fullmatch(r'[0-9a-f]{64}', reference):
            raise ValueError('canonical payout settlement reference required')
        matches = []
        for row in db.execute("SELECT * FROM events WHERE provider='apify' AND account='payouts'"):
            try:
                previous = json.loads(row['body'])
                if not isinstance(previous, dict):
                    raise ValueError('invalid payout history')
                body = json.dumps(previous, sort_keys=True, separators=(',', ':'), allow_nan=False)
                if (hashlib.sha256(body.encode()).hexdigest() != row['digest']
                        or any(previous.get(k) != row[k] for k in ('provider', 'account', 'event_id'))):
                    raise ValueError('invalid payout history')
                if previous.get('kind') == 'REVENUE' and previous.get('attestation') == 'FOUNDER':
                    prior_reference = previous.get('reference_sha256')
                    if (not isinstance(prior_reference, str) or not re.fullmatch(r'[0-9a-f]{64}', prior_reference)
                            or row['action'] != 'CREDIT' or row['operation_id'] is not None):
                        raise ValueError('incomplete payout settlement history')
            except (TypeError, ValueError):
                raise ValueError('payout history requires reconciliation') from None
            if previous.get('reference_sha256') == reference:
                matches.append(row['event_id'])
        if len(matches) > 1:
            raise ValueError('duplicate legacy payout settlement requires reconciliation')
        if matches and matches[0] != receipt['event_id']:
            raise ValueError('payout settlement already assigned to another invoice; reconcile allocations explicitly')

    @staticmethod
    def _bank_settlement(db, receipt):
        """Reject a known bank transfer reused across orders and Apify BANK.

        Legacy Apify receipts omit the destination account and preserve case in
        their reference digest, while orders canonicalizes case. Equal digests
        prove a collision across these adapters, conservatively regardless of
        account alias. Unequal legacy digests cannot prove distinct transfers:
        the original reference is unavailable, so case variants still require
        private reconciliation. Never rewrite historical evidence or claim
        universal matching. WISE/PAYPAL remain in their separate namespaces.
        """
        def bank_receipt(value):
            return (value.get('kind') == 'REVENUE' and value.get('attestation') == 'FOUNDER'
                    and (value.get('provider') == 'orders'
                         or (value.get('provider') == 'apify' and value.get('account') == 'payouts'
                             and value.get('method') == 'BANK')))

        if not bank_receipt(receipt): return
        reference = receipt.get('reference_sha256')
        if not isinstance(reference, str) or not re.fullmatch(r'[0-9a-f]{64}', reference):
            raise ValueError('bank settlement reference digest required')
        other_provider = 'apify' if receipt['provider'] == 'orders' else 'orders'
        for row in db.execute('SELECT * FROM events WHERE provider=?', (other_provider,)):
            try:
                previous = json.loads(row['body'])
                if not isinstance(previous, dict): raise ValueError('invalid bank history')
                body = json.dumps(previous, sort_keys=True, separators=(',', ':'), allow_nan=False)
                if (hashlib.sha256(body.encode()).hexdigest() != row['digest']
                        or any(previous.get(k) != row[k] for k in ('provider', 'account', 'event_id'))):
                    raise ValueError('invalid bank history')
                if not bank_receipt(previous): continue
                prior_reference = previous.get('reference_sha256')
                if (not isinstance(prior_reference, str) or not re.fullmatch(r'[0-9a-f]{64}', prior_reference)
                        or row['action'] != 'CREDIT' or row['operation_id'] is not None):
                    raise ValueError('incomplete bank history')
            except (TypeError, ValueError):
                raise ValueError('bank settlement history requires reconciliation') from None
            if prior_reference == reference:
                raise ValueError('bank settlement already credited through another adapter; reconcile explicitly')

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
                attested = amount if receipt['kind'] == 'REVENUE' and receipt.get('attestation') == 'FOUNDER' else 0
                db.execute("UPDATE treasury SET cash=cash+?, earned=1, revenue=revenue+?, attested=attested+?, state=CASE WHEN state='UNFUNDED' THEN 'ACTIVE' ELSE state END WHERE id=1",
                           (amount, amount if receipt['kind'] == 'REVENUE' else 0, attested))
                available_at = receipt.get('available_at')
                if available_at is not None:
                    # Set by the trusted adapter: the later of the provider payout
                    # and the end of its refund window. Owned now, spendable then.
                    if receipt['kind'] != 'REVENUE' or type(available_at) is not int or not 0 <= available_at <= 9999999999:
                        raise ValueError('available_at must be epoch seconds on REVENUE')
                    db.execute('INSERT INTO credits VALUES(?,?,?,?,?)', (receipt['provider'], receipt['account'], receipt['event_id'], amount, available_at))
        elif kind == 'REVERSAL':
            if self._evidence(db, receipt, {'REVERSAL'}, 'DEBIT'):
                self._reverse(db, receipt)
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

    def _reverse(self, db, receipt):
        """A customer refund or dispute taken back by the provider (a debit).

        It reduces owned cash and verified revenue, and first consumes the
        maturing credit it reverses. If it exceeds owned cash, the provider can
        claim the shortfall from the founder: the bank halts and records it.
        """
        amount = receipt['amount_cents']
        if amount == 0:
            raise ValueError('reversal must debit a positive amount')
        reverses = receipt.get('reverses')
        if reverses is not None:
            _identity(reverses)
            db.execute('UPDATE credits SET amount=MAX(amount-?,0) WHERE provider=? AND account=? AND event_id=?',
                       (amount, receipt['provider'], receipt['account'], reverses))
        cash = self._view(db)['cash_cents'] - amount
        if not -MAX_CENTS <= cash <= MAX_CENTS:
            raise ValueError('cash outside accounting range')
        db.execute('UPDATE treasury SET cash=?, revenue=MAX(revenue-?,0) WHERE id=1', (cash, amount))
        if cash < 0:
            db.execute("UPDATE treasury SET state='HALTED', reason=CASE WHEN reason IS NULL THEN 'verified customer reversal exceeds owned cash' ELSE reason || '; verified customer reversal exceeds owned cash' END WHERE id=1")

    def set_reserve_floor(self, cents):
        """Administrator setting: owned cash that agents may never commit."""
        _amount(cents)
        with self._tx() as db:
            self._alive(db)
            db.execute('UPDATE treasury SET reserve_floor=? WHERE id=1', (cents,))
            return self._view(db)

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
            # Funding first, reversals last: a reversal may consume a credit
            # delivered in the same batch.
            rank = {'FUNDING': 0, 'REVERSAL': 2}
            ordered = sorted(receipts, key=lambda r: rank.get(r.get('kind'), 1) if isinstance(r, dict) else 1)
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

    def reverse(self, receipt):
        return self._account_receipt(receipt, {'REVERSAL'})

    def record_positions(self, receipt):
        return self._account_receipt(receipt, {'POSITIONS'})
