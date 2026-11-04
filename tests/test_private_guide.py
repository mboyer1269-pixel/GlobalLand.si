"""Host-selected private guide cannot be followed by contradictory public instructions."""
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from controller import Controller, TOOL_GUIDE


class PrivateGuideTests(unittest.TestCase):
    def test_private_guide_replaces_public_guide(self):
        with tempfile.TemporaryDirectory() as root:
            planner = Controller(root, None, None, {'controller': {}})
            planner.tool_guide = 'HOST PRIVATE GUIDE: do not publish customer work.'
            with patch.object(planner, 'check_provider'), patch.object(planner, 'run_turn',
                    return_value=(0, b'{"summary":"done","actions":[]}')) as run:
                planner.plan('codex', 'private input')
            prompt = run.call_args.args[1]
            self.assertTrue(prompt.endswith(planner.tool_guide))
            self.assertNotIn(TOOL_GUIDE, prompt)

    def test_public_planning_keeps_existing_guide(self):
        with tempfile.TemporaryDirectory() as root:
            planner = Controller(root, None, None, {'controller': {}})
            with patch.object(planner, 'check_provider'), patch.object(planner, 'run_turn',
                    return_value=(0, b'{"summary":"done","actions":[]}')) as run:
                planner.plan('codex', 'public input')
            self.assertTrue(run.call_args.args[1].endswith(TOOL_GUIDE))


if __name__ == '__main__':
    unittest.main()
