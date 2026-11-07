"""Local fictional end-to-end flow, never calls a bank or mail transport."""
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import order_context
import orders
import orders_admin
from treasury import Treasury


class OrderFlowTests(unittest.TestCase):
    def test_bank_attestation_and_order_survive_restart_without_double_credit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp); private=root/'state/private'; private.mkdir(parents=True,mode=0o700)
            request=private/'request.json'
            def admin(action,data):
                request.write_text(json.dumps(data)); request.chmod(0o600)
                with patch('sys.stdout',new_callable=io.StringIO) as output:
                    result=orders_admin.main([action,'--request',str(request)],root=root,euid=lambda:0)
                self.assertNotIn('bank-private-ref',output.getvalue())
                self.assertNotIn('private-customer',output.getvalue())
                return result
            config={'agentmail':{'inbox_id':'inbox','inbox_address':'city@example.test'}}
            message={'inbox_id':'inbox','message_id':'one','thread_id':'thread',
                'from':'private-customer@example.test','to':['city@example.test'],
                'authentication_results':{'dmarc':'pass','dmarc_domain':'example.test'}}
            key=order_context.case_key(message,config)
            admin('route',{'version':1,'state':'READY_FOR_INSTRUCTIONS','method':'INTERAC','currency':'CAD',
                'recipient_email':'city@example.test','account_alias':'project','confirmed_at':'2026-11-07T19:00:00Z',
                'confirmation':'FOUNDER_OBSERVED'})
            created=admin('create',{'case_key':key,'amount_cents':1900,'currency':'CAD',
                'terms_sha256':'a'*64,'source_id':'order-request'})
            oid=created['order_id']
            admin('accept',{'order_id':oid,'acceptance_source_id':'documented-acceptance'})
            ctx=order_context.for_message(root,message,config)
            self.assertEqual(ctx['orders'][0]['payment_instructions']['reference'],oid)
            admin('claim',{'order_id':oid,'source_id':'customer-claim','amount_cents':1900,'currency':'CAD'})
            self.assertFalse((private/'treasury.sqlite3').exists())
            ctx=order_context.for_message(root,message,config)
            self.assertEqual(ctx['orders'][0]['payment_status'],'CLAIMED_UNVERIFIED')
            self.assertNotIn('payment_instructions',ctx['orders'][0])
            dep=admin('confirm',{'account_alias':'project','reference':'bank-private-ref','amount_cents':1900,
                'currency':'CAD','observed_at':'2026-11-07T19:01:00Z','evidence_sha256':'b'*64,
                'attestation':'FOUNDER_OBSERVED_BANK_DEPOSIT'})['deposit_id']
            admin('allocate',{'deposit_id':dep,'order_id':oid})
            self.assertFalse((private/'treasury.sqlite3').exists())
            admin('post',{'deposit_id':dep,'attestation':'FOUNDER_OBSERVED_BANK_DEPOSIT'})
            admin('post',{'deposit_id':dep,'attestation':'FOUNDER_OBSERVED_BANK_DEPOSIT'})
            bank=Treasury(private/'treasury.sqlite3').snapshot()
            self.assertEqual(bank['cash_cents'],1900)
            self.assertEqual(bank['founder_attested_revenue_cents'],1900)
            self.assertFalse(bank['funding_verified'])
            ctx=order_context.for_message(root,message,config)
            self.assertEqual(ctx['orders'][0]['payment_status'],'BANK_CONFIRMED')
            self.assertEqual(ctx['orders'][0]['treasury_status'],'TREASURY_POSTED')
            self.assertNotIn('payment_instructions',ctx['orders'][0])
            message['from']='other@example.test'
            self.assertEqual(order_context.for_message(root,message,config)['orders'],[])
            self.assertNotIn('private-customer',json.dumps(orders.project(root)))


if __name__=='__main__': unittest.main()
