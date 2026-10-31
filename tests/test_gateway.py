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
if __name__=='__main__':unittest.main()
