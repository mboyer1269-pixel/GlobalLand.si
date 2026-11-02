"""A provider failure may not strand a configured working subscription."""
import json
import copy
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from controller import Controller
from treasury import Treasury
from world import World


class ProviderFailoverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        (self.root / 'state').mkdir()
        self.world = World(self.root / 'state/world.sqlite3')
        self.world.bootstrap()
        self.bank = Treasury(self.root / 'state/bank.sqlite3')
        self.image = 'sha256:' + 'a' * 64
        self.controller = Controller(self.root, self.world, self.bank, {'controller': {
            'mode': 'subscriptions', 'providers': ['codex', 'claude'],
            'subscriptions_confirmed': True, 'extra_usage_disabled': True,
            'image': self.image}})
        self.good = {'summary': 'Observe', 'actions': [{'agent': 'DIRECTOR', 'action': 'STATUS', 'args': {}}]}
        self.seen = []

    def tick(self, outcomes, now=1800000000):
        def auth(provider): self.controller.verified[provider] = True
        def transport(argv, **kwargs):
            provider = argv[argv.index(self.image) + 1]
            self.seen.append(provider)
            value = outcomes[provider]
            if callable(value): value = value()
            if isinstance(value, Exception): raise value
            if provider == 'claude':
                value = {'type': 'result', 'subtype': 'success', 'is_error': False, 'structured_output': value}
            return 0, json.dumps(value).encode()
        with patch.object(self.controller, 'check_provider', side_effect=auth), patch('controller.run_brain', side_effect=transport):
            return self.controller.tick(now)

    def test_timeout_uses_the_other_configured_provider_and_persists_its_batch(self):
        turn, files = self.tick({'codex': TimeoutError('command timed out'), 'claude': self.good})
        self.assertEqual(self.seen, ['codex', 'claude'])
        self.assertEqual(len(files), 1)
        saved = json.loads((self.root / 'state/controller' / (turn + '.json')).read_text())
        self.assertEqual(saved['provider'], 'claude')
        self.assertEqual(saved['attempts'][0]['reason'], 'provider_timeout')
        self.assertEqual(saved['attempts'][1]['status'], 'SUCCEEDED')
        self.assertEqual(self.bank.snapshot()['state'], 'UNFUNDED')

    def test_invalid_envelope_discards_the_entire_first_batch_before_trying_next(self):
        bad = {'summary': 'Wrong path', 'actions': [self.good['actions'][0], {
            'agent': 'BUILDER', 'action': 'EXEC', 'args': {'argv': ['node'], 'outputs': [], 'cwd': '/etc'}}]}
        turn, files = self.tick({'codex': bad, 'claude': self.good})
        self.assertEqual(self.seen, ['codex', 'claude'])
        self.assertEqual(len(files), 1)
        self.assertEqual(json.loads(next(iter(files.values())))['description'], 'Observe')
        saved = json.loads((self.root / 'state/controller' / (turn + '.json')).read_text())
        self.assertEqual(saved['attempts'][0]['stage'], 'task_validation')
        self.assertEqual(saved['attempts'][0]['reason'], 'invalid_task_path')

    def test_all_failed_providers_are_attempted_once_without_creating_tasks(self):
        secret = 'sk-' + 'x' * 32
        with self.assertRaisesRegex(ValueError, 'all configured subscription providers failed'):
            self.tick({'codex': TimeoutError('API_KEY=' + secret), 'claude': ValueError('private account detail')})
        self.assertEqual(self.seen, ['codex', 'claude'])
        self.assertEqual(list((self.root / 'state/controller').glob('THINK-*.json')), [])
        status = self.controller.last_status()
        self.assertEqual(status['state'], 'BLOCKED')
        self.assertEqual(len(status['attempts']), 2)
        text = json.dumps(status)
        self.assertNotIn(secret, text)
        self.assertNotIn('private account detail', text)

    def test_secret_detection_stops_without_asking_another_provider(self):
        bad = dict(self.good, summary='API_KEY=' + 'x' * 30)
        with self.assertRaisesRegex(ValueError, 'secret pattern detected'):
            self.tick({'codex': bad, 'claude': self.good})
        self.assertEqual(self.seen, ['codex'])
        self.assertEqual(list((self.root / 'state/controller').glob('THINK-*.json')), [])

    def test_host_permission_failure_is_not_hidden_by_provider_failover(self):
        with self.assertRaises(PermissionError):
            self.tick({'codex': PermissionError('private path'), 'claude': self.good})
        self.assertEqual(self.seen, ['codex'])

    def test_pending_publication_replays_without_another_model_invocation(self):
        first = self.tick({'codex': TimeoutError(), 'claude': self.good})
        self.assertEqual(self.tick({}, now=1800000300), first)
        self.assertEqual(self.seen, ['codex', 'claude'])

    def test_pending_outbox_repairs_status_after_the_final_status_write_was_interrupted(self):
        original = self.controller.record_status
        def record(turn, state, provider, attempts):
            if state == 'DECISION_READY': raise OSError('interrupted status write')
            return original(turn, state, provider, attempts)
        with patch.object(self.controller, 'record_status', side_effect=record):
            with self.assertRaisesRegex(OSError, 'interrupted status write'):
                self.tick({'codex': TimeoutError(), 'claude': self.good})
        self.assertEqual(self.controller.last_status()['state'], 'RETRYING')
        self.tick({}, now=1800000300)
        self.assertEqual(self.seen, ['codex', 'claude'])
        status = self.controller.last_status()
        self.assertEqual(status['state'], 'DECISION_READY')
        self.assertEqual(status['provider'], 'claude')
        self.assertEqual(status['attempts'][-1]['status'], 'SUCCEEDED')

    def test_uncertain_container_cleanup_stops_before_any_other_provider(self):
        from types import SimpleNamespace
        with patch.object(self.controller, 'check_provider'), patch('controller.bounded_run', side_effect=TimeoutError()) as run, patch(
                'controller.subprocess.run', side_effect=[SimpleNamespace(returncode=1), SimpleNamespace(returncode=0, stdout=b'container-still-running\n')]):
            with self.assertRaisesRegex(RuntimeError, 'cleanup'):
                self.controller.tick(1800000000)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(self.controller.last_status()['attempts'][0]['reason'], 'container_cleanup_unverified')

    def test_cleanup_accepts_confirmed_absence_but_not_an_unavailable_docker_daemon(self):
        from controller import cleanup_brain
        from types import SimpleNamespace
        for status in (0, 1):
            with self.subTest(list_exit=status), patch('controller.subprocess.run', side_effect=[
                    SimpleNamespace(returncode=1), SimpleNamespace(returncode=status, stdout=b'')]):
                if status:
                    with self.assertRaisesRegex(RuntimeError, 'cleanup'): cleanup_brain('globalland-brain-fixture')
                else:
                    cleanup_brain('globalland-brain-fixture')

    def test_public_status_rejects_unknown_fields_or_nonallowlisted_text(self):
        self.tick({'codex': self.good})
        path = self.root / 'state/private/controller-run.json'
        original = json.loads(path.read_text())
        variants = [dict(original, debug='private exception text'), dict(original, provider='private account')]
        bad = copy.deepcopy(original)
        bad['attempts'][0]['reason'] = 'private exception text'
        variants.append(bad)
        for value in variants:
            with self.subTest(fields=list(value)):
                path.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError, 'invalid controller status'):
                    self.controller.last_status()

    def test_successful_turns_preserve_rotation_after_failover(self):
        first, _ = self.tick({'codex': TimeoutError(), 'claude': self.good})
        self.controller.mark_published(first)
        self.seen.clear()
        self.tick({'claude': self.good}, now=1800000300)
        self.assertEqual(self.seen, ['claude'])

    def test_extinction_between_attempts_stops_before_another_invocation(self):
        terminal = False
        def failed():
            nonlocal terminal
            terminal = True
            return TimeoutError()
        with patch.object(self.bank, 'snapshot', side_effect=lambda: {'state': 'EXTINCT' if terminal else 'UNFUNDED'}):
            with self.assertRaisesRegex(ValueError, 'stopped'):
                self.tick({'codex': failed, 'claude': self.good})
        self.assertEqual(self.seen, ['codex'])


class ProviderCircuitBreakerTests(unittest.TestCase):
    """Agent-Reach pattern: a provider that just failed goes last, never out."""
    setUp = ProviderFailoverTests.setUp
    tick = ProviderFailoverTests.tick

    def publish_all(self, *extra):
        # Extra published records shift the rotation so that codex would lead without the pause.
        for name in extra:
            (self.root / 'state/controller' / name).write_text(json.dumps({'published': True}))
        for path in (self.root / 'state/controller').glob('THINK-*.json'):
            path.write_text(json.dumps(dict(json.loads(path.read_text()), published=True)))

    def health(self):
        return json.loads((self.root / 'state/private/provider-health.json').read_text())

    def test_failed_provider_goes_last_on_the_next_cycle_then_recovers_its_turn(self):
        self.tick({'codex': TimeoutError('command timed out'), 'claude': self.good}, now=1800000000)
        self.assertEqual(self.seen, ['codex', 'claude'])
        self.assertEqual(self.health(), {'codex': {'failures': 1, 'at': 1800000000, 'reason': 'provider_timeout'}})
        self.publish_all('THINK-1799999999.json')  # rotation alone would now start with codex
        self.seen.clear()
        self.tick({'codex': self.good, 'claude': self.good}, now=1800000000 + 600)
        self.assertEqual(self.seen, ['claude'])
        # After the pause (30 min for a first failure) codex may lead again and success clears it.
        self.publish_all('THINK-1799999998.json')
        self.seen.clear()
        self.tick({'codex': self.good, 'claude': self.good}, now=1800000000 + 1900)
        self.assertEqual(self.seen, ['codex'])
        self.assertEqual(self.health(), {})

    def test_observed_incident_success_success_then_same_provider_blocked_every_cycle(self):
        # VPS, 31 oct. : cinq tours réussis puis CONTROLLER_BLOCKED, le même
        # fournisseur rechoisi à chaque cron. Ici : deux succès, puis claude
        # refusé (quota) à chaque cycle de 30 min ; chaque cycle doit quand
        # même produire une décision par codex.
        quota = lambda: ValueError('subscription auth/quota/CLI blocker; no paid fallback')
        now = 1800000000
        providers = []
        for cycle in range(6):
            outcomes = {'codex': self.good, 'claude': self.good if cycle < 2 else quota()}
            self.seen.clear()
            turn, files = self.tick(outcomes, now=now + cycle * 1800)
            self.assertEqual(len(files), 1, (cycle, self.seen))
            saved = json.loads((self.root / 'state/controller' / (turn + '.json')).read_text())
            providers.append(saved['provider'])
            if cycle >= 2:
                self.assertIn('codex', self.seen)
                self.assertLessEqual(self.seen.count('claude'), 1)
            self.publish_all()
        self.assertEqual(providers[2:], ['codex'] * 4)
        self.assertGreaterEqual(self.health()['claude']['failures'], 1)

    def test_paused_provider_is_still_tried_when_the_healthy_one_fails(self):
        (self.root / 'state/private').mkdir(parents=True, exist_ok=True)
        (self.root / 'state/private/provider-health.json').write_text(json.dumps(
            {'codex': {'failures': 3, 'at': 1800000000 - 60, 'reason': 'provider_timeout'}}))
        turn, files = self.tick({'codex': self.good, 'claude': TimeoutError('command timed out')})
        self.assertEqual(self.seen, ['claude', 'codex'])
        self.assertEqual(len(files), 1)

    def test_pause_grows_with_repeated_failures_and_is_capped(self):
        from controller import provider_paused, provider_order
        now = 1800000000
        self.assertTrue(provider_paused({'failures': 1, 'at': now - 1799}, now))
        self.assertFalse(provider_paused({'failures': 1, 'at': now - 1800}, now))
        self.assertTrue(provider_paused({'failures': 3, 'at': now - 7000}, now))
        self.assertFalse(provider_paused({'failures': 50, 'at': now - 6 * 3600}, now))
        for bad in (None, 'x', {'failures': '1', 'at': now}, {'failures': 0, 'at': now}, {'failures': True, 'at': now}):
            self.assertFalse(provider_paused(bad, now))
        self.assertEqual(provider_order(['codex', 'claude'], {'codex': {'failures': 1, 'at': now}}, now), ['claude', 'codex'])
        self.assertEqual(provider_order(['codex', 'claude'], {'codex': {'failures': 1, 'at': now}, 'claude': {'failures': 1, 'at': now}}, now),
                         ['codex', 'claude'])

    def test_unwritable_health_file_never_stops_the_failover(self):
        with patch('controller.atomic_json', side_effect=lambda path, value: (_ for _ in ()).throw(OSError('disk full'))
                   if path.name == 'provider-health.json' else __import__('supervisor').atomic_json(path, value)):
            turn, files = self.tick({'codex': TimeoutError('command timed out'), 'claude': self.good})
        self.assertEqual(self.seen, ['codex', 'claude'])
        self.assertEqual(len(files), 1)


if __name__ == '__main__': unittest.main()
