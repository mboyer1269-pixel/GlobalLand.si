"""Sprint 1: host broker, stdio MCP server and broker-enabled think turns."""
import json
import pathlib
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import test_autonomous_integration as integration
from broker import Broker, limits
from controller import Controller, brain_command

TURN = 1793491200
IMAGE = 'brain@sha256:' + '1' * 64


def call(path, op, args=None, raw=None):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(10)
        conn.connect(str(path))
        conn.sendall(raw if raw is not None else (json.dumps({'op': op, 'args': args or {}}) + '\n').encode())
        data = b''
        while not data.endswith(b'\n'):
            chunk = conn.recv(65536)
            if not chunk:
                break
            data += chunk
        return json.loads(data)


class FakeHandlers:
    def __init__(self, journal):
        self.journal = journal
        self.executed = []

    def table(self):
        return dict(world_status=lambda: {'world': {'state': 'ACTIVE'}, 'bank': {'state': 'UNFUNDED'}},
                    list_products=lambda: ['products/a.txt'],
                    read_product=lambda path: {'path': path, 'content': 'hello', 'truncated': False},
                    recent_results=lambda: [], execute=self.execute)

    def execute(self, task):
        # The call must be journaled before any effect.
        logged = [json.loads(line) for line in self.journal.read_text().splitlines()]
        assert any(entry.get('task', {}).get('id') == task['id'] for entry in logged), 'effect before journal'
        self.executed.append(task)
        return {'status': 'DONE', 'output': json.dumps({'ok': task['action']}), 'artifacts': []}


class BrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/tmp'); self.addCleanup(self.tmp.cleanup)
        self.directory = pathlib.Path(self.tmp.name) / 'THINK'
        self.fake = FakeHandlers(self.directory / 'calls.jsonl')

    def broker(self, **kwargs):
        return Broker(self.directory, TURN, self.fake.table(), **kwargs)

    def test_reads_and_submits_through_the_socket_with_journal_first(self):
        with self.broker() as b:
            self.assertEqual(call(b.socket_path, 'list_products'), {'ok': True, 'result': ['products/a.txt']})
            self.assertTrue(call(b.socket_path, 'read_product', {'path': 'products/a.txt'})['ok'])
            first = call(b.socket_path, 'submit_action', {'agent': 'DIRECTOR', 'action': 'STATUS', 'args': {}})
            second = call(b.socket_path, 'submit_action', {'agent': 'BUILDER', 'action': 'WORLD',
                                                           'args': {'op': 'message', 'from_agent': 'BUILDER', 'to_agent': 'DIRECTOR', 'body': 'done'}})
        self.assertEqual(first['result']['task_id'], 'TASK-%010d10' % TURN)
        self.assertEqual(second['result']['task_id'], 'TASK-%010d11' % TURN)
        self.assertEqual([t['submitted_by'] for t in self.fake.executed], ['DIRECTOR', 'BUILDER'])
        task = self.fake.executed[1]
        self.assertEqual((task['type'], task['estimated_cost_cad'], task['approved_by']), ('TOOL', 0, None))
        self.assertFalse(b.socket_path.exists())
        self.assertEqual(oct(self.directory.stat().st_mode & 0o777), '0o711')

    def test_refusals_explain_the_rule_and_never_execute(self):
        with self.broker() as b:
            cases = [
                (call(b.socket_path, None, raw=b'not json\n'), 'one JSON object'),
                (call(b.socket_path, 'delete_world'), 'unknown broker operation'),
                (call(b.socket_path, 'world_status', {'x': 1}), 'takes no arguments'),
                (call(b.socket_path, 'submit_action', {'agent': 'DIRECTOR', 'action': 'SPEND', 'args': {'request': {}}}), 'SPEND and RECONCILE use the final decision'),
                (call(b.socket_path, 'submit_action', {'agent': 'DIRECTOR', 'action': 'EXEC', 'args': {'argv': ['true'], 'surprise': 1}}), 'refused'),
                (call(b.socket_path, 'submit_action', {'agent': 'DIRECTOR', 'action': 'FETCH', 'args': {'url': 'https://example.com/', 'output': '/etc/passwd'}}), 'refused'),
            ]
        for response, fragment in cases:
            with self.subTest(fragment=fragment):
                self.assertFalse(response['ok'])
                self.assertIn(fragment, response['error'])
        self.assertEqual(self.fake.executed, [])

    def test_call_and_action_budgets_are_enforced(self):
        with self.broker(max_calls=3, max_actions=1) as b:
            self.assertTrue(call(b.socket_path, 'submit_action', {'agent': 'DIRECTOR', 'action': 'STATUS', 'args': {}})['ok'])
            self.assertIn('action budget', call(b.socket_path, 'submit_action', {'agent': 'DIRECTOR', 'action': 'STATUS', 'args': {}})['error'])
            self.assertTrue(call(b.socket_path, 'world_status')['ok'])
            self.assertIn('call budget', call(b.socket_path, 'world_status')['error'])
        self.assertEqual(len(self.fake.executed), 1)

    def test_second_attempt_in_same_turn_never_reuses_a_task_slot(self):
        with self.broker() as b:
            call(b.socket_path, 'submit_action', {'agent': 'DIRECTOR', 'action': 'STATUS', 'args': {}})
        with self.broker() as b:
            again = call(b.socket_path, 'submit_action', {'agent': 'DIRECTOR', 'action': 'STATUS', 'args': {}})
        self.assertEqual(again['result']['task_id'], 'TASK-%010d11' % TURN)

    def test_configuration_is_disabled_by_default_and_bounded(self):
        self.assertIsNone(limits({}))
        self.assertIsNone(limits({'broker': {'enabled': 'yes'}}))
        self.assertEqual(limits({'broker': {'enabled': True}})['max_turns'], 40)
        with self.assertRaises(ValueError):
            limits({'broker': {'enabled': True, 'max_actions': 95}})


class McpServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/tmp'); self.addCleanup(self.tmp.cleanup)
        self.directory = pathlib.Path(self.tmp.name) / 'THINK'
        self.fake = FakeHandlers(self.directory / 'calls.jsonl')

    def converse(self, socket_path, messages):
        lines = '\n'.join(json.dumps(m) for m in messages) + '\n'
        out = subprocess.run(['node', str(ROOT / 'scripts/globalland_mcp.js')], input=lines.encode(),
                             env={'GLOBALLAND_BROKER': str(socket_path), 'PATH': '/usr/bin:/bin:/usr/local/bin:/opt/node22/bin'},
                             capture_output=True, timeout=30, check=True).stdout.decode()
        return {r['id']: r for r in map(json.loads, out.splitlines())}

    def test_mcp_lists_tools_and_forwards_calls_to_the_broker(self):
        with Broker(self.directory, TURN, self.fake.table()) as b:
            replies = self.converse(b.socket_path, [
                {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 't', 'version': '1'}}},
                {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'submit_action', 'arguments': {'agent': 'DIRECTOR', 'action': 'STATUS', 'args': {}}}},
                {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'world_status', 'arguments': {'x': 1}}},
                {'jsonrpc': '2.0', 'id': 5, 'method': 'tools/call', 'params': {'name': 'rm_rf', 'arguments': {}}},
                {'jsonrpc': '2.0', 'id': 6, 'method': 'resources/list'},
            ])
        self.assertEqual(replies[1]['result']['protocolVersion'], '2025-06-18')
        self.assertEqual({t['name'] for t in replies[2]['result']['tools']},
                         {'world_status', 'list_products', 'read_product', 'recent_results', 'submit_action'})
        self.assertFalse(replies[3]['result']['isError'])
        self.assertEqual(json.loads(replies[3]['result']['content'][0]['text'])['task_id'], 'TASK-%010d10' % TURN)
        self.assertTrue(replies[4]['result']['isError'])
        self.assertEqual(replies[5]['error']['code'], -32602)
        self.assertEqual(replies[6]['error']['code'], -32601)

    def test_unavailable_broker_is_a_tool_error_not_a_crash(self):
        replies = self.converse(self.directory / 'missing.sock', [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'world_status', 'arguments': {}}}])
        self.assertTrue(replies[1]['result']['isError'])
        self.assertIn('unavailable', replies[1]['result']['content'][0]['text'])


class BrainCommandTests(unittest.TestCase):
    def test_broker_turn_offers_only_globalland_tools_through_read_only_mounts(self):
        argv = brain_command('/opt/globalland', IMAGE, 'claude', broker_dir='/opt/globalland/state/broker/THINK-1', max_turns=40)
        self.assertIn('type=bind,src=/opt/globalland/state/broker/THINK-1,dst=/broker,readonly', argv)
        self.assertIn('type=bind,src=/opt/globalland/control/globalland_mcp.js,dst=/globalland_mcp.js,readonly', argv)
        self.assertEqual(argv[argv.index('--allowedTools') + 1], 'mcp__globalland')
        self.assertEqual(argv[argv.index('--tools') + 1], '')
        self.assertEqual(argv[argv.index('--max-turns') + 1], '40')
        self.assertNotIn('--disallowedTools', argv)
        # --safe-mode drops --mcp-config servers; customizations are excluded explicitly.
        self.assertNotIn('--safe-mode', argv)
        self.assertEqual(argv[argv.index('--setting-sources') + 1], '')
        self.assertIn('--disable-slash-commands', argv)
        self.assertNotIn('credentials', ' '.join(a for a in argv if 'dst=/broker' in a))
        servers = json.loads(argv[argv.index('--mcp-config') + 1])['mcpServers']
        self.assertEqual(list(servers), ['globalland'])
        with self.assertRaises(ValueError):
            brain_command('/opt/globalland', IMAGE, 'codex', broker_dir='/tmp/x')

    def test_without_broker_the_command_is_unchanged(self):
        argv = brain_command('/opt/globalland', IMAGE, 'claude')
        self.assertIn('--disallowedTools', argv)
        self.assertNotIn('--allowedTools', argv)
        self.assertNotIn('dst=/broker', ' '.join(argv))


class ProviderCheckTests(unittest.TestCase):
    def test_broker_turns_require_the_cli_isolation_flags(self):
        config = {'controller': {'mode': 'subscriptions', 'providers': ['claude'], 'subscriptions_confirmed': True,
                                 'extra_usage_disabled': True, 'image': IMAGE, 'broker': {'enabled': True}}}
        old_help = ' '.join(['--safe-mode', '--tools', '--disallowedTools', '--strict-mcp-config', '--mcp-config',
                             '--json-schema', '--no-session-persistence', '--permission-prompts', '--max-turns'])
        with tempfile.TemporaryDirectory() as d, patch('controller.run_brain', return_value=(0, old_help.encode())):
            with self.assertRaisesRegex(ValueError, '--allowedTools, --setting-sources, --disable-slash-commands'):
                Controller(d, None, None, config).check_provider('claude')


class BrokerThinkIntegration(unittest.TestCase):
    setUp = integration.AutonomousIntegration.setUp
    git = integration.AutonomousIntegration.git

    def run(self, args=None, result=None):
        if isinstance(args, list):
            return subprocess.run(args, check=True, capture_output=True).stdout
        return super().run(args if args is not None else result)

    def remote_git(self, *args):
        return self.run(['git', '--git-dir=' + str(self.remote), *args])

    def test_brain_acts_observes_and_decides_within_one_turn(self):
        config = {'executor_enabled': False, 'controller': {
            'mode': 'subscriptions', 'providers': ['claude'], 'subscriptions_confirmed': True,
            'extra_usage_disabled': True, 'image': IMAGE,
            'broker': {'enabled': True, 'max_calls': 10, 'max_actions': 3, 'turn_timeout_seconds': 600, 'max_turns': 30}}}
        (self.install / 'control/config.json').write_text(json.dumps(config))
        seen = {}

        def brain(argv, **kwargs):
            seen['timeout'] = kwargs.get('timeout')
            seen['prompt'] = kwargs['input'].decode()
            mount = next(a for a in argv if a.endswith('dst=/broker,readonly'))
            sock = pathlib.Path(mount.split(',')[1][len('src='):]) / 'broker.sock'
            created = call(sock, 'submit_action', {'agent': 'DIRECTOR', 'action': 'WORLD',
                                                   'args': {'op': 'create_mission', 'mission_id': 'BROKER-MISSION', 'goal': 'Prove the loop'}})
            refused = call(sock, 'submit_action', {'agent': 'BUILDER', 'action': 'EXEC', 'args': {'argv': ['true'], 'outputs': []}})
            observed = call(sock, 'world_status')
            seen['responses'] = (created, refused, observed)
            decision = {'summary': 'Mission created in-turn', 'actions': []}
            return 0, json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False, 'structured_output': decision}).encode()

        with patch.object(Controller, 'check_provider'), patch('controller.run_brain', side_effect=brain):
            self.app.cycle('think')

        created, refused, observed = seen['responses']
        self.assertEqual(seen['timeout'], 600)
        self.assertIn('submit_action', seen['prompt'])
        self.assertEqual(created['result']['status'], 'DONE')
        self.assertEqual(refused['result']['status'], 'REJECTED')
        self.assertIn('executor not configured', refused['result']['output'])
        self.assertTrue(any(m['mission_id'] == 'BROKER-MISSION' for m in observed['result']['world']['missions']))
        done = self.remote_git('ls-tree', '-r', '--name-only', 'main', 'queue/done', 'queue/failed').decode().split()
        created_id, refused_id = created['result']['task_id'], refused['result']['task_id']
        self.assertIn('queue/done/%s.result.json' % created_id, done)
        self.assertIn('queue/failed/%s.result.json' % refused_id, done)
        published = json.loads(self.remote_git('show', 'main:queue/done/%s.result.json' % created_id))
        self.assertEqual(published['request']['args']['mission_id'], 'BROKER-MISSION')
        self.assertEqual(json.loads(self.remote_git('show', 'main:world/controller.json'))['state'], 'OPERATIONAL')
        journal = list((self.install / 'state/broker').glob('THINK-*/calls.jsonl'))
        self.assertEqual(len(journal), 1)
        self.assertEqual(len(journal[0].read_text().splitlines()), 3)
        self.assertEqual(list((self.install / 'state/broker').glob('THINK-*/broker.sock')), [])
        # A later queue cycle neither replays broker actions nor fails on their journals.
        self.app.cycle('queue')
        self.assertEqual(self.remote_git('ls-tree', '-r', '--name-only', 'main', 'queue/done', 'queue/failed').decode().split(), done)


if __name__ == '__main__':
    unittest.main()
