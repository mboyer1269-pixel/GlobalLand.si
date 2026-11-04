"""Execution provenance is public metadata, not a private payment receipt."""
import json
import os
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

    def test_reconstructed_public_history_cannot_evict_latest_private_result(self):
        self.write_result({'status': 'DONE', 'output': '1728\n',
                           'artifacts': ['products/receipts/TASK-180000000000.json']})
        private = self.root / 'state/TASK-180000000000.json'
        os.utime(private, (100, 100))
        public = self.root / 'work/queue/done'
        public.mkdir(parents=True)
        # Archive reconstruction makes every historical public file newer than
        # the durable result, including a public copy with screened request text.
        for number in range(25):
            path = public / ('TASK-%012d.result.json' % (179000000000 + number))
            path.write_text(json.dumps({'status': 'DONE', 'output': 'old result'}))
            os.utime(path, (200 + number, 200 + number))
        duplicate = public / 'TASK-180000000000.result.json'
        duplicate.write_text(json.dumps({'status': 'DONE', 'output': '1728\n',
                                        'request': {'description': 'inspect receipts'}}))
        os.utime(duplicate, (300, 300))
        results = self.controller.context()['latest_task_results']
        self.assertEqual(len(results), 20)
        self.assertEqual(results[0], {'task': 'TASK-180000000000', 'status': 'DONE', 'output': '1728\n'})

    def test_private_completion_order_wins_over_task_number_and_public_duplicates(self):
        self.write_result({'status': 'DONE', 'output': 'earlier completion'})
        os.utime(self.root / 'state/TASK-180000000000.json', (100, 100))
        (self.root / 'state/TASK-0001.json').write_text(json.dumps({
            'task': 'queue/inbox/TASK-0001.json',
            'result': {'status': 'DONE', 'output': 'latest completion'}}))
        public = self.root / 'work/queue/done'
        public.mkdir(parents=True)
        (public / 'TASK-0001.result.json').write_text(json.dumps({'status': 'DONE', 'output': 'public copy'}))
        results = self.controller.context()['latest_task_results']
        self.assertEqual([r['task'] for r in results], ['TASK-0001', 'TASK-180000000000'])
        self.assertEqual(results[0]['output'], 'latest completion')

    def test_public_only_fallback_uses_task_order_independent_of_extraction_times(self):
        public = self.root / 'work/queue/done'
        public.mkdir(parents=True)
        for number, modified in ((179000000001, 300), (179000000003, 100), (179000000002, 200)):
            path = public / ('TASK-%d.result.json' % number)
            path.write_text(json.dumps({'status': 'DONE', 'output': 'public result'}))
            os.utime(path, (modified, modified))
        self.assertEqual([r['task'] for r in self.controller.context()['latest_task_results']],
                         ['TASK-179000000003', 'TASK-179000000002', 'TASK-179000000001'])

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
