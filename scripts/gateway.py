"""Trusted installed finance adapter. No credentials or external spend implementation shipped."""
import hashlib,json,pathlib,re,os
from supervisor import atomic_json,bounded_run

class Gateway:
    def __init__(self,root,treasury):
        self.root=pathlib.Path(root);self.treasury=treasury
    def invoke(self,action,payload):
        adapter=self.root/'integrations'/'finance'
        if not adapter.is_file() or adapter.is_symlink():raise ValueError('No bounded finance integration configured')
        if adapter.stat().st_mode & 0o022:raise ValueError('finance adapter must not be group/world writable')
        code,out=bounded_run([str(adapter),action],env={'PATH':'/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'},input=json.dumps(payload,allow_nan=False).encode(),limit=1024*1024)
        if code:raise RuntimeError('finance adapter failed; retain holds and reconcile')
        return json.loads(out)
    def verify(self,receipt):
        try:return self.invoke('verify',{'receipt':receipt}).get('valid') is True
        except Exception:return False
    def _path(self,ident):
        if not re.fullmatch(r'TASK-[0-9]{4,12}',ident):raise ValueError('invalid financial operation')
        p=self.root/'state'/'gateway'/(ident+'.json');p.parent.mkdir(parents=True,exist_ok=True);return p
    def _accept(self,record,response):
        receipt=response.get('receipt')
        if not receipt:return {'status':'UNKNOWN','operation_id':record['id']}
        if receipt.get('operation_id')!=record['id']:raise ValueError('provider receipt operation mismatch')
        if receipt.get('kind')=='CANCELLED':self.treasury.release(record['id'],receipt)
        elif receipt.get('kind')=='SPEND':
            if record['settlement_kind']=='investment':
                positions=response.get('positions_receipt')
                if not positions:return {'status':'UNKNOWN','operation_id':record['id'],'reason':'Awaiting verified owned position value'}
                evidence=[positions]
                if response.get('revenue_receipt'):evidence.append(response['revenue_receipt'])
                self.treasury.sync_receipts(evidence,complete=False)
            self.treasury.settle(record['id'],receipt)
            if response.get('account_complete') is True and self.treasury.snapshot()['state']!='EXTINCT':self.treasury.sync_receipts([],complete=True)
        else:raise ValueError('unexpected financial receipt kind')
        record['state']='RESOLVED';atomic_json(self._path(record['id']),record)
        return {'status':'RESOLVED','operation_id':record['id'],'bank':self.treasury.snapshot()}
    def spend(self,task):
        ident=task['id'];p=self._path(ident);request=task['args']['request']
        digest=hashlib.sha256(json.dumps({'request':request,'agent':task['submitted_by']},sort_keys=True,allow_nan=False).encode()).hexdigest()
        if p.exists():
            record=json.loads(p.read_text())
            if record['hash']!=digest:raise ValueError('payment request identity changed')
        else:
            quote=self.invoke('quote',{'request':request,'operation_id':ident})
            if quote.get('bounded') is not True or quote.get('idempotent') is not True or quote.get('currency')!='CAD' or quote.get('settlement_kind','expense') not in ('expense','investment'):raise ValueError('adapter must guarantee bounded idempotent CAD debit')
            record={'id':ident,'hash':digest,'agent':task['submitted_by'],'request':request,'maximum':quote['max_debit_cents'],'settlement_kind':quote.get('settlement_kind','expense'),'state':'QUOTED'}
            atomic_json(p,record)
        op=self.treasury.reserve(ident,record['maximum'],digest,record['agent'])
        if op['status']!='HELD':return {'status':op['status'],'operation_id':ident}
        self.treasury.mark_submitted(ident)
        record['state']='SUBMITTING';atomic_json(p,record)
        try:response=self.invoke('submit',{'request':request,'operation_id':ident,'idempotency_key':ident,'max_debit_cents':record['maximum']})
        except Exception:return {'status':'UNKNOWN','operation_id':ident,'reason':'No terminal response; hold retained'}
        return self._accept(record,response)
    def sync(self):
        path=self.root/'state'/'gateway'/'account-sync.json'
        previous=json.loads(path.read_text()) if path.exists() else {}
        response=self.invoke('sync',{'cursor':previous.get('cursor')})
        receipts=response.get('receipts')
        if not isinstance(receipts,list) or len(receipts)>256:raise ValueError('bounded account receipt batch required')
        bank=self.treasury.sync_receipts(receipts,complete=response.get('complete') is True)
        # A cursor advances only after all evidence is applied; replay after crash is idempotent.
        cursor=response.get('next_cursor')
        if cursor is not None and (not isinstance(cursor,str) or len(cursor)>2048):raise ValueError('invalid account cursor')
        atomic_json(path,{'cursor':cursor})
        # Every uncertain operation is reconciled, oldest ID first; one failing
        # record neither starves later ones nor hides its own failure.
        failed=[]
        for pending in sorted(path.parent.glob('TASK-*.json'),key=lambda p:(len(p.stem),p.stem)):
            try:
                record=json.loads(pending.read_text())
                if record.get('state')=='SUBMITTING':self.reconcile(record['id'])
            except Exception:failed.append(pending.stem)
        if failed:raise RuntimeError('reconciliation incomplete; holds retained for '+', '.join(failed))
        return self.treasury.snapshot()
    def reconcile(self,ident):
        p=self._path(ident)
        if not p.exists():raise ValueError('unknown financial operation')
        record=json.loads(p.read_text())
        if record['state']=='RESOLVED':return {'status':'RESOLVED','operation_id':ident,'bank':self.treasury.snapshot()}
        return self._accept(record,self.invoke('reconcile',{'operation_id':ident,'request':record['request']}))
