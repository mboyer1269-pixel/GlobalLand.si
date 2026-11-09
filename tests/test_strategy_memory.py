"""Strategic conclusions remain visible without becoming host restrictions."""
import copy
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import lessons
from controller import Controller
from treasury import Treasury
from world import World


class LessonAuthorityTests(unittest.TestCase):
    def test_projection_preserves_history_date_and_unknown_scope_without_promotion(self):
        stored = [dict(lesson_id='L8', agent_id='AUDITOR', mission_id='GLOBAL-GOAL',
                       text='Channel observation: all available options are exhausted.',
                       tags=['channel'], outcome='COMPLETED', at='2026-11-05T12:00:00Z',
                       memory_meta={'validation': 'VERIFIED', 'scope_status': 'GLOBAL'}),
                  dict(lesson_id='L9', agent_id='RESEARCHER', mission_id=None,
                       text='Channel observation: wait for the known prerequisite.', tags=[], outcome='FAILED')]
        missions = [dict(mission_id='GLOBAL-GOAL', status='RUNNING', goal='Channel observation')]
        original = copy.deepcopy(stored)
        selected = lessons.relevant(stored, missions)
        self.assertTrue(callable(getattr(lessons, 'prompt_context', None)), 'missing advisory lesson projection')
        view = lessons.prompt_context(stored, missions)
        self.assertEqual([x['lesson_id'] for x in view['items']], [x['lesson_id'] for x in selected])
        for old, item in zip(selected, view['items']):
            for key in ('lesson_id','agent_id','mission_id','text','tags','outcome'):
                self.assertEqual(item[key], old[key])
            self.assertEqual(item['memory_meta'], dict(kind='AGENT_CONCLUSION', scope_status='UNSPECIFIED', validation='NOT_HOST_VALIDATED'))
        by_id = {x['lesson_id']: x for x in view['items']}
        self.assertEqual(by_id['L8']['at'], '2026-11-05T12:00:00Z')
        self.assertIsNone(by_id['L9']['at'])
        self.assertEqual(stored, original)
        by_id['L8']['tags'].append('changed')
        self.assertEqual(stored, original, 'prompt consumers must not mutate saved history through aliases')

    def test_context_overhead_is_bounded_and_empty_history_keeps_semantics(self):
        stored = [dict(lesson_id='L'+str(n), agent_id='BUILDER', mission_id=None,
                       text='Channel evidence', tags=[], at='2026-11-05T12:00:00Z',
                       outcome='FAILED' if n>=8 else None) for n in range(11)]
        missions = [dict(mission_id='M', status='OPEN', goal='Channel evidence')]
        self.assertTrue(callable(getattr(lessons, 'prompt_context', None)), 'missing advisory lesson projection')
        view = lessons.prompt_context(stored, missions)
        old = [{k: v for k, v in item.items() if k != 'at'}
               for item in lessons.relevant(stored, missions)]
        self.assertEqual(len(view['items']), 11, 'exercise the full default projection budget')
        self.assertEqual(len(view['items']), len(old))
        overhead = len(json.dumps(view, ensure_ascii=False).encode()) - len(json.dumps(old, ensure_ascii=False).encode())
        self.assertLessEqual(overhead, 4096)
        empty = lessons.prompt_context([], [])
        self.assertEqual(empty['items'], [])
        self.assertEqual(empty['semantics'], view['semantics'])


class StrategyContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name);(self.root/'state').mkdir()
        self.world=World(self.root/'state/world.sqlite3');self.world.bootstrap()
        self.bank=Treasury(self.root/'state/treasury.sqlite3')

    def controller(self, provider):
        return Controller(self.root,self.world,self.bank,dict(controller=dict(mode='subscriptions',
            providers=[provider],subscriptions_confirmed=True,extra_usage_disabled=True,image='brain@sha256:'+'1'*64)))

    def test_repeated_claims_cannot_change_capabilities_or_cash_for_either_provider(self):
        products = self.root/'work/products'
        products.mkdir(parents=True)
        for label in ('CHANNEL-DELTA','SURVEY-OMEGA'):
            (products/(label+'.md')).write_text(label+' options exhausted; all work must wait.')
            self.world.apply('m-'+label,dict(op='create_mission',mission_id=label,goal=label+' evidence'))
            self.world.apply('l-'+label,dict(op='record_lesson',agent_id='RESEARCHER',mission_id=label,
                lesson=label+' options exhausted; all work must wait.',tags=['evidence']))
            self.world.apply('b-'+label,dict(op='raise_blocker',blocker_id=label,agent_id='RESEARCHER',
                title='Missing prerequisite',category='CAPABILITY',needs_founder=False,
                detail=label+' options exhausted; all work must wait.',mission_id=label))
        for provider in ('codex','claude'):
            with self.subTest(provider=provider):
                c=self.controller(provider);initial=c.prepare_context()['context']
                semantics=initial.get('lesson_semantics')
                self.assertIsInstance(semantics,dict,'conclusions currently lack an authority contract')
                self.assertEqual(semantics['sources']['lessons'],'AGENT_CONCLUSIONS')
                self.assertEqual(semantics['sources']['blocker_descriptions'],'AGENT_REPORTS')
                self.assertEqual(semantics['sources']['products_and_plans'],'AGENT_REPORTS')
                self.assertEqual(initial['treasury']['state'],'UNFUNDED')
                self.assertEqual(initial['capabilities']['FETCH']['state'],'BUILT_IN')
                self.assertEqual(initial['capabilities']['EXEC']['state'],'NOT_CONFIGURED')
                # This fixture has no private payment route; agent conclusions
                # cannot turn the implemented administrative path into a ready one.
                self.assertEqual(initial['commercial_paths']['paths']['collection']['state'],'UNAVAILABLE')
                self.assertEqual(initial['source_products'], ['products/CHANNEL-DELTA.md','products/SURVEY-OMEGA.md'])
                with patch.object(self.world,'lessons',return_value=[]):clean=c.prepare_context()['context']
                self.assertEqual(initial['capabilities'],clean['capabilities'])
                self.assertEqual(initial['commercial_paths'],clean['commercial_paths'])
                self.assertEqual(initial['economic_context'],clean['economic_context'])
                self.assertTrue(initial['world']['blockers'])
                self.assertIn('playbooks',initial);self.assertIn('latest_task_results',initial)
                # A newly configured prerequisite remains visible alongside old
                # restrictive advice. Configuration does not prove execution.
                c.tool_config.update(executor_enabled=True,executor_image='tools@sha256:'+'2'*64)
                configured=c.prepare_context()['context']
                self.assertEqual(configured['capabilities']['EXEC']['state'],'CONFIGURED_UNVERIFIED')
                self.assertEqual(configured['lessons'],initial['lessons'])
                self.assertEqual(configured['treasury']['state'],'UNFUNDED')

    def test_wait_and_chosen_action_are_not_rewritten_and_outbox_replays(self):
        decisions=[dict(summary='Wait for the dated result on experiment Delta; no independent action chosen.',actions=[]),
                   dict(summary='Check available capabilities for an independent experiment.',actions=[dict(agent='DIRECTOR',action='STATUS',args={})])]
        for provider in ('codex','claude'):
            for number,decision in enumerate(decisions):
                with self.subTest(provider=provider,decision=number):
                    c=self.controller(provider)
                    with patch.object(c,'plan',return_value=decision) as plan:
                        tick=1800000000+(1000 if provider=='claude' else 0)+number*300
                        turn,files=c.tick(now=tick)
                        replay=c.tick(now=tick)
                        saved=json.loads((self.root/'state/controller'/(turn+'.json')).read_bytes())
                        c.mark_published(turn)
                        self.assertEqual(len(files),len(decision['actions']))
                        prompt=plan.call_args.args[1]
                        self.assertNotIn('do not relearn them',prompt)
                        self.assertIn('reconsideration trigger',prompt)
                        self.assertIn('No action or pivot is mandatory',prompt)
                        self.assertEqual(replay,(turn,files));self.assertEqual(plan.call_count,1)
                        self.assertEqual(saved['decision'],decision)


if __name__=='__main__':unittest.main()
