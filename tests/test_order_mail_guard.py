import json
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import order_context
from tests import test_mail


class OrderMailGuardTests(unittest.TestCase):
    setUp = test_mail.MailTests.setUp
    def test_route_or_order_changed_after_generation_refuses_send(self):
        context={'state':'AVAILABLE','orders':[{'order_id':'ord_example'}]}
        def responder(message):
            context['orders']=[]
            return {'action':'reply','text':'Old payment instructions'}
        with patch('order_context.for_message',side_effect=lambda *a:dict(context)):
            result=self.box.cycle(responder)
        self.assertEqual(result['accepted'],0)
        self.assertFalse(any(c[0]=='POST' for c in self.transport.calls))

    def test_recipient_changed_after_reading_private_order_refuses_send(self):
        def responder(message):
            self.transport.messages[0]['from']='Other <other@example.test>'
            return {'action':'reply','text':'Private original buyer order'}
        result=self.box.cycle(responder)
        self.assertEqual(result['accepted'],0)
        self.assertFalse(any(c[0]=='POST' for c in self.transport.calls))

    def test_saved_reply_guard_cannot_be_replaced_by_fresh_context(self):
        class Saved:
            last_order_context_guard='0'*64
            def __call__(self,message): return {'action':'reply','text':'Old instructions'}
        result=self.box.cycle(Saved())
        self.assertEqual(result['accepted'],0)


if __name__=='__main__': unittest.main()
