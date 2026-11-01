"""Upgrade pauses both GlobalLand schedules and restores them on failure."""
import os
import pathlib
import subprocess
import tempfile
import unittest


class CronPauseTests(unittest.TestCase):
    def setUp(self):
        self.helper = pathlib.Path(__file__).resolve().parents[1] / 'scripts/cron_pause.sh'
        self.assertTrue(self.helper.is_file(), 'cron pause helper missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = pathlib.Path(self.temp.name)
        self.cron = self.base / 'cron.d'
        self.backup = self.base / 'backup'
        self.cron.mkdir(); self.backup.mkdir()
        for name in ('globalland', 'globalland-think', 'oria'):
            (self.cron / name).write_text(name + '\n')

    def run_shell(self, script, env=None):
        return subprocess.run(['bash', '-c', 'set -euo pipefail\nsource "$1"\ncron_root=$2\nbackup_root=$3\n' + script,
                               'cron-test', str(self.helper), str(self.cron), str(self.backup)],
                              capture_output=True, text=True, env=env)

    def test_both_schedules_pause_and_restore_without_touching_oria(self):
        result = self.run_shell('pause_globalland_cron "$cron_root" "$backup_root"\n'
                                'test ! -e "$cron_root/globalland"\n'
                                'test ! -e "$cron_root/globalland-think"\n'
                                'restore_globalland_cron "$cron_root" "$backup_root"\n'
                                'restore_globalland_cron "$cron_root" "$backup_root"\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('globalland', 'globalland-think', 'oria'):
            self.assertEqual((self.cron / name).read_text(), name + '\n')
        self.assertEqual((self.cron / 'globalland-think').stat().st_mode & 0o777, 0o644)

    def test_partial_pause_failure_restores_the_already_moved_schedule(self):
        binary = self.base / 'bin'
        binary.mkdir()
        move = binary / 'mv'
        move.write_text('#!/bin/bash\nfor arg in "$@"; do\ncase "$arg" in */globalland-think) exit 19;; esac\ndone\nexec /bin/mv "$@"\n')
        move.chmod(0o700)
        result = self.run_shell('trap \'restore_globalland_cron "$cron_root" "$backup_root"\' EXIT\n'
                                'pause_globalland_cron "$cron_root" "$backup_root"\n',
                                env={**os.environ, 'PATH': str(binary) + os.pathsep + os.environ['PATH']})
        self.assertNotEqual(result.returncode, 0)
        for name in ('globalland', 'globalland-think', 'oria'):
            self.assertEqual((self.cron / name).read_text(), name + '\n')

    def test_existing_backup_is_not_overwritten_or_restored_over_current_jobs(self):
        (self.backup / 'cron-globalland').write_text('old backup\n')
        result = self.run_shell('trap \'restore_globalland_cron "$cron_root" "$backup_root"\' EXIT\n'
                                'pause_globalland_cron "$cron_root" "$backup_root"\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.backup / 'cron-globalland').read_text(), 'old backup\n')
        self.assertEqual((self.cron / 'globalland').read_text(), 'globalland\n')


if __name__ == '__main__': unittest.main()
