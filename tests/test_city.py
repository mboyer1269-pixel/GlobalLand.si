"""Read-only city contracts against real disposable Git histories."""
import hashlib
import http.client
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

CITY_DIR = pathlib.Path(__file__).resolve().parents[1] / 'prototypes/ville-globalland'
sys.path.insert(0, str(CITY_DIR))
spec = importlib.util.spec_from_file_location('ville_locale', CITY_DIR / 'ville_locale.py')
city = importlib.util.module_from_spec(spec)
spec.loader.exec_module(city)


class CityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = pathlib.Path(self.temp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'city-test@example.invalid')
        self.git('config', 'user.name', 'City test')
        self.git('config', 'commit.gpgsign', 'false')
        self.git('config', 'core.autocrlf', 'false')
        self.addCleanup(patch.stopall)
        patch.object(city, 'REPO', self.repo).start()
        self.agents = [dict(agent_id='BUILDER', role='Construction', status='ACTIVE'),
                       dict(agent_id='_NEW-2', role='<script>unsafe</script>', status='ACTIVE')]
        self.missions = [dict(mission_id='OLD', goal='Old mission', agent_id='BUILDER', status='COMPLETED'),
                         dict(mission_id='NEW', goal='Current work', agent_id='_NEW-2', status='RUNNING',
                              lease_token='PRIVATE_SENTINEL')]
        self.world()
        self.commit('initial world')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.PIPE).decode().strip()

    def put(self, path, value):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = value.encode() if isinstance(value, str) else (json.dumps(value, ensure_ascii=False) + '\n').encode()
        target.write_bytes(raw)
        return raw

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '-qm', message)
        return self.git('rev-parse', 'HEAD')

    def world(self):
        collections = {}
        for key, items in (('agents', self.agents), ('missions', self.missions), ('blockers', [])):
            pages = max(1, len(items))
            collections[key] = dict(total=len(items), pages=pages, path=f'world/pages/{key}-{{page}}.json')
            for i in range(pages):
                self.put(f'world/pages/{key}-{i}.json', dict(collection=key, page=i, pages=pages,
                         total=len(items), next_page=i+1 if i+1 < pages else None,
                         snapshot_sha256='f'*64, items=items[i:i+1]))
        self.put('world/status.json', dict(agents=self.agents[:1], missions=self.missions[:1], blockers=[],
                 projection=dict(snapshot_sha256='f'*64, collections=collections)))
        self.put('world/controller.json', dict(state='OPERATIONAL'))

    def task(self, ident='TASK-170000000001'):
        return dict(id=ident, type='TOOL', submitted_by='BUILDER', action='EXEC',
                    created_at='2026-11-05T10:00:00Z', description='Build useful example',
                    args=dict(mission_id='NEW', argv=['python', '-c', 'PRIVATE_SENTINEL'],
                              outputs=['products/example.txt']))

    def result(self, task=None, status='DONE', broker=True, good_hash=True):
        task = task or self.task()
        if broker:
            raw = (json.dumps(task, ensure_ascii=False, sort_keys=True)+'\n').encode()
        else:
            raw = self.put(f"queue/inbox/{task['id']}.json", task)
            self.commit('plan task')
            (self.repo / f"queue/inbox/{task['id']}.json").unlink()
        result = dict(id=task['id'], status=status, output='PRIVATE_SENTINEL',
                      input_sha256=hashlib.sha256(raw).hexdigest() if good_hash else '0'*64,
                      artifacts=['products/example.txt'])
        if broker:
            result['request'] = task
        folder = 'done' if status == 'DONE' else 'failed'
        self.put(f"queue/{folder}/{task['id']}.result.json", result)
        self.put('products/example.txt', 'first version\n')
        return self.commit('result publication')

    def snapshot(self):
        return city.snapshot(self.git('rev-parse', 'HEAD'))

    def test_pages_include_new_missions_agents_without_leaking_private_fields(self):
        result = self.snapshot()
        self.assertEqual(set(result['missions']), {'OLD', 'NEW'})
        self.assertIn('_NEW-2', result['agents'])
        self.assertEqual(result['missions']['NEW']['goal'], 'Current work')
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(result))
        self.assertIsNone(result['journey'])

    def test_empty_world_has_no_invented_journey_or_agents(self):
        self.agents = []; self.missions = []; self.world(); self.commit('empty world')
        result = self.snapshot()
        self.assertEqual(result['agents'], {})
        self.assertEqual(result['events'], [])
        self.assertEqual(result['missions'], {})
        self.assertIsNone(result['journey'])

    def test_broker_task_is_attributed_and_links_its_original_artifact_version(self):
        published = self.result()
        self.put('products/example.txt', 'replacement\n'); self.commit('later replacement')
        result = self.snapshot()
        event = result['events'][0]
        self.assertEqual(event['agent'], 'BUILDER')
        self.assertEqual(event['mission'], 'NEW')
        self.assertEqual(event['kind'], 'done')
        artifact = result['artifacts'][event['artifact']]
        self.assertIn('/blob/'+published+'/products/example.txt', artifact['sourceUrl'])
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(result))
        self.assertEqual(result['journey']['mission'], 'NEW')

    def test_queued_request_is_recovered_from_parent_and_hash_verified(self):
        self.result(broker=False)
        event = self.snapshot()['events'][0]
        self.assertEqual(event['agent'], 'BUILDER')
        self.assertIn('/queue/inbox/TASK-170000000001.json', event['decisionUrl'])

    def test_mismatched_hash_keeps_result_but_never_invents_attribution(self):
        self.result(good_hash=False)
        result = self.snapshot(); event = result['events'][0]
        self.assertEqual(event['kind'], 'done')
        self.assertIsNone(event['agent'])
        self.assertIsNone(event['mission'])
        self.assertNotIn('decisionUrl', event)
        self.assertIsNone(result['journey'])

    def test_result_without_request_is_visible_as_unattributed(self):
        self.put('queue/done/TASK-170000000003.result.json',
                 dict(id='TASK-170000000003', status='DONE', input_sha256='a'*64, output='hello'))
        self.commit('legacy result')
        event = self.snapshot()['events'][0]
        self.assertEqual(event['id'], 'TASK-170000000003')
        self.assertIsNone(event['agent'])

    def test_rejected_task_is_not_labelled_execution_failure_or_success(self):
        self.result(status='REJECTED')
        self.assertEqual(self.snapshot()['events'][0]['kind'], 'rejected')

    def test_pending_task_is_announced_and_attached_to_its_agent(self):
        self.put('queue/inbox/TASK-170000000001.json', self.task()); self.commit('pending')
        result = self.snapshot()
        self.assertEqual(result['events'][0]['kind'], 'planned')
        self.assertEqual(result['agents']['BUILDER']['next'], 'TASK-170000000001')

    def test_page_from_another_snapshot_is_rejected(self):
        path = self.repo / 'world/pages/missions-1.json'
        page = json.loads(path.read_bytes()); page['snapshot_sha256'] = 'b'*64
        self.put('world/pages/missions-1.json', page); self.commit('inconsistent page')
        with self.assertRaisesRegex((RuntimeError, ValueError), 'page|Page|coh'):
            self.snapshot()

    def test_cached_reader_distinguishes_local_copy_from_failed_refresh(self):
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        reader = city.SnapshotReader(False)
        result = reader.read()
        self.assertEqual(result['sourceMode'], 'cached')
        self.assertFalse(result['stale'])

    def test_invalid_new_snapshot_keeps_last_valid_view_and_reports_stale(self):
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        reader = city.SnapshotReader(False)
        with patch.object(city.time, 'monotonic', return_value=0):
            original = reader.read()
        self.put('world/status.json', '{invalid'); self.commit('bad update')
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        with patch.object(city.time, 'monotonic', return_value=60):
            later = reader.read()
        self.assertEqual(later['revision'], original['revision'])
        self.assertEqual(later['missions'], original['missions'])
        self.assertTrue(later['stale'])

    def serve(self):
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        server = city.ThreadingHTTPServer(('127.0.0.1', 0), city.handler_for(city.SnapshotReader(False)))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server.server_port

    def request(self, port, path, host=None):
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
        self.addCleanup(connection.close)
        connection.request('GET', path, headers={'Host': host or f'127.0.0.1:{port}'})
        response = connection.getresponse()
        return response.status, response.read(), dict(response.getheaders())

    def test_http_serves_only_allowlisted_projection_and_static_files(self):
        port = self.serve()
        status, raw, headers = self.request(port, '/snapshot.json')
        self.assertEqual(status, 200)
        self.assertNotIn(b'PRIVATE_SENTINEL', raw)
        self.assertIn('NEW', json.loads(raw)['missions'])
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(self.request(port, '/world/status.json')[0], 404)
        self.assertEqual(self.request(port, '/snapshot.json', 'attacker.invalid')[0], 403)

    def test_http_invalid_initial_source_returns_503_without_demo_activity(self):
        self.put('world/status.json', '{invalid'); self.commit('broken source')
        port = self.serve()
        self.assertEqual(self.request(port, '/snapshot.json')[0], 503)

    def test_malformed_request_does_not_hide_other_valid_results(self):
        self.result()
        broken = self.task('TASK-170000000002'); broken['action'] = ['not-an-action']
        self.result(task=broken)
        result = self.snapshot()
        self.assertEqual(len(result['events']), 2)
        self.assertIsNone(next(e for e in result['events'] if e['id'] == broken['id'])['agent'])

    def test_missing_page_version_is_not_accepted_as_coherent(self):
        world = json.loads((self.repo / 'world/status.json').read_bytes())
        del world['projection']['snapshot_sha256']
        self.put('world/status.json', world)
        for path in (self.repo / 'world/pages').glob('*.json'):
            value = json.loads(path.read_bytes()); del value['snapshot_sha256']
            self.put(path.relative_to(self.repo), value)
        self.commit('unversioned pages')
        with self.assertRaisesRegex(ValueError, 'version|Version'):
            self.snapshot()

    def test_invalid_result_status_does_not_hide_valid_results(self):
        self.result()
        self.put('queue/failed/TASK-170000000002.result.json',
                 dict(id='TASK-170000000002', status=['FAILED']))
        self.commit('malformed result')
        result = self.snapshot()
        self.assertEqual([e['id'] for e in result['events']], ['TASK-170000000001'])
        self.assertEqual(len(result['coverage']['warnings']), 1)

    def test_artifact_directory_is_not_presented_as_a_delivered_file(self):
        self.result()
        path = 'queue/done/TASK-170000000001.result.json'
        result = json.loads((self.repo / path).read_bytes())
        result['artifacts'] = ['products/folder', 'products/example.txt']
        self.put(path, result)
        self.put('products/folder/nested.txt', 'nested')
        self.commit('result names directory and file')
        snapshot = self.snapshot()
        self.assertEqual([a['title'] for a in snapshot['artifacts'].values()], ['example.txt'])
        self.assertEqual(len(snapshot['coverage']['warnings']), 1)


if __name__ == '__main__':
    unittest.main()
