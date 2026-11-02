"""Exercise model working directories through task validation and durable output."""
import copy
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from controller import Controller
from tools import validate_envelope
from treasury import Treasury
from world import World


class ModelWorkingDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = pathlib.Path(self.directory.name)
        state = self.root / 'state'
        state.mkdir()
        world = World(state / 'world.sqlite3')
        world.bootstrap()
        bank = Treasury(state / 'bank.sqlite3')
        self.controller = Controller(self.root, world, bank, {'controller': {
            'mode': 'subscriptions', 'providers': ['codex'],
            'subscriptions_confirmed': True, 'extra_usage_disabled': True,
            'image': 'sha256:' + 'a' * 64,
        }})

    def action(self, cwd):
        return {'agent': 'BUILDER', 'action': 'EXEC', 'args': {
            'argv': ['node', '-e', 'console.log("world")'],
            'outputs': [], 'cwd': cwd, 'mission_id': None,
        }}

    def tick(self, actions):
        wire = {'summary': 'Build a product', 'actions': actions}
        before = copy.deepcopy(wire)
        with patch.object(self.controller, 'check_provider'), patch(
                'controller.run_brain', return_value=(0, json.dumps(wire).encode())):
            result = self.controller.tick(now=1800000000)
        self.assertEqual(wire, before)
        return result

    def test_workspace_root_aliases_become_executable_durable_tasks(self):
        turn, files = self.tick([self.action(cwd) for cwd in
                                 ('', '.', './', '/workspace', '/workspace/')])
        self.assertEqual(len(files), 5)
        for text in files.values():
            task = validate_envelope(json.loads(text))
            self.assertEqual(task['args'], {
                'argv': ['node', '-e', 'console.log("world")'], 'outputs': [],
            })
        outbox = json.loads((self.root / 'state/controller' / (turn + '.json')).read_text())
        self.assertEqual(outbox['files'], files)
        self.assertFalse(outbox['published'])

    def test_null_root_and_relative_subdirectory_keep_their_meaning(self):
        _, files = self.tick([self.action(None), self.action('products/project')])
        tasks = [validate_envelope(json.loads(text)) for text in files.values()]
        self.assertNotIn('cwd', tasks[0]['args'])
        self.assertEqual(tasks[1]['args']['cwd'], 'products/project')

    def test_other_absolute_or_traversing_paths_never_enter_outbox(self):
        paths = ['/etc', '/workspace/products', '/workspace/../oria',
                 '../oria', 'products/../oria', 'products//x', 'products/./x',
                 '.git', 'products/.git', 'products\\x', '/workspace//']
        for cwd in paths:
            with self.subTest(cwd=cwd):
                with self.assertRaises(ValueError):
                    self.tick([self.action(None), self.action(cwd)])
                self.assertEqual(list((self.root / 'state/controller').glob('THINK-*.json')), [])


if __name__ == '__main__':
    unittest.main()
