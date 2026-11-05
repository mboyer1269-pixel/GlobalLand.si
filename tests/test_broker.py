"""Sprint 1: host broker, stdio MCP server and broker-enabled think turns."""
import json
import pathlib
import shutil
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
                    list_products=lambda **args: {'revision': '1' * 40, 'entries': [{'path': 'products/a.txt', 'size': 5, 'oid': '2' * 40}], 'next_cursor': None},
                    read_product=lambda path: {'path': path, 'content': 'hello', 'truncated': False},
                    recent_results=lambda: [], execute=self.execute)

    def execute(self, task):
        # The call must be journaled before any effect.
        logged = [json.loads(line) for line in self.journal.read_text().splitlines()]
        assert any(entry.get('task', {}).get('id') == task['id'] for entry in logged), 'effect before journal'
        self.executed.append(task)
        return {'status': 'DONE', 'output': json.dumps({'ok': task['action']}), 'artifacts': []}


class BrokerTests(unittest.TestCase):
    def test_world_pages_are_complete_bounded_and_validate_arguments(self):
        from broker import read_handlers
        from world import World
        world=World(pathlib.Path(self.tmp.name)/'world.sqlite3');world.bootstrap()
        for n in range(12):
            world.apply('page-create-'+str(n),dict(op='create_mission',mission_id='PAGE-'+str(n),goal='x'*10000),actor='DIRECTOR')
        class Bank:
            def snapshot(self):return dict(state='UNFUNDED')
        handlers=read_handlers(pathlib.Path(self.tmp.name),world,Bank(),lambda:dict(capabilities={},latest_task_results=[]))
        handlers['execute']=self.fake.execute
        with Broker(self.directory,TURN,handlers,max_calls=40) as b:
            overview=call(b.socket_path,'world_status')['result']['world']
            self.assertTrue(overview['projection']['truncated'])
            pages=overview['projection']['collections']['missions']['pages']
            items=[]
            for page in range(pages):
                response=call(b.socket_path,'world_status',dict(collection='missions',page=page))
                self.assertTrue(response['ok'])
                self.assertLess(len(json.dumps(response).encode()),256*1024)
                value=response['result']['world']
                self.assertEqual(value['snapshot_sha256'],overview['projection']['snapshot_sha256'])
                items.extend(value['items'])
            self.assertEqual({v['mission_id'] for v in items},{v['mission_id'] for v in world.snapshot()['missions']})
            for args in (dict(page=0),dict(collection='missions',page=True),dict(collection='../missions'),dict(collection='unknown'),dict(collection='missions',page=pages)):
                self.assertFalse(call(b.socket_path,'world_status',args)['ok'])

    def test_pending_publication_is_visible_to_the_brain(self):
        table=self.fake.table()
        table['execute']=lambda task:dict(status='DONE',output='effect recorded',
            artifacts=['products/recorded.txt'],publication='PENDING: effect recorded; publication retried next cycle. Do not resubmit.')
        with Broker(self.directory,TURN,table) as b:
            response=call(b.socket_path,'submit_action',dict(agent='BUILDER',action='EXEC',args=dict(argv=['true'],outputs=[])))
        self.assertTrue(response['ok'])
        self.assertEqual(response['result']['status'],'DONE')
        self.assertIn('Do not resubmit',response['result'].get('publication',''))
        self.assertFalse(response['result'].get('artifacts_visible',True))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/tmp'); self.addCleanup(self.tmp.cleanup)
        self.directory = pathlib.Path(self.tmp.name) / 'THINK'
        self.fake = FakeHandlers(self.directory / 'calls.jsonl')

    def broker(self, **kwargs):
        return Broker(self.directory, TURN, self.fake.table(), **kwargs)

    def test_reads_and_submits_through_the_socket_with_journal_first(self):
        with self.broker() as b:
            page=call(b.socket_path, 'list_products')
            self.assertTrue(page['ok'])
            self.assertEqual([entry['path'] for entry in page['result']['entries']], ['products/a.txt'])
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
                (call(b.socket_path, 'world_status', {'x': 1}), 'world_status accepts'),
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

    def test_refused_calls_count_toward_a_retried_turn_budget(self):
        with self.broker(max_calls=4) as b:
            call(b.socket_path, 'world_status')
            call(b.socket_path, 'world_status', {'x': 1})
            call(b.socket_path, 'submit_action', {'agent': 'DIRECTOR', 'action': 'SPEND', 'args': {}})
        with self.broker(max_calls=4) as b:
            self.assertTrue(call(b.socket_path, 'list_products')['ok'])
            self.assertIn('call budget', call(b.socket_path, 'list_products')['error'])

    def test_stop_waits_for_an_in_flight_action_and_refuses_new_calls(self):
        import threading, time
        started, release, order = threading.Event(), threading.Event(), []
        table = self.fake.table()
        def slow(task):
            started.set(); release.wait(5); order.append('action finished'); return {'status': 'DONE', 'output': ''}
        table['execute'] = slow
        b = Broker(self.directory, TURN, table); b.start()
        client = threading.Thread(target=call, args=(b.socket_path, 'submit_action', {'agent': 'DIRECTOR', 'action': 'STATUS', 'args': {}}))
        client.start(); started.wait(5)
        stopper = threading.Thread(target=lambda: (b.stop(), order.append('stopped')))
        stopper.start(); time.sleep(0.3)
        self.assertEqual(order, [])
        self.assertIn('turn ended', b.request(b'{"op": "world_status"}')['error'])
        release.set(); stopper.join(10); client.join(10)
        self.assertEqual(order, ['action finished', 'stopped'])

    def test_protocol_rules_from_the_decision_schema_are_explained(self):
        with self.broker() as b:
            response = call(b.socket_path, 'submit_action', {'agent': 'DIRECTOR', 'action': 'WORLD',
                                                             'args': {'op': 'raise_blocker', 'blocker_id': 'X', 'agent_id': 'DIRECTOR',
                                                                      'title': 't', 'category': 'OTHER', 'needs_founder': 'yes', 'detail': 'd'}})
        self.assertIn('Invalid argument type', response['error'])
        self.assertNotIn('withheld', response['error'])

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
        out = subprocess.run([shutil.which('node') or 'node', str(ROOT / 'scripts/globalland_mcp.js')], input=lines.encode(),
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

    def test_multibyte_text_survives_chunked_socket_reads(self):
        text = ('Équipe à Gatineau — café ✓ ' * 9000)
        table = self.fake.table(); table['world_status'] = lambda: {'note': text}
        with Broker(self.directory, TURN, table) as b:
            replies = self.converse(b.socket_path, [
                {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'world_status', 'arguments': {}}}])
        self.assertEqual(json.loads(replies[1]['result']['content'][0]['text'])['note'], text)

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
            brain_command('/opt/globalland', IMAGE, 'cursor', broker_dir='/tmp/x')

    def test_codex_broker_turn_gets_only_the_globalland_server_preapproved_and_required(self):
        argv = brain_command('/opt/globalland', IMAGE, 'codex', broker_dir='/opt/globalland/state/broker/THINK-1')
        self.assertIn('type=bind,src=/opt/globalland/state/broker/THINK-1,dst=/broker,readonly', argv)
        self.assertIn('type=bind,src=/opt/globalland/control/globalland_mcp.js,dst=/globalland_mcp.js,readonly', argv)
        overrides = [argv[i + 1] for i, a in enumerate(argv) if a == '-c']
        self.assertNotIn('mcp_servers={}', overrides)
        servers = {o.split('.')[1] for o in overrides if o.startswith('mcp_servers.')}
        self.assertEqual(servers, {'globalland'})
        for expected in ('mcp_servers.globalland.command="node"', 'mcp_servers.globalland.args=["/globalland_mcp.js"]',
                         'mcp_servers.globalland.env={GLOBALLAND_BROKER="/broker/broker.sock"}', 'mcp_servers.globalland.required=true',
                         'mcp_servers.globalland.default_tools_approval_mode="approve"',
                         'mcp_servers.globalland.enabled_tools=["world_status", "list_products", "read_product", "recent_results", "submit_action"]',
                         'approval_policy="never"', 'features.shell_tool=false', 'web_search="disabled"', 'apps._default.enabled=false'):
            self.assertIn(expected, overrides)
        self.assertEqual(argv[argv.index('--sandbox') + 1], 'read-only')
        self.assertEqual(argv[-1], '-')
        # Each override value must parse as TOML, as Codex parses it.
        import tomllib
        for o in overrides:
            key, value = o.split('=', 1)
            tomllib.loads('v = ' + value)

    def test_codex_without_broker_keeps_mcp_disabled(self):
        argv = brain_command('/opt/globalland', IMAGE, 'codex')
        self.assertIn('mcp_servers={}', argv)
        self.assertNotIn('dst=/broker', ' '.join(argv))

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


class BrokerProvidersTests(unittest.TestCase):
    def test_broker_defaults_to_claude_and_accepts_codex_opt_in(self):
        from broker import limits
        self.assertIsNone(limits({}))
        self.assertEqual(limits({'broker': {'enabled': True}})['providers'], ['claude'])
        self.assertEqual(limits({'broker': {'enabled': True, 'providers': ['claude', 'codex']}})['providers'], ['claude', 'codex'])
        for bad in ([], ['cursor'], ['codex', 'codex'], 'codex', None):
            with self.assertRaises(ValueError):
                limits({'broker': {'enabled': True, 'providers': bad}})

    def test_codex_turn_uses_the_broker_only_when_listed(self):
        config = {'controller': {'mode': 'subscriptions', 'providers': ['codex'], 'image': IMAGE,
                                 'broker': {'enabled': True, 'providers': ['claude']}}}
        with tempfile.TemporaryDirectory() as d:
            planner = Controller(d, None, None, config)
            planner.executor = lambda task: {'status': 'DONE'}
            planner.turn_seconds = TURN
            with patch('controller.run_brain', return_value=(0, b'{}')) as run:
                planner.run_turn('codex', 'prompt')
            self.assertNotIn('dst=/broker', ' '.join(run.call_args[0][0]))
            planner.config['broker']['providers'] = ['claude', 'codex']
            with patch('controller.run_brain', return_value=(0, b'{}')) as run, patch('broker.read_handlers', return_value=dict(world_status=None, list_products=None, read_product=None, recent_results=None)):
                planner.run_turn('codex', 'prompt')
            argv = run.call_args[0][0]
            self.assertIn('dst=/broker', ' '.join(argv))
            self.assertIn('submit_action executes', run.call_args[1]['input'].decode())
            self.assertEqual(run.call_args[1]['timeout'], 900)

    def test_codex_broker_requires_the_config_flag_in_help(self):
        config = {'controller': {'mode': 'subscriptions', 'providers': ['codex'], 'subscriptions_confirmed': True,
                                 'extra_usage_disabled': True, 'image': IMAGE, 'broker': {'enabled': True, 'providers': ['codex']}}}
        old_help = ' '.join(['--ignore-user-config', '--ignore-rules', '--sandbox', '--ephemeral', '--skip-git-repo-check', '--output-schema'])
        with tempfile.TemporaryDirectory() as d, patch('controller.run_brain', return_value=(0, old_help.encode())):
            with self.assertRaisesRegex(ValueError, '--config'):
                Controller(d, None, None, config).check_provider('codex')


class BrokerPublicationTests(unittest.TestCase):
    setUp = integration.AutonomousIntegration.setUp
    git = integration.AutonomousIntegration.git

    def run(self, args=None, result=None):
        if isinstance(args, list):
            return subprocess.run(args, check=True, capture_output=True).stdout
        return super().run(args if args is not None else result)

    def test_failed_publication_reports_the_recorded_effect_instead_of_an_error(self):
        world, bank, config = self.app.services()
        task = {'id': 'TASK-%010d10' % TURN, 'type': 'TOOL', 'submitted_by': 'DIRECTOR', 'created_at': '2026-11-01T00:00:00Z',
                'action': 'WORLD', 'args': {'op': 'create_mission', 'mission_id': 'ONCE', 'goal': 'Exactly once'},
                'description': 'broker', 'estimated_cost_cad': 0, 'approved_by': None}
        self.app.refresh_work()
        with patch.object(self.app, 'finish', side_effect=RuntimeError('git push failed')):
            result = self.app.execute_tool(task, world, bank, config)
        self.assertEqual(result['status'], 'DONE')
        self.assertIn('Do not resubmit', result['publication'])
        self.assertEqual(sum(m['mission_id'] == 'ONCE' for m in world.snapshot()['missions']), 1)
        # Same identifier again: the recorded result, never a second effect.
        self.assertEqual(self.app.execute_tool(task, world, bank, config)['status'], 'DONE')
        # The next cycle publishes the pending record.
        self.app.cycle('queue')
        names = self.run(['git', '--git-dir=' + str(self.remote), 'ls-tree', '-r', '--name-only', 'main', 'queue/done']).decode()
        self.assertIn(task['id'], names)


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
        entries = [json.loads(line) for line in journal[0].read_text().splitlines()]
        # Three counted calls, and the two submitted tasks recorded before execution.
        self.assertEqual([e['op'] for e in entries if 'task' not in e], ['submit_action', 'submit_action', 'world_status'])
        self.assertEqual([e['task']['id'] for e in entries if 'task' in e], [created['result']['task_id'], refused['result']['task_id']])
        self.assertEqual(list((self.install / 'state/broker').glob('THINK-*/broker.sock')), [])
        # A later queue cycle neither replays broker actions nor fails on their journals.
        self.app.cycle('queue')
        self.assertEqual(self.remote_git('ls-tree', '-r', '--name-only', 'main', 'queue/done', 'queue/failed').decode().split(), done)


if __name__ == '__main__':
    unittest.main()
