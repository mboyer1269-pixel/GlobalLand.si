"""Sprint 2-B: Apify Store publication (PUBLISH_ACTOR, ACTOR_STATS) against a fake API."""
import itertools
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import apify
import test_autonomous_integration as integration
from apify import ApifyError, Publisher, load_source, pricing

README = '# Title extractor\n\nBuilt and maintained by autonomous AI agents of GlobalLand.\n'
ACTOR_JSON = json.dumps({'actorSpecification': 1, 'name': 'title-extractor', 'version': '0.1', 'input': './input_schema.json'})
CONFIG = {'apify': {'enabled': True, 'max_event_price_usd': 0.01, 'allow_public': True, 'build_wait_seconds': 60}}


def write_actor(work, name='title-extractor', readme=README, actor_json=ACTOR_JSON, extra=None):
    base = pathlib.Path(work) / 'products/actors' / name
    (base / 'actor-config').mkdir(parents=True, exist_ok=True)
    (base / 'actor-config/actor.json').write_text(actor_json)
    (base / 'actor-config/input_schema.json').write_text('{"title":"Input","type":"object","schemaVersion":1,"properties":{}}')
    (base / 'Dockerfile').write_text('FROM apify/actor-node:22\nCOPY . ./\nCMD npm start\n')
    (base / 'README.md').write_text(readme)
    (base / 'main.js').write_text("console.log('hello')\n")
    for rel, text in (extra or {}).items():
        (base / rel).write_text(text)
    return base


class FakeApify:
    def __init__(self, build_statuses=('SUCCEEDED',)):
        self.calls, self.actors, self.build_statuses = [], {}, list(build_statuses)
        self.fail_build_post = False
        self.runs = []

    def __call__(self, method, path, body=None):
        self.calls.append((method, path.split('?')[0], body))
        if path == '/v2/users/me':
            return 200, {'data': {'username': 'globalland'}}
        if method == 'GET' and path.startswith('/v2/acts/globalland~'):
            actor = self.actors.get(path.rsplit('~', 1)[1])
            return (200, {'data': actor}) if actor else (404, None)
        if method == 'POST' and path == '/v2/acts':
            actor = dict(body, id='A%d' % (len(self.actors) + 1), pricingInfos=[])
            self.actors[body['name']] = actor
            return 201, {'data': actor}
        if method == 'PUT' and path.startswith('/v2/acts/A'):
            actor = next(a for a in self.actors.values() if a['id'] == path.rsplit('/', 1)[1])
            actor.update(body)
            return 200, {'data': actor}
        if method == 'POST' and path.endswith('/builds?version=0.1&tag=latest&waitForFinish=60'):
            if self.fail_build_post:
                return 500, None
            return 201, {'data': {'id': 'B1', 'status': self.build_statuses.pop(0)}}
        if method == 'GET' and path.startswith('/v2/actor-builds/B1'):
            return 200, {'data': {'id': 'B1', 'status': self.build_statuses.pop(0) if self.build_statuses else 'RUNNING'}}
        if method == 'GET' and path == '/v2/logs/B1':
            return 200, 'npm ERR! missing script: start\n'
        if method == 'GET' and '/runs' in path:
            return 200, {'data': {'items': self.runs}}
        return 404, None

    def count(self, method, path):
        return sum(1 for m, p, _ in self.calls if m == method and p == path)


class ApifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        write_actor(self.root / 'work')
        self.fake = FakeApify()

    PUBLISHER = ('THINK-2', 'claude')

    def publisher(self, config=CONFIG, reviews=None, origin=PUBLISHER):
        return Publisher(self.root, config, client=apify.Client('token-not-used', transport=self.fake), reviews=reviews, origin=origin)

    def task(self, ident='TASK-179349120010', **args):
        base = {'actor': 'title-extractor', 'title': 'Title extractor', 'description': 'Extracts page titles.'}
        base.update(args)
        return {'id': ident, 'action': 'PUBLISH_ACTOR', 'submitted_by': 'BUILDER', 'args': base}

    def approval(self, digest, reviewer='AUDITOR', verdict='APPROVE', at=1, turn='THINK-1', provider='codex'):
        # host_turn/host_provider are set by the host (Toolbox), never by the brain.
        return dict(reviewer=reviewer, subject='actor:title-extractor', digest=digest, verdict=verdict, at=at, seq=at,
                    host_turn=turn, host_provider=provider)

    def test_source_is_validated_and_actor_config_becomes_dot_actor(self):
        files, version, digest = load_source(self.root / 'work', 'title-extractor')
        names = {f['name'] for f in files}
        self.assertIn('.actor/actor.json', names)
        self.assertNotIn('actor-config/actor.json', names)
        self.assertEqual(version, '0.1')
        work = self.root / 'other'
        cases = {
            'disclosure': dict(readme='# Tool\n'),
            'name': dict(actor_json=json.dumps({'actorSpecification': 1, 'name': 'other', 'version': '0.1'})),
            'secret': dict(extra={'config.js': 'const k = "ghp_' + 'x' * 30 + '"'}),
        }
        for label, kwargs in cases.items():
            with self.subTest(label):
                write_actor(work / label, **kwargs)
                with self.assertRaises(ValueError):
                    load_source(work / label, 'title-extractor')
        with self.assertRaisesRegex(ApifyError, 'Invalid actor name'):
            load_source(self.root / 'work', '../etc')

    def test_pricing_is_capped_in_micro_usd(self):
        event = dict(name='result', title='Result', description='One result', price_microusd=2000)
        record = pricing([event], 10_000)[0]['pricingPerEvent']['actorChargeEvents']['result']
        self.assertEqual((record['eventPriceUsd'], record['isPrimaryEvent']), (0.002, True))
        for bad in ([dict(event, price_microusd=10_001)], [event, event], [dict(event, name='Bad Name')], [event] * 6):
            with self.subTest(bad=len(bad)), self.assertRaises(ApifyError):
                pricing(bad, 10_000)
        self.assertEqual(pricing(None, 10_000), [])
        with self.assertRaisesRegex(ApifyError, 'floor'):
            pricing([dict(event, price_microusd=100)], 10_000, min_price_micro=500)
        self.assertEqual(apify.settings({'apify': {'enabled': True}})['min_price_micro'], 500)
        with self.assertRaises(ValueError):
            apify.settings({'apify': {'enabled': True, 'min_event_price_usd': 0.1, 'max_event_price_usd': 0.05}})

    def test_private_build_then_public_listing_without_rebuilding(self):
        first = self.publisher().publish(self.task())
        self.assertEqual((first['status'], first['public']), ('PRIVATE_BUILD_READY', False))
        self.assertEqual(Publisher.task_status(first), 'DONE')
        self.assertFalse(self.fake.actors['title-extractor']['isPublic'])
        event = dict(name='result', title='Result', description='One result', price_microusd=2000)
        listing = apify.review_digest(first['source_digest'], self.task(events=[event])['args'])
        reviews = [self.approval(listing)]
        second = self.publisher(reviews=reviews).publish(self.task('TASK-179349120011', public=True, events=[event]))
        self.assertEqual(second['status'], 'PUBLISHED')
        self.assertEqual(second['store_url'], 'https://apify.com/globalland/title-extractor')
        actor = self.fake.actors['title-extractor']
        self.assertTrue(actor['isPublic'])
        self.assertEqual(actor['pricingInfos'][0]['pricingModel'], 'PAY_PER_EVENT')
        self.assertEqual(self.fake.count('POST', '/v2/acts'), 1)
        self.assertEqual(self.fake.count('POST', '/v2/acts/A1/builds'), 1)

    def test_public_listing_needs_an_independent_approval_of_the_exact_source(self):
        private = self.publisher().publish(self.task())
        digest = private['review_digest']
        self.assertEqual(digest, apify.review_digest(private['source_digest'], self.task()['args']))
        cases = {
            'no review': [],
            'self review': [self.approval(digest, reviewer='BUILDER')],
            'other source': [self.approval('0' * 64)],
            'approval later contradicted': [self.approval(digest, at=1), self.approval(digest, reviewer='CRITIC', verdict='NEEDS_WORK', at=2)],
            # Security review finding: one brain can type any agent name, so names alone prove nothing.
            'same provider, other agent name': [self.approval(digest, turn='THINK-1', provider='claude')],
            'same turn': [self.approval(digest, turn='THINK-2', provider='codex')],
            'no host provenance': [dict(self.approval(digest), host_turn=None, host_provider=None)],
        }
        for label, reviews in cases.items():
            with self.subTest(label), self.assertRaisesRegex(ApifyError, 'review APPROVE'):
                self.publisher(reviews=reviews).publish(self.task('TASK-179349120011', public=True))
        self.assertFalse(self.fake.actors['title-extractor']['isPublic'])
        # Changing the listing after approval needs a new approval.
        with self.assertRaisesRegex(ApifyError, 'review APPROVE'):
            self.publisher(reviews=[self.approval(digest)]).publish(self.task('TASK-179349120013', public=True, title='Different title'))
        for label, review in (('external (Grok via GitHub)', self.approval(digest, at=3, turn='EXTERNAL-TASK-0200', provider='EXTERNAL')),
                              ('founder', dict(self.approval(digest, at=4, reviewer='FOUNDER', turn='FOUNDER-1', provider='FOUNDER')))):
            with self.subTest(label):
                ok = self.publisher(reviews=cases['approval later contradicted'] + [review]).publish(self.task('TASK-17934912001%d' % review['at'], public=True))
                self.assertEqual(ok['status'], 'PUBLISHED')

    def test_refusal_never_hands_the_digest_to_the_brain(self):
        private = self.publisher().publish(self.task())
        with self.assertRaises(ApifyError) as refused:
            self.publisher().publish(self.task('TASK-179349120011', public=True))
        self.assertNotIn(private['review_digest'], str(refused.exception))
        self.assertNotIn(private['source_digest'], str(refused.exception))

    def test_public_listing_needs_the_founders_permission(self):
        config = {'apify': dict(CONFIG['apify'], allow_public=False)}
        with self.assertRaisesRegex(ApifyError, 'not allowed'):
            self.publisher(config).publish(self.task(public=True))
        self.assertEqual(self.fake.calls, [])

    def test_failed_build_returns_the_log_and_is_not_rebuilt(self):
        self.fake.build_statuses = ['FAILED']
        result = self.publisher().publish(self.task())
        self.assertEqual((result['status'], Publisher.task_status(result)), ('BUILD_FAILED', 'FAILED'))
        self.assertIn('missing script', result['log_tail'])
        again = self.publisher().publish(self.task('TASK-179349120011'))
        self.assertIn('already failed to build', again['note'])
        self.assertEqual(self.fake.count('POST', '/v2/acts/A1/builds'), 1)
        self.assertFalse(self.fake.actors['title-extractor']['isPublic'])

    def test_pending_build_is_resumed_not_restarted(self):
        self.fake.build_statuses = ['RUNNING']
        with patch('apify.time.monotonic', side_effect=itertools.count(0, 100)):
            pending = self.publisher().publish(self.task())
        self.assertEqual((pending['status'], Publisher.task_status(pending)), ('PENDING', 'TIMEOUT'))
        self.fake.build_statuses = ['SUCCEEDED']
        done = self.publisher().publish(self.task('TASK-179349120011'))
        self.assertEqual(done['status'], 'PRIVATE_BUILD_READY')
        self.assertEqual(self.fake.count('POST', '/v2/acts/A1/builds'), 1)

    def test_crash_after_creation_never_creates_a_second_actor(self):
        self.fake.fail_build_post = True
        with self.assertRaisesRegex(ApifyError, 'HTTP 500'):
            self.publisher().publish(self.task())
        self.fake.fail_build_post = False
        self.assertEqual(self.publisher().publish(self.task('TASK-179349120011'))['status'], 'PRIVATE_BUILD_READY')
        self.assertEqual(self.fake.count('POST', '/v2/acts'), 1)

    def test_token_and_enablement_are_host_controlled(self):
        with self.assertRaisesRegex(ApifyError, 'not enabled'):
            Publisher(self.root, {}).publish(self.task())
        with self.assertRaisesRegex(ApifyError, 'No Apify integration configured'):
            Publisher(self.root, CONFIG).publish(self.task())
        token = self.root / 'credentials/apify/token'
        token.parent.mkdir(parents=True)
        token.write_text('apify_api_example\n')
        os.chmod(token, 0o644)
        with self.assertRaisesRegex(ApifyError, 'owner only'):
            Publisher(self.root, CONFIG).publish(self.task())
        os.chmod(token, 0o600)
        self.assertEqual(apify.read_token(self.root), 'apify_api_example')

    def test_stats_estimate_charges_and_say_they_are_not_revenue(self):
        event = dict(name='result', title='Result', description='One result', price_microusd=2000)
        no_review = {'apify': dict(CONFIG['apify'], require_review=False)}
        self.publisher(no_review).publish(self.task(public=True, events=[event]))
        self.fake.runs = [{'status': 'SUCCEEDED', 'chargedEventCounts': {'result': 150}},
                          {'status': 'FAILED', 'chargedEventCounts': {'result': 10}}]
        stats = self.publisher().stats({'args': {'actor': 'title-extractor'}})
        self.assertEqual((stats['recent_runs'], stats['recent_succeeded']), (2, 1))
        self.assertEqual(stats['charged_events'], {'result': 160})
        self.assertAlmostEqual(stats['gross_charges_estimate_usd'], 0.32)
        self.assertIn('not', stats['note'].lower())


class HostProvenanceTests(unittest.TestCase):
    """Reviewer identity comes from the host, never from the brain's arguments."""

    def setUp(self):
        from treasury import Treasury
        from world import World
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / 'state/controller').mkdir(parents=True)
        self.world = World(self.root / 'w.sqlite3'); self.world.bootstrap()
        self.bank = Treasury(self.root / 't.sqlite3')

    def review_task(self, ident, **extra):
        args = dict(op='review', reviewer='AUDITOR', subject='actor:x', digest='a' * 64, verdict='APPROVE')
        args.update(extra)
        return {'id': ident, 'type': 'TOOL', 'submitted_by': 'BUILDER', 'created_at': '2026-11-01T00:00:00Z',
                'action': 'WORLD', 'args': args, 'estimated_cost_cad': 0, 'approved_by': None}

    def test_review_provenance_is_set_by_the_host(self):
        from tools import Toolbox
        (self.root / 'state/controller/THINK-1793491202.json').write_text(json.dumps({'provider': 'codex'}))
        box = Toolbox(self.root, self.world, self.bank, {})
        box.run(self.review_task('TASK-179349120201'))
        box.run(self.review_task('TASK-0300'))
        first, second = self.world.reviews()
        self.assertEqual((first['host_turn'], first['host_provider']), ('THINK-1793491202', 'codex'))
        self.assertEqual((second['host_turn'], second['host_provider']), ('EXTERNAL-TASK-0300', 'EXTERNAL'))
        with self.assertRaisesRegex(ValueError, 'host fields are reserved'):
            box.run(self.review_task('TASK-0301', host_provider='FOUNDER', host_turn='FOUNDER-1'))
        broker_origin = ('THINK-1793491300', 'claude')
        box.run(self.review_task('TASK-179349130010'), origin=broker_origin)
        self.assertEqual(self.world.reviews()[-1]['host_provider'], 'claude')

    def test_founder_review_cli(self):
        import review_admin
        review = review_admin.approve(self.world, 'title-extractor', 'b' * 64, notes='checked the README')
        self.assertEqual((review['reviewer'], review['host_provider']), ('FOUNDER', 'FOUNDER'))
        with self.assertRaisesRegex(ValueError, 'administrator'):
            review_admin.main(['approve', '--actor', 'x', '--digest', 'b' * 64], root=str(self.root), euid=lambda: 1000)
        with self.assertRaises(ValueError):
            self.world.apply('fake', dict(op='review', reviewer='AUDITOR', subject='actor:x', digest='b' * 64,
                                          verdict='APPROVE', host_turn='FOUNDER-1', host_provider='FOUNDER'))


class PublishActorQueueIntegration(unittest.TestCase):
    setUp = integration.AutonomousIntegration.setUp
    git = integration.AutonomousIntegration.git
    submit = integration.AutonomousIntegration.submit

    def run(self, args=None, result=None):
        if isinstance(args, list):
            return subprocess.run(args, check=True, capture_output=True).stdout
        return super().run(args if args is not None else result)

    def test_without_founder_setup_the_refusal_says_what_is_missing(self):
        self.submit(120, 'PUBLISH_ACTOR', {'actor': 'title-extractor', 'title': 'Titles', 'description': 'Extracts titles.'})
        self.app.cycle('queue')
        result = json.loads(self.run(['git', '--git-dir=' + str(self.remote), 'show', 'main:queue/failed/TASK-0120.result.json']))
        self.assertEqual(result['status'], 'REJECTED')
        self.assertIn('Apify integration not enabled by the founder', result['output'])


if __name__ == '__main__':
    unittest.main()
