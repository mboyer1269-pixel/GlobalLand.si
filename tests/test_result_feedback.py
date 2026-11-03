"""Execution provenance is public metadata, not a private payment receipt."""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from controller import Controller


class Snapshot:
    def snapshot(self):
        return {'state': 'UNFUNDED'}


class ResultFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        (self.root / 'state').mkdir()
        self.controller = Controller(self.root, Snapshot(), Snapshot(), {})

    def write_result(self, result):
        ident = 'TASK-180000000000'
        record = {'id': ident, 'origin': 'broker', 'task': None,
                  'request': {'action': 'EXEC'}, 'state': 'PUBLISHED', 'result': result}
        (self.root / 'state' / (ident + '.json')).write_text(json.dumps(record))

    def test_success_with_technical_provenance_reaches_the_next_turn(self):
        self.write_result({'status': 'DONE', 'output': '21 tests passed',
                           'artifacts': ['products/tool/result.txt',
                                         'products/receipts/TASK-180000000000.json']})
        self.assertEqual(self.controller.context()['latest_task_results'],
                         [{'task': 'TASK-180000000000', 'status': 'DONE',
                           'output': '21 tests passed'}])

    def test_private_receipt_content_is_still_excluded(self):
        for private in ('receipt private-bank-data', 'access_token private-data',
                        'API_KEY=' + 'x' * 30):
            with self.subTest(private=private.split()[0]):
                self.write_result({'status': 'DONE', 'output': private,
                                   'artifacts': ['products/receipts/TASK-180000000000.json']})
                self.assertEqual(self.controller.context()['latest_task_results'], [])

    def test_other_receipt_and_auth_artifacts_are_still_excluded(self):
        for path in ('products/receipts/bank-payment.json', 'products/auth.json',
                     'products/credential.txt'):
            with self.subTest(path=path):
                self.write_result({'status': 'DONE', 'output': 'finished', 'artifacts': [path]})
                self.assertEqual(self.controller.context()['latest_task_results'], [])

    def test_malformed_results_do_not_break_the_next_context(self):
        for result in (None, [], 'invalid'):
            with self.subTest(result=result):
                self.write_result(result)
                self.assertEqual(self.controller.context()['latest_task_results'], [])

    def test_finance_task_results_remain_excluded(self):
        path = self.root / 'state/TASK-180000000000.json'
        for action in ('SPEND', 'RECONCILE'):
            with self.subTest(action=action):
                path.write_text(json.dumps({'task': {'action': action},
                    'result': {'status': 'DONE', 'output': 'settled',
                               'artifacts': ['products/receipts/TASK-180000000000.json']}}))
                self.assertEqual(self.controller.context()['latest_task_results'], [])


if __name__ == '__main__':
    unittest.main()
