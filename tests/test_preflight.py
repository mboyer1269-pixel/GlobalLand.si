"""Go-live checklist: GO only when every required check passes; never reads secrets' content."""
import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import preflight

DIGEST = 'sha256:' + '1' * 64


class Done:
    returncode = 0
    stdout = '27.0'


class Usage:
    free = 50e9


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)

    def install(self, **extra):
        (self.root / 'control').mkdir(parents=True, exist_ok=True)
        config = {'executor_enabled': True, 'executor_image': 'node:22-bookworm@' + DIGEST,
                  'controller': {'mode': 'subscriptions', 'providers': ['codex', 'claude'], 'image': DIGEST}}
        config.update(extra)
        (self.root / 'control/config.json').write_text(json.dumps(config))
        (self.root / 'control/REVISION').write_text('abc123\n')
        for provider in ('codex', 'claude'):
            (self.root / 'credentials' / provider).mkdir(parents=True, exist_ok=True)
            (self.root / 'credentials' / provider / 'auth.json').write_text('{}')
        (self.root / 'state/private').mkdir(parents=True, exist_ok=True)
        os.chmod(self.root / 'state/private', 0o700)
        (self.root / 'state/cron-test').write_text('')

    def run_checks(self):
        return preflight.checks(self.root, run=lambda *a, **k: Done(), disk=lambda p: Usage())

    def test_empty_install_is_no_go_with_fixes(self):
        results = preflight.checks(self.root, run=lambda *a, **k: Done(), disk=lambda p: Usage())
        self.assertEqual(preflight.verdict(results), 'NO-GO')
        self.assertTrue(all(r['fix'] for r in results if not r['ok']))

    def test_ready_install_is_go_and_optional_gaps_are_listed(self):
        self.install()
        results = self.run_checks()
        self.assertEqual(preflight.verdict(results), 'GO', [r for r in results if not r['ok'] and r['level'] == 'REQUIRED'])
        optional = {r['check'] for r in results if r['level'] == 'OPTIONAL' and not r['ok']}
        self.assertIn('Token Apify privé (600)', optional)

    def test_single_provider_and_readable_token_are_flagged(self):
        self.install(controller={'mode': 'subscriptions', 'providers': ['claude'], 'image': DIGEST},
                     apify={'enabled': True})
        token = self.root / 'credentials/apify/token'
        token.parent.mkdir(parents=True); token.write_text('secret-value'); os.chmod(token, 0o644)
        results = {r['check']: r for r in self.run_checks()}
        self.assertFalse(results['Au moins deux fournisseurs (bascule et revue croisée)']['ok'])
        self.assertFalse(results['Token Apify privé (600)']['ok'])
        self.assertNotIn('secret-value', json.dumps(list(results.values())))


if __name__ == '__main__':
    unittest.main()
