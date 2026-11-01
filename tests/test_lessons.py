"""Sprint 2-C: lessons recorded at mission outcomes and injected into prompts."""
import json
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import lessons
import test_autonomous_integration as integration
from controller import Controller
from world import World


class WorldLessonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.world = World(pathlib.Path(self.tmp.name) / 'w.sqlite3')
        self.world.bootstrap()
        self.world.apply('m1', dict(op='create_mission', mission_id='HOSTING', goal='Publish the demo on free hosting'))

    def claim(self, op_id):
        return self.world.apply(op_id, dict(op='claim_mission', mission_id='HOSTING', agent_id='ACQUISITION', lease_seconds=600))['lease_token']

    def test_mission_outcomes_and_explicit_lessons_are_recorded(self):
        token = self.claim('c1')
        self.world.apply('f1', dict(op='fail_mission', mission_id='HOSTING', agent_id='ACQUISITION', lease_token=token,
                                    reason='No credentials', lesson='Probing CLIs for hosting access wastes turns; raise a blocker once.'))
        self.world.apply('l1', dict(op='record_lesson', agent_id='RESEARCHER', lesson='Manager.io forum threads are old; demand is weak.',
                                    tags=['demand', 'invoice']))
        stored = self.world.lessons()
        self.assertEqual([(l['lesson_id'], l['outcome'], l['mission_id']) for l in stored],
                         [('L1', 'FAILED', 'HOSTING'), ('L2', None, None)])
        snap = self.world.snapshot()
        self.assertNotIn('lessons', snap)
        self.assertEqual(snap['lesson_count'], 2)

    def test_invalid_lessons_are_refused_and_storage_is_bounded(self):
        for bad in (dict(tags=['x'] * 9), dict(mission_id='NOPE'), dict(lesson='')):
            args = dict(op='record_lesson', agent_id='RESEARCHER', lesson='ok')
            args.update(bad)
            with self.subTest(bad=list(bad)), self.assertRaises(ValueError):
                self.world.apply('bad-' + next(iter(bad)), args)
        for n in range(World.MAX_LESSONS + 5):
            self.world.apply('n%d' % n, dict(op='record_lesson', agent_id='RESEARCHER', lesson='lesson %d' % n))
        stored = self.world.lessons()
        self.assertEqual(len(stored), World.MAX_LESSONS)
        self.assertEqual(stored[-1]['lesson_id'], 'L%d' % (World.MAX_LESSONS + 5))


class RelevanceTests(unittest.TestCase):
    LESSONS = [
        dict(lesson_id='L1', text='Invoice CSV buyers on Manager.io forum were few; demand is weak.', tags=['demand'], mission_id=None, outcome=None),
        dict(lesson_id='L2', text='Hosting access: no Cloudflare token; raise a blocker once instead of probing.', tags=['hosting'], mission_id=None, outcome='FAILED'),
        dict(lesson_id='L3', text='Apify actors need input schema and README before Store listing.', tags=['apify'], mission_id=None, outcome=None),
        dict(lesson_id='L4', text='Unrelated note about GLC interest policy.', tags=[], mission_id=None, outcome=None),
    ]
    MISSIONS = [dict(mission_id='APIFY-ACTOR', goal='Publish a scraper actor on the Apify Store with pay per event pricing', status='RUNNING'),
                dict(mission_id='OLD', goal='Invoice import research', status='COMPLETED')]

    def test_lessons_matching_open_missions_come_first_with_recent_failures(self):
        chosen = [l['lesson_id'] for l in lessons.relevant(self.LESSONS, self.MISSIONS)]
        self.assertEqual(chosen[0], 'L3')
        self.assertIn('L2', chosen)      # recent failure, always shown
        self.assertNotIn('L4', chosen)
        self.assertNotIn('L1', chosen)   # matches only a completed mission

    def test_works_without_fts5_and_without_lessons(self):
        self.assertEqual(lessons.relevant([], self.MISSIONS), [])
        with patch.object(lessons.sqlite3, 'connect', side_effect=sqlite3.OperationalError('no fts5')):
            chosen = [l['lesson_id'] for l in lessons.relevant(self.LESSONS, self.MISSIONS)]
        self.assertEqual(chosen[0], 'L3')


class PlaybookTests(unittest.TestCase):
    def test_playbooks_are_loaded_without_the_license_file_and_bounded(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        loaded = lessons.playbooks(root)
        self.assertEqual(set(loaded), {'idea-verdict', 'growth-constraint', 'completion-evidence', 'two-key-review'})
        self.assertTrue(all('MIT' in text for text in loaded.values()))
        self.assertLessEqual(len(lessons.playbooks(root, limit_chars=1000)), 1)
        self.assertEqual(lessons.playbooks(root / 'missing'), {})


class LessonPromptIntegration(unittest.TestCase):
    setUp = integration.AutonomousIntegration.setUp
    git = integration.AutonomousIntegration.git

    def run(self, args=None, result=None):
        if isinstance(args, list):
            return subprocess.run(args, check=True, capture_output=True).stdout
        return super().run(args if args is not None else result)

    def test_relevant_lessons_reach_the_brain_prompt(self):
        config = {'controller': {'mode': 'subscriptions', 'providers': ['claude'], 'subscriptions_confirmed': True,
                                 'extra_usage_disabled': True, 'image': 'brain@sha256:' + '1' * 64}}
        (self.install / 'control/config.json').write_text(json.dumps(config))
        playbooks = self.seed / 'agents/playbooks'
        playbooks.mkdir(parents=True)
        source = pathlib.Path(__file__).resolve().parents[1] / 'agents/playbooks'
        for name in ('two-key-review.md', 'idea-verdict.md', 'THIRD_PARTY.md'):
            (playbooks / name).write_text((source / name).read_text())
        self.git('add', '.'); self.git('commit', '-m', 'playbooks'); self.git('push', 'origin', 'main')
        world, _, _ = self.app.services()
        world.apply('m', dict(op='create_mission', mission_id='APIFY-ACTOR', goal='Publish a scraper actor on the Apify Store'))
        world.apply('l', dict(op='record_lesson', agent_id='BUILDER', lesson='Apify actors need an input schema before Store listing.'))
        prompts = []
        decision = {'summary': 'ok', 'actions': []}
        reply = json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False, 'structured_output': decision}).encode()

        def brain(argv, **kwargs):
            prompts.append(kwargs['input'].decode())
            return 0, reply

        with patch.object(Controller, 'check_provider'), patch('controller.run_brain', side_effect=brain):
            self.app.cycle('think')
        self.assertIn('Apify actors need an input schema before Store listing.', prompts[0])
        self.assertIn('producer and auditor are never the same agent', prompts[0])
        self.assertIn('Give one verdict', prompts[0])
        self.assertIn('include a lesson', prompts[0])


if __name__ == '__main__':
    unittest.main()
