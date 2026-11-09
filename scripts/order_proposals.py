"""Administrator-only product evidence bridge. Never sends or moves money.

Saved authenticated mail supplies a conversation binding, not contract authority.
An explicit administrator review supplies acceptance; bank attestation is separate.
"""
import hashlib
import os
from pathlib import Path
import re
import tempfile

import continuity
import order_context
import orders


ARTIFACT_LIMIT = 1024 * 1024  # Existing per-file product output bound.


def _fields(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError('invalid proposal fields')


def _text(value, limit=4096):
    if (not isinstance(value, str) or not value.strip() or len(value) > limit
            or any(ord(c) < 32 and c not in '\n\t' for c in value)):
        raise ValueError('bounded proposal text required')
    return value


def _hash(value):
    return hashlib.sha256(continuity.canonical(value)).hexdigest()


def _private(root, value):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('absolute private path required')
    parent = Path(root).absolute() / 'state/private'
    try: path.relative_to(parent)
    except ValueError: raise ValueError('private path required') from None
    orders._safe_path(parent, private=True, directory=True)
    orders._safe_path(path.parent, private=True, directory=True)
    orders._safe_path(path, private=True)
    return path


def _config(root):
    path = Path(root).absolute() / 'control/config.json'
    orders._safe_path(path)
    config = continuity.read(path, 128 * 1024)
    from mail import settings
    if settings(config) is None:
        raise ValueError('current mail configuration required')
    return config


def _source(root, reference, excerpt):
    _fields(reference, ('version', 'case_key', 'ready_digest'))
    path = continuity.case_path(root, reference.get('case_key'))
    _private(root, str(path))
    source = continuity.load_ready(root, reference)
    config = _config(root)
    auth = continuity.authorize_message(source['incoming'], config['agentmail'])
    if (source['continuity']['state'] != 'ELIGIBLE' or auth['state'] != 'ELIGIBLE'
            or auth['binding'] != source['continuity']['binding']):
        raise ValueError('authenticated source required')
    # These are routing holds, never proof that a financial notification is real.
    from mail import _financial_notice, _armor_deferred, _should_ignore
    import commercial
    feedback = commercial.settings(config)
    if feedback['state'] == 'UNAVAILABLE':
        raise ValueError('current source exclusions unavailable')
    synthetic = {continuity.address(sender) for sender in feedback['synthetic_senders']}
    if (auth['binding']['peer'] in synthetic
            or commercial.host_origin(source['incoming'], config) in ('SYNTHETIC', 'AUTOMATED')
            or _financial_notice(source['incoming']) or _armor_deferred(source['incoming'])
            or _should_ignore(source['incoming'], config['agentmail']['inbox_address'])):
        raise ValueError('eligible customer source required')
    _text(excerpt, 2048)
    message = continuity.observation_message(source)
    text = message.get('extracted_text') or message.get('text')
    if not isinstance(text, str) or excerpt not in text:
        raise ValueError('excerpt must occur in current source text')
    return source


def _terms(root, value):
    _fields(value, ('version', 'product_id', 'product_version', 'offer_version', 'title',
                    'scope', 'exclusions', 'license', 'support', 'amount_cents', 'currency', 'delivery'))
    if type(value['version']) is not int or value['version'] != 1:
        raise ValueError('unsupported proposal version')
    if type(value['offer_version']) is not int or not 1 <= value['offer_version'] <= 1000000:
        raise ValueError('positive bounded offer version required')
    for key in ('product_id', 'product_version'):
        if not isinstance(value[key], str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,79}', value[key]):
            raise ValueError('bounded product identity required')
    for key in ('title', 'scope', 'exclusions', 'license', 'support'):
        _text(value[key], 256 if key == 'title' else 4096)
    orders._amount(value['amount_cents']); orders._currency(value['currency'])
    delivery = value['delivery']
    _fields(delivery, ('mode', 'artifact_path', 'artifact_sha256'))
    if delivery['mode'] != 'MANUAL_ARTIFACT':
        raise ValueError('manual product delivery required')
    orders._digest(delivery['artifact_sha256'])
    from tools import product_path
    name = _text(delivery['artifact_path'], 240)
    product_path(name)
    path = Path(root).absolute() / name
    orders._safe_path(path)
    if path.stat().st_size > ARTIFACT_LIMIT:
        raise ValueError('product evidence exceeds artifact bound')
    with path.open('rb') as stream: raw = stream.read(ARTIFACT_LIMIT + 1)
    if len(raw) > ARTIFACT_LIMIT or hashlib.sha256(raw).hexdigest() != delivery['artifact_sha256']:
        raise ValueError('product evidence mismatch')
    return len(raw)


def _prepare(root, request):
    _fields(request, ('completion', 'demand_excerpt', 'terms'))
    source = _source(root, request['completion'], request['demand_excerpt'])
    size = _terms(root, request['terms'])
    terms = request['terms']
    identifier = 'prop_' + _hash(dict(identity=source['identity'], product_id=terms['product_id'],
                                      offer_version=terms['offer_version']))
    return dict(version=1, proposal_id=identifier, terms_sha256=_hash(terms),
                case_key=_hash(source['continuity']['binding']), artifact_bytes=size, request=request), source


def _snapshot_path(root, identifier, directory='order-proposals'):
    if not isinstance(identifier, str) or not re.fullmatch(r'(?:prop|accept)_[0-9a-f]{64}', identifier):
        raise ValueError('invalid proposal evidence identifier')
    return _private(root, str(Path(root).absolute() / 'state/private' / directory / (identifier + '.json')))


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def _immutable(path, value):
    """Serialize immutable publication; a crash never leaves a linked snapshot."""
    import fcntl
    raw = continuity.canonical(value)
    if len(raw) > 32768: raise ValueError('proposal evidence exceeds private document bound')
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    orders._safe_path(path.parent, private=True, directory=True)
    _sync_directory(path.parent.parent)
    lock = path.parent / '.lock'
    orders._safe_path(lock, private=True)
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'rb') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        orders._safe_path(lock, private=True)
        if path.exists():
            if continuity.canonical(order_context.read_private(path)) != raw:
                raise ValueError('immutable proposal evidence changed')
            _sync_directory(path.parent)
            return
        fd, temporary = tempfile.mkstemp(prefix='.proposal-', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as pending:
                pending.write(raw); pending.flush(); os.fsync(pending.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
            _sync_directory(path.parent)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)


def _proposal(root, identifier):
    if not isinstance(identifier, str) or not identifier.startswith('prop_'):
        raise ValueError('proposal identifier required')
    saved = order_context.read_private(_snapshot_path(root, identifier))
    _fields(saved, ('version', 'proposal_id', 'terms_sha256', 'case_key', 'artifact_bytes', 'request'))
    expected, source = _prepare(root, saved['request'])
    if continuity.canonical(expected) != continuity.canonical(saved) or saved['proposal_id'] != identifier:
        raise ValueError('proposal evidence mismatch')
    return saved, source


def _order(root, proposal, identifier):
    # Read-only lookup: constructing OrderRegister would initialize absent storage.
    with orders._connection(root) as db:
        row = orders._require(db, 'orders', 'order_id', identifier)
        result = orders._order_view(db, row)
    terms = proposal['request']['terms']
    if (result['case_key'] != proposal['case_key'] or result['source_id'] != proposal['proposal_id']
            or result['terms_sha256'] != proposal['terms_sha256'] or result['synthetic']
            or result['amount_cents'] != terms['amount_cents'] or result['currency'] != terms['currency']):
        raise ValueError('order does not match proposal')
    return result


def _result(proposal, order):
    return {**{k: proposal[k] for k in ('proposal_id', 'terms_sha256')},
            **{k: order[k] for k in ('order_id', 'commercial_status', 'payment_status', 'treasury_status')}}


def propose(root, data):
    proposal, _ = _prepare(root, data)
    _immutable(_snapshot_path(root, proposal['proposal_id']), proposal)
    terms = data['terms']
    order = orders.OrderRegister(root).create_order(proposal['case_key'], terms['amount_cents'],
        terms['currency'], proposal['terms_sha256'], proposal['proposal_id'])
    return dict(action='propose', recorded=True, **_result(proposal, order))


def accept(root, data):
    _fields(data, ('proposal_id', 'order_id', 'terms_sha256', 'completion', 'acceptance_excerpt', 'attestation'))
    if data['attestation'] != 'ADMIN_REVIEWED_EXACT_TERMS':
        raise ValueError('explicit administrative acceptance review required')
    proposal, demand = _proposal(root, data['proposal_id'])
    if data['terms_sha256'] != proposal['terms_sha256']:
        raise ValueError('acceptance terms mismatch')
    source = _source(root, data['completion'], data['acceptance_excerpt'])
    if (source['identity'] == demand['identity']
            or source['continuity']['binding'] != demand['continuity']['binding']):
        raise ValueError('distinct acceptance source in the same conversation required')
    order = _order(root, proposal, data['order_id'])
    acceptance_id = 'accept_' + _hash(source['identity'])
    if order['acceptance_source_id'] not in (None, acceptance_id):
        raise ValueError('acceptance replay changed source')
    _immutable(_snapshot_path(root, acceptance_id, 'order-acceptances'), dict(version=1, request=data))
    accepted = orders.OrderRegister(root).accept_order(data['order_id'], acceptance_id)
    return dict(action='accept-proposal', recorded=True, **_result(proposal, accepted))


def instructions(root, data):
    _fields(data, ('proposal_id', 'order_id', 'output'))
    output = _private(root, data['output'])
    if output.exists(): raise ValueError('instruction output must be a new private file')
    proposal, source = _proposal(root, data['proposal_id'])
    _order(root, proposal, data['order_id'])
    message = source['incoming']
    config = _config(root)
    context = order_context.for_message(root, message, config, order_id=data['order_id'])
    selected = next((row for row in context['orders'] if row['order_id'] == data['order_id']), None)
    if selected is None or 'payment_instructions' not in selected:
        raise ValueError('payment instructions unavailable for this order')
    value = dict(version=1, proposal_id=data['proposal_id'], order_id=data['order_id'],
                 terms_sha256=proposal['terms_sha256'], payment_instructions=selected['payment_instructions'],
                 order_context_guard=order_context.guard(message, context), delivery_mode='MANUAL_ARTIFACT',
                 note='Private preparation snapshot only. No message or product was sent. Recheck order state before use.')
    # O_EXCL: an administrator's other private documents can never be overwritten.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(continuity.canonical(value)); stream.flush(); os.fsync(stream.fileno())
    return dict(action='instructions', prepared=True, order_id=data['order_id'], proposal_id=data['proposal_id'])
