"""Contract between brain_command and the real provider CLIs.

The unit tests always run. The real-CLI tests run only with
GLOBALLAND_CLI_CONTRACT=1 and an installed CLI; they never log in, never call a
model and never spend: `codex doctor` only loads the configuration.

Limit: this proves that the argv's keys are recognized and that the five
feature flags below are off. It is not an inventory of every tool the model
may receive: other flags stay enabled and some tools depend on the model.
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


FORBIDDEN_FEATURES = ('shell_tool', 'view_image', 'image_generation', 'multi_agent', 'hooks')


def config_load_problems(report):
    """Problems in `codex doctor --json` config.load; [] only for a full, clean load."""
    check = report.get('checks', {}).get('config.load')
    if not isinstance(check, dict):
        return ['config.load check missing']
    if check.get('status') != 'ok':
        return ['config.load status %r' % check.get('status')]
    details = check.get('details') or {}
    problems = []
    if 'startup warning' in details:
        problems.append('startup warning: %s' % details['startup warning'])
    if not isinstance(details.get('enabled feature flags'), str):
        return problems + ['enabled feature flags missing']
    enabled = {f.strip() for f in details['enabled feature flags'].split(',')}
    problems += ['feature enabled: ' + f for f in FORBIDDEN_FEATURES if f in enabled]
    return problems


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


class ConfigLoadProblemsTests(unittest.TestCase):
    """A failed or partial `codex doctor` report must never read as a pass."""
    def report(self, status='ok', **details):
        return {'checks': {'config.load': {'status': status, 'details': details}}}

    def test_failed_configuration_load_is_a_problem(self):
        # Shape of Codex 0.166.0 with -c forced_login_method="invalid".
        failed = {'checks': {'config.load': {'status': 'fail', 'summary': 'config could not be loaded',
                                             'details': {'error': 'invalid value'}}}}
        self.assertTrue(config_load_problems(failed))

    def test_missing_feature_list_is_a_problem(self):
        self.assertTrue(config_load_problems(self.report()))

    def test_missing_config_check_is_a_problem(self):
        self.assertTrue(config_load_problems({'checks': {}}))

    def test_startup_warning_is_a_problem(self):
        self.assertTrue(config_load_problems(self.report(**{
            'enabled feature flags': 'sqlite', 'startup warning': '`tools.view_image` is ignored.'})))

    def test_enabled_builtin_tool_is_a_problem(self):
        self.assertTrue(config_load_problems(self.report(**{'enabled feature flags': 'sqlite, view_image'})))

    def test_clean_report_has_no_problem(self):
        self.assertEqual(config_load_problems(self.report(**{'enabled feature flags': 'sqlite, apps'})), [])


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
            # Includes the broker's mcp_servers.globalland.* keys: doctor only
            # loads them (syntax); the bridge itself is proven on the VPS.
            values = overrides(codex_cli(argv))
            args = ['doctor', '--json']
            for value in values:
                args += ['-c', value]
            with self.subTest(name), tempfile.TemporaryDirectory() as home:
                result = self.run_cli(args, home, timeout=120)
                self.assertEqual(config_load_problems(json.loads(result.stdout)), [])

    def test_the_check_detects_an_invalid_value_with_the_real_cli(self):
        # Guards against a false green: a configuration that fails to load
        # has no warning and no feature list.
        with tempfile.TemporaryDirectory() as home:
            result = self.run_cli(['doctor', '--json', '-c', 'forced_login_method="invalid"'], home, timeout=120)
        self.assertTrue(config_load_problems(json.loads(result.stdout)))


if __name__ == '__main__':
    unittest.main()
