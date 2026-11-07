import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import orders_admin


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name); (self.root/'state/private').mkdir(parents=True)
        self.path=self.root/'state/private/request.json'

    def request(self,data):
        self.path.write_text(json.dumps(data)); self.path.chmod(0o600)
        return ['route','--request',str(self.path)]

    def test_unprivileged_does_not_read_or_create(self):
        with self.assertRaises(ValueError): orders_admin.main(['status'],root=self.root,euid=lambda:1000)
        self.assertFalse((self.root/'state/private/orders.sqlite3').exists())

    def test_readonly_status_does_not_create_ledger(self):
        with patch('orders_admin._project',return_value={'state':'UNAVAILABLE'}),patch('sys.stdout',new_callable=io.StringIO) as out:
            orders_admin.main(['status'],root=self.root,euid=lambda:0)
        self.assertNotIn('recipient_email',out.getvalue())
        self.assertFalse((self.root/'state/private/orders.sqlite3').exists())

    def test_route_requires_explicit_observation_and_private_input(self):
        args=self.request({'version':1,'state':'READY_FOR_INSTRUCTIONS','method':'INTERAC','currency':'CAD',
            'recipient_email':'city@example.test','account_alias':'project-account','confirmed_at':'2026-11-07T19:00:00Z',
            'confirmation':'FOUNDER_OBSERVED'})
        with patch('sys.stdout',new_callable=io.StringIO) as out:
            orders_admin.main(args,root=self.root,euid=lambda:0)
        self.assertTrue((self.root/'state/private/payment-route.json').exists())
        self.assertNotIn('city@example.test',out.getvalue())
        self.assertNotIn('project-account',out.getvalue())

    def test_reject_request_outside_private_root(self):
        p=self.root/'public.json'; p.write_text('{}')
        with self.assertRaises(ValueError):
            orders_admin.main(['route','--request',str(p)],root=self.root,euid=lambda:0)

    def test_confirm_requires_attestation_before_register_open(self):
        args=self.request({'account_alias':'project','reference':'private-secret'})
        args[0]='confirm'
        with self.assertRaises(ValueError): orders_admin.main(args,root=self.root,euid=lambda:0)
        self.assertFalse((self.root/'state/private/orders.sqlite3').exists())

    def test_route_alias_cannot_be_changed_to_recredit_the_same_account(self):
        data={'version':1,'state':'READY_FOR_INSTRUCTIONS','method':'INTERAC','currency':'CAD',
            'recipient_email':'city@example.test','account_alias':'project-account','confirmed_at':'2026-11-07T19:00:00Z',
            'confirmation':'FOUNDER_OBSERVED'}
        with patch('sys.stdout',new_callable=io.StringIO):
            orders_admin.main(self.request(data),root=self.root,euid=lambda:0)
        data['account_alias']='other-label-same-bank'
        with self.assertRaises(ValueError):
            orders_admin.main(self.request(data),root=self.root,euid=lambda:0)


if __name__=='__main__': unittest.main()
