"""CLI diagnostic echo must not kill a valid decision with a large context."""
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from controller import run_brain
from supervisor import bounded_run


class BrainOutputTests(unittest.TestCase):
    def test_prompt_echo_above_64k_does_not_discard_the_decision(self):
        payload = ('Contexte utile aux agents. ' * 4000).encode()
        argv = [sys.executable, '-c',
                'import sys; data=sys.stdin.buffer.read(); '
                'sys.stderr.buffer.write(data); '
                'sys.stdout.write(\'{"summary":"observed","actions":[]}\')',
                '--name', 'globalland-brain-test']
        with patch('controller.cleanup_brain'):
            code, raw = run_brain(argv, input=payload, limit=64)
        self.assertEqual(code, 0)
        self.assertEqual(raw, b'{"summary":"observed","actions":[]}')

    def test_excessive_brain_diagnostics_are_still_stopped(self):
        argv = [sys.executable, '-c',
                'import sys; sys.stderr.buffer.write(b"x" * 2000000)',
                '--name', 'globalland-brain-test']
        with patch('controller.cleanup_brain'):
            with self.assertRaisesRegex(ValueError, 'error output limit'):
                run_brain(argv)

    def test_other_commands_keep_their_existing_stderr_bound(self):
        with self.assertRaisesRegex(ValueError, 'error output limit'):
            bounded_run([sys.executable, '-c',
                         'import sys; sys.stderr.buffer.write(b"x" * 70000)'], env=None)


if __name__ == '__main__':
    unittest.main()
