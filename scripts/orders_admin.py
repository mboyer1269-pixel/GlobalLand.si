#!/usr/bin/env python3
"""Administrator-only private order reconciliation. Never sends mail or moves money."""
import argparse
import json
import os
import pathlib
import sys
import tempfile
import order_context


def _project(root):
    import orders
    return orders.project(root)


def _write_route(root,value):
    value=order_context.validate_route(value)
    parent=pathlib.Path(root)/'state/private'
    if any(p.is_symlink() for p in (parent,*parent.parents)): raise ValueError('unsafe private directory')
    parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    path=parent/'payment-route.json'
    if path.is_symlink() or (path.exists() and path.stat().st_nlink!=1): raise ValueError('unsafe route')
    if path.exists():
        old=order_context.validate_route(order_context.read_private(path))
        if old['account_alias']!=value['account_alias']:
            raise ValueError('account identity migration requires explicit reconciliation')
    fd,name=tempfile.mkstemp(prefix='.payment-route-',dir=parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(value,stream,sort_keys=True); stream.flush(); os.fsync(stream.fileno())
        os.chmod(name,0o600); os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)
    return order_context.capability(root)


def main(argv=None,root='/opt/globalland',euid=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['status','route','create','accept','claim','confirm','allocate','post',
                                        'propose','accept-proposal','instructions'])
    parser.add_argument('--request',help='absolute path of administrator-private JSON below state/private')
    args=parser.parse_args(argv)
    euid=euid or getattr(os,'geteuid',lambda:-1)
    if euid()!=0: raise ValueError('administrator required')
    root=pathlib.Path(root)
    if args.action=='status':
        result={'route':order_context.capability(root),'orders':_project(root)}
    else:
        if not args.request: raise ValueError('private request required')
        path=pathlib.Path(args.request)
        # Validate lexical containment before following or reading any path.
        if not path.is_absolute() or '..' in path.parts:
            raise ValueError('private request required')
        try: path.relative_to(root.absolute()/'state/private')
        except ValueError: raise ValueError('private request required') from None
        data=order_context.read_private(path)
        if args.action=='route':
            result=_write_route(root,data)
        elif args.action in ('propose','accept-proposal','instructions'):
            import order_proposals
            result={'propose':order_proposals.propose, 'accept-proposal':order_proposals.accept,
                    'instructions':order_proposals.instructions}[args.action](root,data)
        else:
            signatures={
                'create':({'case_key','amount_cents','currency','terms_sha256','source_id'}, {'synthetic'}),
                'accept':({'order_id','acceptance_source_id'},set()),
                'claim':({'order_id','source_id','amount_cents','currency'},set()),
                'confirm':({'account_alias','reference','amount_cents','currency','observed_at','evidence_sha256','attestation'}, {'synthetic'}),
                'allocate':({'deposit_id','order_id'},set()),
                'post':({'deposit_id','attestation'},set())}
            required,optional=signatures[args.action]
            if not required<=data.keys() or data.keys()-required-optional: raise ValueError('invalid request fields')
            if args.action in ('confirm','post'):
                if data.pop('attestation',None)!='FOUNDER_OBSERVED_BANK_DEPOSIT':
                    raise ValueError('explicit founder bank attestation required')
            if args.action=='confirm':
                route=order_context.route(root)
                if (route['state']!='READY_FOR_INSTRUCTIONS'
                        or data['account_alias']!=route['account_alias']):
                    raise ValueError('confirmed dedicated account route required')
            import orders
            register=orders.OrderRegister(root)
            method={'create':'create_order','accept':'accept_order','claim':'record_claim',
                    'confirm':'confirm_deposit','allocate':'allocate','post':'post'}[args.action]
            response=getattr(register,method)(**data)
            # Never print private case bindings, source IDs, bank references or evidence.
            result={'action':args.action,'recorded':True}
            if isinstance(response,dict):
                result.update({k:response[k] for k in ('order_id','deposit_id','payment_status',
                    'treasury_status','commercial_status') if k in response})
    print(json.dumps(result,sort_keys=True))
    return result


if __name__=='__main__':
    try: main()
    except Exception:
        print('Order operation refused; inspect the private request and reconciliation state locally.',file=sys.stderr)
        sys.exit(1)
