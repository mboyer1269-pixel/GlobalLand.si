"""Contract between brain_command and the real provider CLIs.

The unit tests always run. The real-CLI tests run only with
GLOBALLAND_CLI_CONTRACT=1 and an installed CLI; they never log in, never call a
model and never spend: `codex doctor` only loads the configuration.
"""
import json, os, pathlib, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from controller import brain_command

IMAGE = 'sha256:' + 'a' * 64
# Built-in Codex tools that a decision turn must never have.
CODEX_TOOLS_OFF = ('features.shell_tool=false', 'features.view_image=false',
                   'features.image_generation=false', 'features.multi_agent=false',
                   'features.hooks=false')


def codex_variants():
    """Both Codex argv shapes: plain turn and broker turn."""
    plain = brain_command('/opt/globalland', IMAGE, 'codex')
    broker = brain_command('/opt/globalland', IMAGE, 'codex', broker_dir='/tmp/gl-broker')
    return {'plain': plain, 'broker': broker}


def codex_cli(argv):
    """The CLI part of a brain argv, starting at the `codex` program."""
    return argv[argv.index(IMAGE) + 1:]


def overrides(cli):
    return [cli[i + 1] for i, a in enumerate(cli) if a == '-c']


class CodexArgvTests(unittest.TestCase):
    def test_exec_subcommand_comes_first(self):
        for name, argv in codex_variants().items():
            with self.subTest(name):
                cli = codex_cli(argv)
                self.assertEqual(cli[:2], ['codex', 'exec'])

    def test_builtin_tools_are_disabled_with_keys_the_cli_recognizes(self):
        for name, argv in codex_variants().items():
            with self.subTest(name):
                values = overrides(codex_cli(argv))
                for expected in CODEX_TOOLS_OFF:
                    self.assertIn(expected, values)
                # Codex 0.166.0 reports `tools.view_image` as ignored.
                self.assertFalse([v for v in values if v.startswith('tools.view_image')])


def contract_enabled():
    return os.environ.get('GLOBALLAND_CLI_CONTRACT') == '1'


@unittest.skipUnless(contract_enabled(), 'real CLI contract requires GLOBALLAND_CLI_CONTRACT=1')
class CodexRealCliContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codex = shutil.which(os.environ.get('GLOBALLAND_CODEX_BIN', 'codex'))
        if not cls.codex:
            raise unittest.SkipTest('codex CLI not installed')

    def run_cli(self, args, home, timeout=60):
        env = {k: v for k, v in os.environ.items() if not k.endswith(('_KEY', '_TOKEN'))}
        env['CODEX_HOME'] = home
        return subprocess.run([self.codex] + args, env=env, capture_output=True,
                              timeout=timeout, cwd=home)

    def test_every_flag_is_documented_by_exec_help(self):
        with tempfile.TemporaryDirectory() as home:
            helptext = self.run_cli(['exec', '--help'], home).stdout.decode()
        for name, argv in codex_variants().items():
            for flag in [a for a in codex_cli(argv) if a.startswith('--')]:
                with self.subTest(variant=name, flag=flag):
                    self.assertIn(flag, helptext)

    def test_global_position_of_exec_flags_is_rejected(self):
        with tempfile.TemporaryDirectory() as home:
            result = self.run_cli(['--ignore-user-config', '--ignore-rules', 'exec', '--help'], home)
        self.assertEqual(result.returncode, 2)

    def test_overrides_are_recognized_and_disable_builtin_tools(self):
        for name, argv in codex_variants().items():
            # The GlobalLand MCP server needs the broker bridge; its keys are
            # checked by the broker smoke test, not here.
            values = [v for v in overrides(codex_cli(argv))
                      if not v.startswith('mcp_servers.globalland.')]
            args = ['doctor', '--json']
            for value in values:
                args += ['-c', value]
            with self.subTest(name), tempfile.TemporaryDirectory() as home:
                result = self.run_cli(args, home, timeout=120)
                report = json.loads(result.stdout)
                details = report['checks']['config.load']['details']
                self.assertNotIn('startup warning', details, details.get('startup warning'))
                enabled = {f.strip() for f in details.get('enabled feature flags', '').split(',')}
                for feature in ('shell_tool', 'view_image', 'image_generation', 'multi_agent', 'hooks'):
                    self.assertNotIn(feature, enabled)


if __name__ == '__main__':
    unittest.main()
