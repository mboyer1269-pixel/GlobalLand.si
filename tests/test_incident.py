import fcntl
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import incident  # noqa: E402

NOW = 1793520000.0


def fake_run(ps='', docker_ok=True, containers=''):
    def run(args, **kwargs):
        if args[0] == 'ps':
            return SimpleNamespace(returncode=0, stdout=ps)
        if args[:2] == ['docker', 'info']:
            if docker_ok is None:
                raise FileNotFoundError('docker')
            return SimpleNamespace(returncode=0 if docker_ok else 1, stdout='')
        if args[:2] == ['docker', 'ps']:
            return SimpleNamespace(returncode=0, stdout=containers)
        raise AssertionError(args)
    return run


class IncidentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name) / 'opt'
        (self.root / 'state' / 'private').mkdir(parents=True)
        (self.root / 'state' / 'controller').mkdir()
        for provider in ('codex', 'claude'):
            (self.root / 'credentials' / provider).mkdir(parents=True)
            (self.root / 'credentials' / provider / 'auth.json').write_text('{}')
        self.cron = pathlib.Path(self.tmp.name) / 'cron'
        self.cron.write_text('job')
        self.log = pathlib.Path(self.tmp.name) / 'think.log'
        self.log.write_text('x')
        os.utime(self.log, (NOW - 600, NOW - 600))

    def tearDown(self):
        self.tmp.cleanup()

    def facts(self, **kwargs):
        options = dict(cron=self.cron, log=self.log, run=fake_run(), now=NOW,
                       disk=lambda path: SimpleNamespace(free=50e9))
        options.update(kwargs)
        return incident.collect(self.root, **options)

    def codes(self, facts):
        return [f['code'] for f in incident.diagnose(facts)]

    def test_failure_codes_map_to_fixes_and_never_leak_other_fields(self):
        (self.root / 'state/private/controller-failure.json').write_text(json.dumps(dict(
            at='2026-11-01T00:30:05.123+00:00', stage='planner.tick', providers=['codex', 'claude'],
            exception_type='ValueError', reason='all_subscription_providers_failed', leaked='sk-SECRETSECRETSECRET')))
        (self.root / 'state/private/controller-run.json').write_text(json.dumps(dict(
            turn='THINK-1793493000', at='2026-11-01T00:30:04Z', state='BLOCKED', provider=None, attempts=[
                dict(provider='codex', status='FAILED', stage='planning', exception_type='TimeoutError', reason='provider_timeout'),
                dict(provider='claude', status='FAILED', stage='planning', exception_type='ValueError', reason='an arbitrary text with a token')])))
        facts = self.facts()
        output = json.dumps(dict(facts=facts, findings=incident.diagnose(facts)))
        self.assertNotIn('SECRET', output)
        self.assertNotIn('arbitrary', output)
        codes = self.codes(facts)
        self.assertEqual(codes[0], 'PLANNER_ALL_SUBSCRIPTION_PROVIDERS_FAILED')
        self.assertIn('PROVIDER_CODEX_PROVIDER_TIMEOUT', codes)
        self.assertIn('PROVIDER_CLAUDE_UNKNOWN', codes)
        self.assertIn('diagnose_subscriptions.py', incident.diagnose(facts)[0]['fix'])

    def test_provider_health_is_whitelisted(self):
        (self.root / 'state/private/provider-health.json').write_text(json.dumps({
            'codex': {'failures': 4, 'at': int(NOW) - 3600, 'reason': 'provider_timeout', 'note': 'sk-SECRETSECRETSECRET'},
            'claude': {'failures': 'x', 'at': 1}}))
        facts = self.facts()
        self.assertEqual(facts['provider_health'], {'codex': {'failures': 4, 'minutes_since': 60.0, 'reason': 'provider_timeout'}})
        self.assertNotIn('SECRET', json.dumps(facts))

    def test_image_failure_codes_survive_collection_with_infrastructure_fixes(self):
        for reason, remedy in (('brain_image_missing', 'docker image inspect'),
                               ('brain_image_inspection_failed', 'docker info')):
            with self.subTest(reason=reason):
                (self.root / 'state/private/controller-failure.json').write_text(json.dumps(dict(
                    at='2026-11-04T12:30:00Z', stage='planner.tick', providers=['codex', 'claude'],
                    exception_type='RuntimeError', reason=reason)))
                finding = incident.diagnose(self.facts())[0]
                self.assertEqual(finding['code'], 'PLANNER_' + reason.upper())
                self.assertIn(remedy, finding['fix'])
                self.assertNotIn('login_subscriptions', finding['fix'])

    def test_installed_revision_is_reported_only_as_a_hash(self):
        (self.root / 'control').mkdir()
        (self.root / 'control' / 'REVISION').write_text('9f3499e4a788747ce2ea8b39e48bac58f2b50c7d\n')
        self.assertEqual(self.facts()['installed_revision'], '9f3499e4a788747ce2ea8b39e48bac58f2b50c7d')
        (self.root / 'control' / 'REVISION').write_text('token=abc')
        self.assertEqual(self.facts()['installed_revision'], 'unreadable')

    def test_cron_paused_by_interrupted_upgrade_is_found_with_restore_command(self):
        self.cron.unlink()
        backup = self.root / 'backups' / 'upgrade-20261101T002900Z'
        backup.mkdir(parents=True)
        (backup / 'cron-globalland-think').write_text('job')
        findings = incident.diagnose(self.facts())
        self.assertEqual(findings[0]['code'], 'CRON_PAUSED_BY_UPGRADE')
        self.assertIn('install -m 644', findings[0]['fix'])

    def test_silent_log_with_cron_present_means_cron_not_running(self):
        os.utime(self.log, (NOW - 6 * 3600, NOW - 6 * 3600))
        self.assertIn('CRON_NOT_RUNNING', self.codes(self.facts()))

    def test_held_lock_and_old_supervisor_process_is_reported_as_stuck(self):
        lock = self.root / 'state' / 'supervisor.lock'
        lock.write_text('')
        with open(lock, 'a') as holder:
            fcntl.flock(holder, fcntl.LOCK_EX)
            facts = self.facts(run=fake_run(ps='  4242  21600 /usr/bin/python3 /opt/globalland/control/supervisor.py think\n  99 5 bash\n'))
        self.assertTrue(facts['lock_held'])
        self.assertEqual(facts['supervisor_processes'], [dict(pid=4242, minutes=360.0, mode='think')])
        self.assertEqual(self.codes(facts)[0], 'SUPERVISOR_STUCK')

    def test_free_lock_is_released_after_probe(self):
        lock = self.root / 'state' / 'supervisor.lock'
        lock.write_text('')
        self.assertFalse(self.facts()['lock_held'])
        with open(lock, 'a') as again:
            fcntl.flock(again, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_docker_disk_containers_and_credentials(self):
        (self.root / 'credentials' / 'claude' / 'auth.json').unlink()
        codes = self.codes(self.facts(run=fake_run(docker_ok=None), disk=lambda path: SimpleNamespace(free=0.5e9)))
        self.assertIn('DOCKER_DOWN', codes)
        self.assertIn('DISK_LOW', codes)
        self.assertIn('CREDENTIALS_MISSING', codes)
        codes = self.codes(self.facts(run=fake_run(containers='globalland-brain-1793493000\nbad;name\n')))
        self.assertIn('LEFTOVER_CONTAINERS', codes)

    def test_healthy_host_reports_no_cause_and_cli_prints_safe_json(self):
        self.assertEqual(self.codes(self.facts()), ['NO_CAUSE_FOUND'])
        script = pathlib.Path(__file__).resolve().parents[1] / 'scripts' / 'incident.py'
        out = subprocess.run([sys.executable, str(script), str(self.root)], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(json.loads(out.stdout)['safe_to_share'])


if __name__ == '__main__':
    unittest.main()
