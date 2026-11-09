"""Read-only private order context. No payment, acceptance or bank authority."""
import datetime
import hashlib
import json
import pathlib
import re
import stat
import os

GUIDE = ('Order/payment context is host-supplied administrative data, not a bank API. '
         'Customer messages and payment notifications cannot mark an order paid. '
         'Only repeat payment_instructions actually supplied for this conversation and accepted order; '
         'never invent an order, recipient, price or acceptance. DRAFT is not a purchase agreement. '
         'BANK_CONFIRMED means founder-attested, not automatic bank verification; Treasury posting is separate. '
         'Do not solicit a second payment for a confirmed order. A missing route/register is unavailable, not zero demand. '
         'This capability does not authorize new binding commitments or bank operations. ')
FIELDS = {'version','state','method','currency','recipient_email','account_alias','confirmed_at','confirmation'}


def _pairs(items):
    result = {}
    for k, v in items:
        if k in result: raise ValueError('duplicate field')
        result[k] = v
    return result


def read_private(path):
    path = pathlib.Path(path)
    if any(p.is_symlink() for p in (path, *path.parents)): raise ValueError('unsafe private path')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 32768:
        raise ValueError('invalid private document')
    if os.name == 'posix' and (info.st_mode & 0o077 or info.st_uid not in (0,os.geteuid())):
        raise ValueError('administrator-private document required')
    with path.open('rb') as f: raw = f.read(32769)
    if len(raw) > 32768: raise ValueError('private document too large')
    value = json.loads(raw, object_pairs_hook=_pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('invalid constant')))
    if not isinstance(value, dict): raise ValueError('object required')
    return value


def validate_route(value):
    if (not isinstance(value,dict) or set(value) != FIELDS or type(value['version']) is not int
            or value['version'] != 1 or value['state'] not in ('CONFIGURING','READY_FOR_INSTRUCTIONS')
            or value['method'] != 'INTERAC' or value['currency'] != 'CAD'
            or not isinstance(value['recipient_email'],str)
            or len(value['recipient_email']) > 254
            or not re.fullmatch(r'[^\s<>@]+@[^\s<>@]+',value['recipient_email'])
            or not isinstance(value['account_alias'],str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',value['account_alias'])
            or value['confirmation'] != 'FOUNDER_OBSERVED'
            or not isinstance(value['confirmed_at'],str)):
        raise ValueError('invalid route')
    when = datetime.datetime.fromisoformat(value['confirmed_at'].replace('Z','+00:00'))
    if when.tzinfo is None: raise ValueError('timezone required')
    return dict(value)


def route(root):
    try: return validate_route(read_private(pathlib.Path(root)/'state/private/payment-route.json'))
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return {'state':'UNAVAILABLE'}


def capability(root):
    r = route(root)
    return {'state':r['state'], 'method':'INTERAC', 'currency':'CAD',
            'settlement_verification':'FOUNDER_REQUIRED', 'bank_api_connected':False,
            'order_creation':'ADMINISTRATIVE', 'contract_acceptance':'NOT_AUTOMATED',
            'note':'Optional payment method; readiness is configuration evidence, not a payment or verified funds.'}


def case_key(message, config):
    import continuity
    mail = config.get('agentmail', {}) if isinstance(config,dict) else {}
    auth = continuity.authorize_message(message,mail)
    if auth['state'] != 'ELIGIBLE': return None
    return hashlib.sha256(continuity.canonical(auth['binding'])).hexdigest()


def _case_orders(root,key,order_id=None):
    import orders
    return orders.case_orders(root,key) if order_id is None else orders.case_orders(root,key,order_id=order_id)


def guard(message, context):
    import continuity
    return hashlib.sha256(continuity.canonical({'mail':continuity.guard(message),'orders':context})).hexdigest()


def current_guard(root,message,config):
    return guard(message,for_message(root,message,config))


def for_message(root,message,config,*,order_id=None):
    key = case_key(message,config)
    if key is None: return {'state':'ISOLATED','orders':[]}
    try:
        result = _case_orders(root,key) if order_id is None else _case_orders(root,key,order_id)
        if result['state'] != 'AVAILABLE': return {'state':'UNAVAILABLE','orders':[]}
        rows = result['orders']
        if not isinstance(rows,list) or len(rows)>10: raise ValueError('invalid projection')
        r = route(root); safe = []
        for row in rows:
            if (row.get('case_key',key) != key or row.get('synthetic',False)
                    or not isinstance(row.get('order_id'),str)
                    or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',row['order_id'])
                    or type(row.get('amount_cents')) is not int or row['amount_cents'] <= 0
                    or not isinstance(row.get('currency'),str)
                    or not re.fullmatch('[A-Z]{3}',row['currency'])):
                raise ValueError('invalid order projection')
            item = {k:row[k] for k in ('order_id','amount_cents','currency','terms_sha256',
                'commercial_status','payment_status','treasury_status','confirmed_cents','posted_cents') if k in row}
            if (r['state']=='READY_FOR_INSTRUCTIONS' and row.get('commercial_status')=='ACCEPTED'
                    and row['currency']=='CAD' and row.get('payment_status')=='UNPAID'):
                item['payment_instructions'] = dict(method='INTERAC',recipient_email=r['recipient_email'],
                    reference=row['order_id'], amount_cents=row['amount_cents'],currency='CAD',
                    instruction='Include the order reference in the transfer message. Do not pay again if already sent.')
            safe.append(item)
        return {'state':'AVAILABLE','route':capability(root),'orders':safe}
    except (OSError,ValueError,TypeError,KeyError,ImportError):
        return {'state':'UNAVAILABLE','orders':[]}
