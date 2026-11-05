"""Operational accomplishments must not conceal a lack of verified revenue."""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import progress


class VerifiedRevenueProgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.world = {'missions': [{'mission_id': 'BUILD', 'status': 'RUNNING'}]}
        self.bank = {'revenue_cents': 0}

    def turn(self, number):
        result = progress.assess(self.root, self.world, self.bank, {})
        progress.commit(self.root, 'THINK-' + str(number), result)
        return result

    def test_technical_completion_and_failure_do_not_reset_revenue_gap(self):
        self.assertEqual(self.turn(1)['turns_without_verified_revenue'], 0)
        self.world['missions'][0]['status'] = 'COMPLETED'
        completed = self.turn(2)
        self.assertTrue(completed['change']['outcome'])
        self.assertEqual(completed['turns_without_verified_revenue'], 1)
        self.world['missions'].append({'mission_id': 'ABANDONED', 'status': 'FAILED'})
        failed = self.turn(3)
        self.assertTrue(failed['change']['outcome'])
        self.assertEqual(failed['turns_without_verified_revenue'], 2)
        self.assertEqual(progress.for_prompt(failed)['turns_without_verified_revenue'], 2)

    def test_existing_revenue_is_baseline_and_only_new_revenue_resets_gap(self):
        self.bank['revenue_cents'] = 700
        self.assertEqual(self.turn(1)['turns_without_verified_revenue'], 0)
        self.assertEqual(self.turn(2)['turns_without_verified_revenue'], 1)
        self.bank['revenue_cents'] = 800
        self.assertEqual(self.turn(3)['turns_without_verified_revenue'], 0)
        self.bank['revenue_cents'] = 700
        self.assertEqual(self.turn(4)['turns_without_verified_revenue'], 1)

    def test_assessment_retry_does_not_count_as_another_successful_turn(self):
        self.turn(1)
        first = progress.assess(self.root, self.world, self.bank, {})
        retry = progress.assess(self.root, self.world, self.bank, {})
        self.assertEqual(first['turns_without_verified_revenue'], 1)
        self.assertEqual(retry['turns_without_verified_revenue'], 1)


if __name__ == '__main__':
    unittest.main()
