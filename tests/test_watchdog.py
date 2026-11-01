"""Dead man's switch: silence or a blocked controller must raise an alert."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import watchdog


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.repo = pathlib.Path(self.tmp.name)
        self.git('init', '-q', '-b', 'main')

    def git(self, *args, author='globalland-supervisor', date=None):
        env = {'GIT_AUTHOR_NAME': author, 'GIT_AUTHOR_EMAIL': 'a@local', 'GIT_COMMITTER_NAME': author,
               'GIT_COMMITTER_EMAIL': 'a@local', 'PATH': '/usr/bin:/bin:/usr/local/bin'}
        if date:
            env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True, env=env)

    def commit(self, files, author='globalland-supervisor', at=1793491200):
        for name, value in files.items():
            path = self.repo / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))
        self.git('add', '.'); self.git('commit', '-q', '-m', 'ops', author=author, date='@%d +0000' % at)

    def test_healthy_world_is_ok(self):
        self.commit({'world/controller.json': {'state': 'OPERATIONAL'}}, at=1793491200)
        report = watchdog.check(self.repo, now=1793491200 + 1800)
        self.assertEqual((report['status'], report['reasons']), ('OK', []))

    def test_silence_blocked_controller_and_founder_actions_alert(self):
        self.commit({'world/controller.json': {'state': 'CONTROLLER_BLOCKED', 'reason_code': 'provider_timeout'},
                     'world/blockers.json': {'open': [{'id': 'NO-APIFY', 'owner': 'FOUNDER', 'title': 'Token Apify manquant'}]}}, at=1793491200)
        # A human commit afterwards does not count as the supervisor being alive.
        self.commit({'README.md': 'x'}, author='Michael', at=1793491200 + 5 * 3600)
        report = watchdog.check(self.repo, now=1793491200 + 5 * 3600)
        self.assertEqual(report['status'], 'ALERT')
        self.assertEqual(report['last_supervisor_commit_age_hours'], 5.0)
        text = ' '.join(report['reasons'])
        for fragment in ('5.0 h', 'CONTROLLER_BLOCKED', 'provider_timeout', 'Token Apify manquant'):
            self.assertIn(fragment, text)
        body = watchdog.issue_body(report)
        self.assertIn('controller-failure.json', body)

    def test_no_supervisor_commit_at_all_is_an_alert(self):
        self.commit({'README.md': 'x'}, author='Michael')
        self.assertEqual(watchdog.check(self.repo, now=1793491200)['status'], 'ALERT')

    def test_workflow_is_scheduled_with_minimal_permissions(self):
        text = (pathlib.Path(__file__).resolve().parents[1] / '.github/workflows/watchdog.yml').read_text()
        self.assertIn("cron: '23 * * * *'", text)
        self.assertIn('permissions:\n  contents: read\n  issues: write\n', text)
        self.assertNotIn('secrets.', text)

if __name__ == '__main__':
    unittest.main()
