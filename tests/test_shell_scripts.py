import pathlib, subprocess, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]


class ShellSyntaxTests(unittest.TestCase):
    def test_every_shell_script_parses(self):
        scripts = sorted((ROOT / 'scripts').glob('*.sh'))
        self.assertTrue(scripts)
        for script in scripts:
            with self.subTest(script=script.name):
                result = subprocess.run(['bash', '-n', str(script)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_ci_checks_each_script_not_only_the_first(self):
        # `bash -n a.sh b.sh` parses a.sh only; b.sh becomes a positional argument.
        step = 'for f in scripts/*.sh; do bash -n "$f" || exit 1; done'
        self.assertIn(step, (ROOT / '.github/workflows/checks.yml').read_text())
        with tempfile.TemporaryDirectory() as d:
            (pathlib.Path(d) / 'scripts').mkdir()
            (pathlib.Path(d) / 'scripts/a.sh').write_text('echo ok\n')
            (pathlib.Path(d) / 'scripts/b.sh').write_text('if then\n')
            self.assertEqual(subprocess.run(['bash', '-c', 'bash -n scripts/*.sh'], cwd=d).returncode, 0)
            self.assertNotEqual(subprocess.run(['bash', '-c', step], cwd=d, capture_output=True).returncode, 0)


if __name__ == '__main__':
    unittest.main()
