"""A printed failure must fail CI, even in the legacy product test runners."""
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ACTORS = pathlib.Path(__file__).resolve().parents[1] / 'products/actors'


class ActorRunnerExitTests(unittest.TestCase):
    def test_a_broken_output_contract_causes_nonzero_exit(self):
        for actor in ('rss-reader', 'link-checker', 'domain-availability', 'csv-preflight'):
            with self.subTest(actor=actor), tempfile.TemporaryDirectory() as directory:
                dest = pathlib.Path(directory) / 'actors' / actor
                shutil.copytree(ACTORS / actor, dest, ignore=shutil.ignore_patterns('__pycache__'))
                research = pathlib.Path(directory) / 'research'
                research.mkdir()
                shutil.copy(ACTORS.parent / 'research/fixture-github-blog-feed.xml', research)
                # Break the real row contract before executing the actual test runner.
                mutation = {'domain-availability': "core.is_billable=lambda row: True",
                            'csv-preflight': "core.check=lambda *a, **kw: {'ok':True,'issues':[]}"}.get(actor, "core.FIELDS=['broken']")
                script = "from src import core; " + mutation + "; import runpy; runpy.run_path('tests/run_tests.py', run_name='__main__')"
                run = subprocess.run([sys.executable, '-c', script], cwd=dest, capture_output=True, text=True, timeout=40)
                self.assertIn('FAIL', run.stdout, run.stdout + run.stderr)
                self.assertNotEqual(run.returncode, 0, run.stdout)


if __name__ == '__main__':
    unittest.main()
