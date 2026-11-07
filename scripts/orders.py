"""Host-private order reconciliation. No payment, network or agent authority.

Only the privileged admin boundary may call mutations. Read-only projections
never initialize storage. Claims are observations; only explicit FOUNDER bank
attestation plus allocation and posting can produce a Treasury receipt.
"""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import uuid


MAX_CENTS = 2**63 - 1
MAX_BYTES = 32 * 1024 * 1024
SCHEMA = '''
CREATE TABLE orders (
 order_id TEXT PRIMARY KEY, case_key TEXT NOT NULL, amount_cents INTEGER NOT NULL,
 currency TEXT NOT NULL, terms_sha256 TEXT NOT NULL, source_id TEXT NOT NULL UNIQUE,
 synthetic INTEGER NOT NULL CHECK(synthetic IN (0,1)), acceptance_source_id TEXT UNIQUE);
CREATE TABLE claims (
 source_id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(order_id),
 amount_cents INTEGER NOT NULL, currency TEXT NOT NULL);
CREATE TABLE deposits (
 deposit_id TEXT PRIMARY KEY, transfer_key TEXT NOT NULL UNIQUE,
 account_sha256 TEXT NOT NULL, reference_sha256 TEXT NOT NULL,
 amount_cents INTEGER NOT NULL, currency TEXT NOT NULL, observed_at TEXT NOT NULL,
 evidence_sha256 TEXT NOT NULL, synthetic INTEGER NOT NULL CHECK(synthetic IN (0,1)),
 order_id TEXT REFERENCES orders(order_id), receipt_json TEXT NOT NULL,
 posting_started INTEGER NOT NULL DEFAULT 0 CHECK(posting_started IN (0,1)),
 posted INTEGER NOT NULL DEFAULT 0 CHECK(posted IN (0,1)));
PRAGMA user_version=1;
'''


def _text(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 512 or any(ord(c) < 32 for c in value):
        raise ValueError('bounded nonempty text required')
    return value


def _amount(value):
    if type(value) is not int or not 0 < value <= MAX_CENTS:
        raise ValueError('positive bounded integer cents required')
    return value


def _currency(value):
    if not isinstance(value, str) or not re.fullmatch('[A-Z]{3}', value):
        raise ValueError('three-letter uppercase currency required')
    return value


def _digest(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('SHA256 digest required')
    return value


def _synthetic(value):
    if type(value) is not bool:
        raise ValueError('boolean synthetic flag required')
    return int(value)


def _observed(value):
    _text(value)
    try:
        timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if timestamp.tzinfo is None: raise ValueError()
        return timestamp.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError):
        raise ValueError('timezone-aware bank observation time required') from None


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _safe_path(path, private=False, directory=False):
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('unsafe private storage path')
    if not path.exists(): return
    info = path.stat()
    if directory:
        valid = stat.S_ISDIR(info.st_mode)
    else:
        valid = stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= MAX_BYTES
    if not valid:
        raise ValueError('unsafe private storage file')
    if os.name != 'nt' and (info.st_uid not in (0, os.geteuid()) or info.st_mode & (0o077 if private else 0o022)):
        raise ValueError('unsafe private storage permissions')


def _storage(root, create=False, name='orders.sqlite3'):
    root = Path(root).absolute()
    _safe_path(root, directory=True)
    state, private = root / 'state', root / 'state/private'
    _safe_path(state, directory=True)
    _safe_path(private, private=True, directory=True)
    if create:
        private.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = private / name
    for suffix in ('', '-journal', '-wal', '-shm'):
        _safe_path(Path(str(path) + suffix), private=True)
    return path


def _new_file(path):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    os.close(fd)


@contextmanager
def _connection(root, write=False):
    path = _storage(root)
    db = sqlite3.connect(path.as_uri() + ('?mode=rw' if write else '?mode=ro'),
                         uri=True, timeout=30, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        _validate(db)
        yield db
        if write: _validate(db)
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def _receipt(row):
    return dict(provider='orders', account=row['account_sha256'], event_id=row['transfer_key'],
                kind='REVENUE', amount_cents=row['amount_cents'], currency=row['currency'],
                settled=True, attestation='FOUNDER', reference_sha256=row['reference_sha256'],
                evidence_sha256=row['evidence_sha256'], observed_at=row['observed_at'])


def _validate(db):
    if db.execute('PRAGMA user_version').fetchone()[0] != 1 or db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
        raise ValueError('invalid order register')
    if db.execute('PRAGMA foreign_key_check').fetchone():
        raise ValueError('invalid order associations')
    orders = {}
    totals = {}
    def add_total(kind, row):
        key = (kind, row['currency'], row['synthetic'])
        totals[key] = totals.get(key, 0) + row['amount_cents']
        if totals[key] > MAX_CENTS: raise ValueError('aggregate cents exceed accounting bound')
    for row in db.execute('SELECT * FROM orders'):
        if not isinstance(row['order_id'], str) or not re.fullmatch('ord_[0-9a-f]{32}', row['order_id']):
            raise ValueError('invalid opaque order identifier')
        _text(row['case_key']); _text(row['source_id'])
        _amount(row['amount_cents']); _currency(row['currency']); _digest(row['terms_sha256'])
        if row['synthetic'] not in (0, 1): raise ValueError('invalid synthetic flag')
        if row['acceptance_source_id'] is not None: _text(row['acceptance_source_id'])
        add_total('orders', row)
        orders[row['order_id']] = row
    for row in db.execute('SELECT * FROM claims'):
        _text(row['source_id']); _amount(row['amount_cents']); _currency(row['currency'])
        if row['order_id'] not in orders: raise ValueError('invalid claim association')
    for row in db.execute('SELECT * FROM deposits'):
        for key in ('transfer_key', 'account_sha256', 'reference_sha256', 'evidence_sha256'): _digest(row[key])
        _amount(row['amount_cents']); _currency(row['currency'])
        if (_observed(row['observed_at']) != row['observed_at']
                or row['transfer_key'] != _hash(row['account_sha256'] + ':' + row['reference_sha256'])
                or row['deposit_id'] != 'dep_' + row['transfer_key']
                or row['receipt_json'] != _json(_receipt(row))
                or any(row[key] not in (0, 1) for key in ('synthetic', 'posted', 'posting_started'))):
            raise ValueError('invalid deposit evidence')
        order = orders.get(row['order_id'])
        if row['order_id'] is not None and (order is None or row['synthetic'] != order['synthetic']):
            raise ValueError('invalid deposit association')
        if row['posting_started'] and (row['synthetic'] or order is None or not order['acceptance_source_id']
                                      or row['currency'] != 'CAD' or order['currency'] != 'CAD'):
            raise ValueError('invalid posting intent')
        if row['posted'] and not row['posting_started']: raise ValueError('invalid posted evidence')
        add_total('deposits', row)


def _require(db, table, key, value):
    _text(value)
    row = db.execute(f'SELECT * FROM {table} WHERE {key}=?', (value,)).fetchone()
    if row is None: raise ValueError('unknown private register identifier')
    return row


def _order_view(db, row, private=True):
    deposits = list(db.execute('SELECT * FROM deposits WHERE order_id=?', (row['order_id'],)))
    confirmed = sum(d['amount_cents'] for d in deposits if d['currency'] == row['currency'])
    posted = sum(d['amount_cents'] for d in deposits if d['posted'])
    claimed = db.execute('SELECT 1 FROM claims WHERE order_id=?', (row['order_id'],)).fetchone() is not None
    status = 'CLAIMED_UNVERIFIED' if claimed else 'UNPAID'
    if deposits:
        status = ('CURRENCY_MISMATCH' if any(d['currency'] != row['currency'] for d in deposits)
                  else 'PARTIAL' if confirmed < row['amount_cents']
                  else 'EXCESS' if confirmed > row['amount_cents'] else 'BANK_CONFIRMED')
    treasury = ('TREASURY_NOT_POSTED' if not posted else
                'TREASURY_POSTED' if all(d['posted'] for d in deposits) else 'TREASURY_PARTIALLY_POSTED')
    result = dict(order_id=row['order_id'], amount_cents=row['amount_cents'], currency=row['currency'],
                  terms_sha256=row['terms_sha256'], synthetic=bool(row['synthetic']),
                  commercial_status='ACCEPTED' if row['acceptance_source_id'] else 'DRAFT',
                  payment_status=status, treasury_status=treasury, confirmed_cents=confirmed, posted_cents=posted)
    if private:
        result.update(case_key=row['case_key'], source_id=row['source_id'], acceptance_source_id=row['acceptance_source_id'])
    return result


def _deposit_view(row):
    return dict(deposit_id=row['deposit_id'], amount_cents=row['amount_cents'], currency=row['currency'],
                synthetic=bool(row['synthetic']), allocated_order_id=row['order_id'], bank_status='BANK_CONFIRMED',
                treasury_status='TREASURY_POSTED' if row['posted'] else 'TREASURY_NOT_POSTED')


class OrderRegister:
    def __init__(self, root):
        self.root = Path(root).absolute()
        path = _storage(self.root, create=True)
        try:
            _new_file(path)
        except FileExistsError:
            pass
        else:
            with closing(sqlite3.connect(path)) as db:
                db.executescript(SCHEMA)
        with _connection(self.root): pass

    def create_order(self, case_key, amount_cents, currency, terms_sha256, source_id, synthetic=False):
        values = (_text(case_key), _amount(amount_cents), _currency(currency), _digest(terms_sha256),
                  _text(source_id), _synthetic(synthetic))
        with _connection(self.root, write=True) as db:
            prior = db.execute('SELECT * FROM orders WHERE source_id=?', (source_id,)).fetchone()
            if prior:
                if tuple(prior[k] for k in ('case_key', 'amount_cents', 'currency', 'terms_sha256', 'source_id', 'synthetic')) != values:
                    raise ValueError('order replay changed immutable terms')
                return _order_view(db, prior)
            order_id = 'ord_' + uuid.uuid4().hex
            db.execute('INSERT INTO orders VALUES(?,?,?,?,?,?,?,NULL)', (order_id, *values))
            return _order_view(db, _require(db, 'orders', 'order_id', order_id))

    def accept_order(self, order_id, acceptance_source_id):
        _text(acceptance_source_id)
        with _connection(self.root, write=True) as db:
            row = _require(db, 'orders', 'order_id', order_id)
            prior = row['acceptance_source_id']
            if prior is not None and prior != acceptance_source_id:
                raise ValueError('acceptance replay changed source')
            if db.execute('SELECT 1 FROM orders WHERE acceptance_source_id=? AND order_id!=?', (acceptance_source_id, order_id)).fetchone():
                raise ValueError('acceptance source already assigned')
            db.execute('UPDATE orders SET acceptance_source_id=? WHERE order_id=?', (acceptance_source_id, order_id))
            return _order_view(db, _require(db, 'orders', 'order_id', order_id))

    def record_claim(self, order_id, source_id, amount_cents, currency):
        values = (_text(source_id), _text(order_id), _amount(amount_cents), _currency(currency))
        with _connection(self.root, write=True) as db:
            _require(db, 'orders', 'order_id', order_id)
            prior = db.execute('SELECT * FROM claims WHERE source_id=?', (source_id,)).fetchone()
            if prior and tuple(prior) != values: raise ValueError('claim replay changed evidence')
            if not prior: db.execute('INSERT INTO claims VALUES(?,?,?,?)', values)
            return dict(source_id=source_id, order_id=order_id, amount_cents=amount_cents,
                        currency=currency, verification_status='UNVERIFIED')

    def confirm_deposit(self, account_alias, reference, amount_cents, currency, observed_at,
                        evidence_sha256, attested_by='FOUNDER', synthetic=False):
        if attested_by != 'FOUNDER': raise ValueError('founder bank attestation required')
        # Conservative case/outer-whitespace normalization prevents replay under
        # presentation changes. Keep punctuation; never guess a bank reference.
        account_hash = _hash(_text(account_alias).strip().casefold())
        reference_hash = _hash(_text(reference).strip().casefold())
        transfer_key = _hash(account_hash + ':' + reference_hash)
        values = dict(deposit_id='dep_' + transfer_key, transfer_key=transfer_key,
                      account_sha256=account_hash, reference_sha256=reference_hash,
                      amount_cents=_amount(amount_cents), currency=_currency(currency),
                      observed_at=_observed(observed_at), evidence_sha256=_digest(evidence_sha256),
                      synthetic=_synthetic(synthetic))
        values['receipt_json'] = _json(_receipt(values))
        with _connection(self.root, write=True) as db:
            prior = db.execute('SELECT * FROM deposits WHERE transfer_key=?', (transfer_key,)).fetchone()
            if prior:
                if any(prior[k] != v for k, v in values.items()): raise ValueError('deposit replay changed evidence')
                return _deposit_view(prior)
            columns = ','.join(values)
            db.execute(f'INSERT INTO deposits({columns}) VALUES({",".join("?" for _ in values)})', tuple(values.values()))
            return _deposit_view(_require(db, 'deposits', 'deposit_id', values['deposit_id']))

    def allocate(self, deposit_id, order_id):
        with _connection(self.root, write=True) as db:
            deposit = _require(db, 'deposits', 'deposit_id', deposit_id)
            order = _require(db, 'orders', 'order_id', order_id)
            if deposit['order_id'] not in (None, order_id): raise ValueError('deposit already allocated')
            if deposit['synthetic'] != order['synthetic']: raise ValueError('synthetic and real records cannot mix')
            if deposit['order_id'] is None and db.execute('SELECT 1 FROM deposits WHERE order_id=? AND posting_started=1 AND posted=0', (order_id,)).fetchone():
                raise ValueError('repair pending Treasury posting before allocation')
            db.execute('UPDATE deposits SET order_id=? WHERE deposit_id=?', (order_id, deposit_id))
            return _deposit_view(_require(db, 'deposits', 'deposit_id', deposit_id))

    def post(self, deposit_id, bank=None):
        # Commit intent BEFORE calling the separate Treasury database. An
        # interruption reuses the immutable receipt and Treasury event identity.
        with _connection(self.root, write=True) as db:
            deposit = _require(db, 'deposits', 'deposit_id', deposit_id)
            if deposit['synthetic'] or deposit['currency'] != 'CAD' or deposit['order_id'] is None:
                raise ValueError('allocated real CAD deposit required')
            order = _order_view(db, _require(db, 'orders', 'order_id', deposit['order_id']))
            if not deposit['posting_started'] and (order['commercial_status'] != 'ACCEPTED' or order['currency'] != 'CAD'
                                      or order['payment_status'] not in ('PARTIAL', 'BANK_CONFIRMED')):
                raise ValueError('accepted reconciled order required')
            db.execute('UPDATE deposits SET posting_started=1 WHERE deposit_id=?', (deposit_id,))
            expected = deposit['receipt_json']
        path = _storage(self.root, name='treasury.sqlite3')
        if bank is None:
            if not path.exists():
                try: _new_file(path)
                except FileExistsError: pass
            try:
                from .treasury import Treasury
            except ImportError:
                from treasury import Treasury
            bank = Treasury(path)
        elif Path(bank.db_path).absolute() != path:
            raise ValueError('Treasury must use the private host database')
        previous_verifier = bank.verifier
        bank.verifier = lambda candidate: _json(candidate) == expected
        try:
            bank.credit(json.loads(expected))
        finally:
            bank.verifier = previous_verifier
        with _connection(self.root, write=True) as db:
            db.execute('UPDATE deposits SET posted=1 WHERE deposit_id=?', (deposit_id,))
            return _deposit_view(_require(db, 'deposits', 'deposit_id', deposit_id))

    def get_order(self, order_id):
        with _connection(self.root) as db:
            return _order_view(db, _require(db, 'orders', 'order_id', order_id))


def case_orders(root, case_key, limit=10):
    """Caller must bind case_key to its authenticated conversation, never a model."""
    result = dict(state='UNAVAILABLE', orders=[])
    try:
        _text(case_key)
        if type(limit) is not int or not 1 <= limit <= 50: raise ValueError('invalid case view limit')
        with _connection(root) as db:
            rows = db.execute('SELECT * FROM orders WHERE case_key=? AND synthetic=0 ORDER BY rowid DESC LIMIT ?', (case_key, limit))
            result = dict(state='AVAILABLE', orders=[_order_view(db, row, private=False) for row in rows])
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError, OverflowError):
        pass
    return result


def project(root):
    """Validated non-synthetic counts only; absence/corruption is never zero demand."""
    fields = ('orders_count', 'pending_orders_count', 'claimed_orders_count',
              'bank_confirmed_deposits_count', 'unallocated_deposits_count',
              'reconciliation_blocked_orders_count', 'treasury_posted_cad_cents')
    result = dict(state='UNAVAILABLE', unavailable_reason='ORDER_REGISTER_UNAVAILABLE',
                  evidence_authority='FOUNDER_ATTESTATION', bank_api_verified=False,
                  **dict.fromkeys(fields))
    try:
        with _connection(root) as db:
            views = [_order_view(db, row, private=False) for row in db.execute('SELECT * FROM orders WHERE synthetic=0')]
            deposits = list(db.execute('SELECT * FROM deposits WHERE synthetic=0'))
            result.update(state='AVAILABLE', unavailable_reason=None, orders_count=len(views),
                pending_orders_count=sum(v['payment_status'] != 'BANK_CONFIRMED' for v in views),
                claimed_orders_count=db.execute('SELECT COUNT(DISTINCT c.order_id) FROM claims c JOIN orders o USING(order_id) WHERE o.synthetic=0').fetchone()[0],
                bank_confirmed_deposits_count=len(deposits),
                unallocated_deposits_count=sum(d['order_id'] is None for d in deposits),
                reconciliation_blocked_orders_count=sum(v['payment_status'] in ('PARTIAL', 'EXCESS', 'CURRENCY_MISMATCH') for v in views),
                treasury_posted_cad_cents=sum(d['amount_cents'] for d in deposits if d['posted'] and d['currency'] == 'CAD'))
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError, OverflowError):
        pass
    return result
