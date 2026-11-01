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

    def publisher(self, config=CONFIG, reviews=None):
        return Publisher(self.root, config, client=apify.Client('token-not-used', transport=self.fake), reviews=reviews)

    def task(self, ident='TASK-179349120010', **args):
        base = {'actor': 'title-extractor', 'title': 'Title extractor', 'description': 'Extracts page titles.'}
        base.update(args)
        return {'id': ident, 'action': 'PUBLISH_ACTOR', 'submitted_by': 'BUILDER', 'args': base}

    def approval(self, digest, reviewer='AUDITOR', verdict='APPROVE', at=1):
        return dict(reviewer=reviewer, subject='actor:title-extractor', digest=digest, verdict=verdict, at=at, seq=at)

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

    def test_private_build_then_public_listing_without_rebuilding(self):
        first = self.publisher().publish(self.task())
        self.assertEqual((first['status'], first['public']), ('PRIVATE_BUILD_READY', False))
        self.assertEqual(Publisher.task_status(first), 'DONE')
        self.assertFalse(self.fake.actors['title-extractor']['isPublic'])
        event = dict(name='result', title='Result', description='One result', price_microusd=2000)
        reviews = [self.approval(first['source_digest'])]
        second = self.publisher(reviews=reviews).publish(self.task('TASK-179349120011', public=True, events=[event]))
        self.assertEqual(second['status'], 'PUBLISHED')
        self.assertEqual(second['store_url'], 'https://apify.com/globalland/title-extractor')
        actor = self.fake.actors['title-extractor']
        self.assertTrue(actor['isPublic'])
        self.assertEqual(actor['pricingInfos'][0]['pricingModel'], 'PAY_PER_EVENT')
        self.assertEqual(self.fake.count('POST', '/v2/acts'), 1)
        self.assertEqual(self.fake.count('POST', '/v2/acts/A1/builds'), 1)

    def test_public_listing_needs_an_independent_approval_of_the_exact_source(self):
        digest = self.publisher().publish(self.task())['source_digest']
        cases = {
            'no review': [],
            'self review': [self.approval(digest, reviewer='BUILDER')],
            'other source': [self.approval('0' * 64)],
            'approval later contradicted': [self.approval(digest, at=1), self.approval(digest, reviewer='CRITIC', verdict='NEEDS_WORK', at=2)],
        }
        for label, reviews in cases.items():
            with self.subTest(label), self.assertRaisesRegex(ApifyError, 'review APPROVE'):
                self.publisher(reviews=reviews).publish(self.task('TASK-179349120011', public=True))
        self.assertFalse(self.fake.actors['title-extractor']['isPublic'])
        ok = self.publisher(reviews=cases['approval later contradicted'] + [self.approval(digest, at=3)]).publish(self.task('TASK-179349120012', public=True))
        self.assertEqual(ok['status'], 'PUBLISHED')

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
