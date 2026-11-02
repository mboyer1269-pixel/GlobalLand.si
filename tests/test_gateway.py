import pathlib, tempfile, sys, unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from treasury import Treasury
class GatewayTests(unittest.TestCase):
 def test_no_adapter_means_no_external_spend(self):
  from gateway import Gateway
  with tempfile.TemporaryDirectory() as d:
   r=pathlib.Path(d);(r/'state').mkdir();bank=Treasury(r/'state/bank.sqlite3')
   g=Gateway(r,bank)
   with self.assertRaisesRegex(ValueError,'configured'):g.spend({'id':'TASK-0101','submitted_by':'DIRECTOR','args':{'request':{'anything':'strategy'}}})
   self.assertEqual(bank.snapshot()['cash_cents'],0)
 def test_gateway_reserves_then_reconciles_unknown_without_resubmitting(self):
  from gateway import Gateway
  with tempfile.TemporaryDirectory() as d:
   r=pathlib.Path(d);(r/'state').mkdir();b=Treasury(r/'state/bank.sqlite3',verifier=lambda r:True)
   b.confirm_funding({'provider':'test','account':'world','event_id':'fund','amount_cents':5000,'currency':'CAD','kind':'FUNDING','settled':True})
   class Fake(Gateway):
    calls=[]
    def invoke(self,action,payload):
     self.calls.append(action)
     if action=='quote':return {'bounded':True,'idempotent':True,'currency':'CAD','max_debit_cents':5000}
     if action=='submit':raise TimeoutError('uncertain')
     if action=='reconcile':return {'receipt':{'provider':'test','account':'world','event_id':'spend','operation_id':'TASK-0101','amount_cents':200,'currency':'CAD','kind':'SPEND','settled':True}}
   g=Fake(r,b);t={'id':'TASK-0101','submitted_by':'DIRECTOR','args':{'request':{'buy':'whatever'}}}
   self.assertEqual(g.spend(t)['status'],'UNKNOWN');self.assertEqual(b.snapshot()['reserved_cents'],5000)
   self.assertEqual(g.spend(t)['status'],'UNKNOWN');self.assertEqual(g.calls.count('submit'),1)
   g.reconcile('TASK-0101');self.assertEqual(b.snapshot()['cash_cents'],4800);self.assertEqual(b.snapshot()['reserved_cents'],0)
 def test_account_sync_imports_real_revenue_automatically_once(self):
  from gateway import Gateway
  with tempfile.TemporaryDirectory() as d:
   r=pathlib.Path(d);(r/'state').mkdir();b=Treasury(r/'state/bank.sqlite3',verifier=lambda r:True)
   fund={'provider':'test','account':'world','event_id':'fund','amount_cents':5000,'currency':'CAD','kind':'FUNDING','settled':True}
   revenue={'provider':'test','account':'world','event_id':'sale','amount_cents':700,'currency':'CAD','kind':'REVENUE','settled':True}
   class Fake(Gateway):
    def invoke(self,action,payload):
     if action=='sync':return {'receipts':[fund,revenue],'complete':True,'next_cursor':'event-2'}
     raise ValueError('unexpected action')
   g=Fake(r,b);g.sync();self.assertEqual(b.snapshot()['cash_cents'],5700);g.sync();self.assertEqual(b.snapshot()['cash_cents'],5700)
 def test_sync_reconciles_every_uncertain_operation_beyond_sixteen(self):
  from gateway import Gateway
  import json
  from supervisor import atomic_json
  with tempfile.TemporaryDirectory() as d:
   r=pathlib.Path(d);(r/'state').mkdir();b=Treasury(r/'state/bank.sqlite3',verifier=lambda r:True)
   b.confirm_funding({'provider':'test','account':'world','event_id':'fund','amount_cents':5000,'currency':'CAD','kind':'FUNDING','settled':True})
   ids=['TASK-%04d'%i for i in range(1000,1020)]
   class Fake(Gateway):
    reconciled=[]
    def invoke(self,action,payload):
     if action=='sync':return {'receipts':[],'complete':True,'next_cursor':None}
     if action=='reconcile':
      ident=payload['operation_id'];self.reconciled.append(ident)
      if ident=='TASK-1003':raise RuntimeError('provider outage for one record')
      return {'receipt':{'provider':'test','account':'world','event_id':'spend-'+ident,'operation_id':ident,'amount_cents':10,'currency':'CAD','kind':'SPEND','settled':True}}
     raise ValueError('unexpected action')
   g=Fake(r,b)
   for ident in ids:
    b.reserve(ident,100,'h-'+ident);b.mark_submitted(ident)
    atomic_json(g._path(ident),{'id':ident,'hash':'h-'+ident,'agent':'DIRECTOR','request':{},'maximum':100,'settlement_kind':'expense','state':'SUBMITTING'})
   with self.assertRaisesRegex(RuntimeError,'TASK-1003'):g.sync()
   self.assertEqual(sorted(g.reconciled),ids)
   self.assertEqual(b.snapshot()['reserved_cents'],100)
   self.assertEqual(b.snapshot()['cash_cents'],5000-19*10)
   self.assertEqual(json.loads(g._path('TASK-1003').read_text())['state'],'SUBMITTING')
 def test_sync_orders_numeric_ids_oldest_first(self):
  from gateway import Gateway
  from supervisor import atomic_json
  with tempfile.TemporaryDirectory() as d:
   r=pathlib.Path(d);(r/'state').mkdir();b=Treasury(r/'state/bank.sqlite3',verifier=lambda r:True)
   class Fake(Gateway):
    order=[]
    def invoke(self,action,payload):
     if action=='sync':return {'receipts':[],'complete':False}
     self.order.append(payload['operation_id']);return {}
   g=Fake(r,b)
   for ident in ('TASK-179349120200','TASK-0101','TASK-99999'):
    atomic_json(g._path(ident),{'id':ident,'request':{},'state':'SUBMITTING'})
   g.sync();self.assertEqual(g.order,['TASK-0101','TASK-99999','TASK-179349120200'])
if __name__=='__main__':unittest.main()
