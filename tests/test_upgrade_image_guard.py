"""Run the upgrader in an isolated filesystem; fake only external guard/Docker."""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
PIN = 'node:22-bookworm@sha256:' + '2' * 64


@unittest.skipUnless(os.name == 'posix', 'The VPS upgrader requires a POSIX filesystem and Bash')
class UpgradeImageGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = pathlib.Path(self.tmp.name)
        self.root, self.cron, self.checkout, self.bin = [base / p for p in ('install', 'cron', 'checkout', 'bin')]
        for path in (self.cron, self.checkout / 'scripts', self.bin):
            path.mkdir(parents=True)
        for name in ('control', 'source.git', 'state', 'ssh', 'releases'):
            (self.root / name).mkdir(parents=True)
        self.config = {'controller': {'mode': 'subscriptions', 'image': 'sha256:' + '1' * 64},
                       'executor_image': 'old-executor', 'custom_setting': {'preserve': True}}
        (self.root / 'control/config.json').write_text(json.dumps(self.config))
        (self.root / 'control/compose.yml').write_text('services:\n  core:\n    image: ' + PIN + '\n')
        for name in ('globalland', 'globalland-think', 'oria'):
            (self.cron / name).write_text(name + '\n')
        # Redirect only hard-coded host paths and the root requirement in the fixture copy.
        source = (REPO / 'scripts/upgrade_vps.sh').read_text()
        source = source.replace("[[ $EUID -eq 0 ]] || { echo 'Run with sudo'; exit 1; }", ':')
        source = source.replace('ROOT=/opt/globalland', 'ROOT=' + str(self.root))
        source = source.replace('/etc/cron.d', str(self.cron))
        (self.checkout / 'scripts/upgrade_vps.sh').write_text(source)
        shutil.copyfile(REPO / 'scripts/cron_pause.sh', self.checkout / 'scripts/cron_pause.sh')
        (self.checkout / 'scripts/placeholder.js').write_text('// fixture\n')
        (self.checkout / 'scripts/placeholder.json').write_text('{}\n')
        (self.checkout / 'scripts/image_guard.py').write_text('''import argparse,json,pathlib
p=argparse.ArgumentParser()
p.add_argument('--root');p.add_argument('--config');p.add_argument('action')
a=p.parse_args();root=pathlib.Path(a.root)
config=json.loads(pathlib.Path(a.config).read_text())
with (root/'guard-observations.jsonl').open('a') as out:
 out.write(json.dumps(config)+'\\n')
raise SystemExit(31 if (root/'guard-fail').exists() else 0)
''')
        docker = self.bin / 'docker'
        docker.write_text('#!/bin/sh\n[ "$1" = compose ] || exit 99\nexit 0\n')
        docker.chmod(0o700)
        date = self.bin / 'date'
        date.write_text('#!/bin/sh\nprintf "%s\\n" "$TEST_STAMP"\n')
        date.chmod(0o700)
        for args in (['init', '-q'], ['add', '.'],
                     ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture']):
            subprocess.run(['git', '-C', str(self.checkout), *args], check=True, capture_output=True)
        self.rev = subprocess.check_output(['git', '-C', str(self.checkout), 'rev-parse', 'HEAD'], text=True).strip()

    def upgrade(self, stamp):
        return subprocess.run(['bash', str(self.checkout / 'scripts/upgrade_vps.sh'), self.rev],
                              env={**os.environ, 'PATH': str(self.bin) + os.pathsep + os.environ['PATH'],
                                   'TEST_STAMP': stamp}, capture_output=True, text=True, timeout=30)

    def assert_cron_preserved(self):
        for name in ('globalland', 'globalland-think', 'oria'):
            self.assertEqual((self.cron / name).read_text(), name + '\n')

    def test_guard_failure_preserves_control_and_cron_without_final_release(self):
        (self.root / 'guard-fail').touch()
        result = self.upgrade('20261104T120000Z')
        self.assertEqual(result.returncode, 31, result.stdout + result.stderr)
        self.assertFalse((self.root / 'releases' / self.rev).exists(), 'failed retention must not reserve the final release')
        self.assertFalse((self.root / 'control').is_symlink())
        self.assertEqual(json.loads((self.root / 'control/config.json').read_text()), self.config)
        self.assert_cron_preserved()
        pending = json.loads((self.root / 'guard-observations.jsonl').read_text().splitlines()[0])
        self.assertEqual(pending['executor_image'], PIN)
        self.assertEqual(pending['controller'], self.config['controller'])
        self.assertEqual(pending['custom_setting'], {'preserve': True})

    def test_retry_after_image_repair_installs_validated_config_and_restores_cron(self):
        marker = self.root / 'guard-fail'
        marker.touch()
        self.assertEqual(self.upgrade('20261104T120000Z').returncode, 31)
        marker.unlink()
        result = self.upgrade('20261104T120001Z')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / 'control').is_symlink())
        self.assertEqual((self.root / 'control').resolve(), self.root / 'releases' / self.rev)
        installed = json.loads((self.root / 'control/config.json').read_text())
        self.assertEqual(installed['executor_image'], PIN)
        self.assertEqual(installed['controller'], self.config['controller'])
        self.assertEqual(installed['custom_setting'], {'preserve': True})
        self.assert_cron_preserved()


if __name__ == '__main__':
    unittest.main()
