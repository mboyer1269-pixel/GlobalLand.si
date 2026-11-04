"""Image retention contracts; Docker is an isolated stateful process-boundary fake."""
import copy
import contextlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import image_guard
BRAIN = 'sha256:' + '1' * 64
EXECUTOR = 'node:22@sha256:' + '2' * 64
EXECUTOR_ID = 'sha256:' + '3' * 64


class Docker:
    def __init__(self):
        self.images = {BRAIN: {'Id': BRAIN, 'Config': {'Volumes': None}},
                       EXECUTOR: {'Id': EXECUTOR_ID, 'Config': {'Volumes': None}}}
        self.containers = {}
        self.calls = []
        self.create_error = False

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        out, code = '', 0
        if args[:3] == ['docker', 'image', 'inspect']:
            if args[3] not in self.images:
                code = 1
            else:
                out = json.dumps([self.images[args[3]]])
        elif args[:3] == ['docker', 'container', 'ls']:
            name = args[args.index('--filter') + 1][7:-1]
            out = 'container-id' if name in self.containers else ''
        elif args[:3] == ['docker', 'container', 'inspect']:
            out = json.dumps([self.containers[args[3]]])
        elif args[:3] == ['docker', 'container', 'create']:
            if self.create_error:
                code = 1
            else:
                name = args[args.index('--name') + 1]
                labels = dict(args[i+1].split('=', 1) for i, a in enumerate(args) if a == '--label')
                self.containers[name] = {
                    'Name': '/' + name, 'Image': args[-2],
                    'State': {'Running': False, 'Status': 'created'},
                    'Config': {'Labels': labels, 'Entrypoint': ['/bin/false'], 'User': '65534:65534'},
                    'HostConfig': {'NetworkMode': 'none', 'Binds': None, 'ReadonlyRootfs': True,
                                   'RestartPolicy': {'Name': 'no'}, 'AutoRemove': False}, 'Mounts': []}
                out = 'container-id'
        else:
            raise AssertionError('Unexpected Docker operation: ' + repr(args))
        return subprocess.CompletedProcess(args, code, out, 'Docker operation failed' if code else '')


class ImageGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / 'control').mkdir()
        self.config = {'controller': {'image': BRAIN}, 'executor_image': EXECUTOR}
        self.write_config()
        self.docker = Docker()

    def write_config(self):
        (self.root / 'control/config.json').write_text(json.dumps(self.config))

    def check(self, ensure=False):
        return image_guard.guard(self.root, ensure=ensure, run=self.docker)

    def test_ensure_retains_exact_local_ids_without_start_mount_credentials_or_pull(self):
        result = self.check(ensure=True)
        self.assertTrue(result['ok'], result)
        self.assertEqual({c['Image'] for c in self.docker.containers.values()}, {BRAIN, EXECUTOR_ID})
        creates = [a for a in self.docker.calls if a[:3] == ['docker', 'container', 'create']]
        self.assertEqual(len(creates), 2)
        for args in creates:
            self.assertEqual(args[args.index('--network') + 1], 'none')
            self.assertEqual(args[args.index('--pull') + 1], 'never')
            self.assertEqual(args[args.index('--entrypoint') + 1], '/bin/false')
            self.assertTrue({'--mount', '--volume', '-v', '--env', '-e', '--rm'}.isdisjoint(args))

    def test_second_ensure_is_idempotent_and_status_is_read_only(self):
        self.check(ensure=True)
        before = copy.deepcopy(self.docker.containers)
        self.docker.calls.clear()
        self.assertTrue(self.check(ensure=True)['ok'])
        self.assertTrue(self.check()['ok'])
        self.assertEqual(before, self.docker.containers)
        self.assertFalse(any(a[:3] == ['docker', 'container', 'create'] for a in self.docker.calls))

    def test_status_reports_unprotected_images_without_creating_anchors(self):
        result = self.check()
        self.assertFalse(result['ok'])
        self.assertEqual([r['status'] for r in result['images']], ['unprotected', 'unprotected'])
        self.assertFalse(self.docker.containers)

    def test_missing_second_image_prevents_any_creation(self):
        del self.docker.images[EXECUTOR]
        result = self.check(ensure=True)
        self.assertFalse(result['ok'])
        self.assertEqual(result['images'][1]['status'], 'image_unavailable')
        self.assertFalse(self.docker.containers)

    def test_foreign_ownership_wrong_image_running_or_unsafe_anchor_is_never_changed(self):
        self.check(ensure=True)
        original = copy.deepcopy(self.docker.containers)
        name = next(iter(original))
        mutations = [lambda c: c['Config'].update(Labels={}),
                     lambda c: c.update(Image=EXECUTOR_ID),
                     lambda c: c['State'].update(Running=True, Status='running'),
                     lambda c: c['State'].update(Status='exited'),
                     lambda c: c.update(Mounts=[{'Source': '/private'}]),
                     lambda c: c['HostConfig'].update(NetworkMode='host')]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.docker.containers = copy.deepcopy(original)
                mutate(self.docker.containers[name])
                before = copy.deepcopy(self.docker.containers)
                result = self.check(ensure=True)
                self.assertFalse(result['ok'])
                self.assertEqual(result['images'][0]['status'], 'conflict')
                self.assertEqual(before, self.docker.containers)

    def test_config_upgrade_creates_new_anchor_and_preserves_old_and_unrelated_containers(self):
        self.check(ensure=True)
        before = copy.deepcopy(self.docker.containers)
        self.docker.containers['oria'] = {'unrelated': True}
        replacement = 'sha256:' + '4' * 64
        self.config['controller']['image'] = replacement
        self.write_config()
        self.docker.images[replacement] = {'Id': replacement, 'Config': {'Volumes': None}}
        self.assertTrue(self.check(ensure=True)['ok'])
        for name, container in before.items():
            self.assertEqual(self.docker.containers[name], container)
        self.assertEqual(self.docker.containers['oria'], {'unrelated': True})
        self.assertEqual(len(self.docker.containers), 4)

    def test_invalid_config_rejected_before_docker_access(self):
        for config in ({}, [], {'controller': [], 'executor_image': EXECUTOR},
                       {'controller': {'image': 'latest'}, 'executor_image': EXECUTOR}):
            self.config = config
            self.write_config()
            with self.assertRaises(image_guard.GuardError):
                self.check(ensure=True)
        self.assertFalse(self.docker.calls)

    def test_image_declared_volume_is_rejected_before_container_creation(self):
        self.docker.images[EXECUTOR]['Config']['Volumes'] = {'/data': {}}
        result = self.check(ensure=True)
        self.assertFalse(result['ok'])
        self.assertEqual(result['images'][1]['status'], 'unsafe_image')
        self.assertFalse(self.docker.containers)

    def test_creation_failure_is_reported_without_success_or_cleanup(self):
        self.docker.create_error = True
        result = self.check(ensure=True)
        self.assertFalse(result['ok'])
        self.assertEqual(result['images'][0]['status'], 'create_failed')
        self.assertFalse(self.docker.containers)

    def test_docker_unavailable_fails_closed(self):
        def unavailable(*args, **kwargs):
            raise FileNotFoundError('docker')
        with self.assertRaises(image_guard.GuardError):
            image_guard.guard(self.root, ensure=True, run=unavailable)

    def test_separate_installations_do_not_claim_each_others_anchors(self):
        self.check(ensure=True)
        other = self.root / 'other'
        (other / 'control').mkdir(parents=True)
        (other / 'control/config.json').write_text(json.dumps(self.config))
        self.assertTrue(image_guard.guard(other, ensure=True, run=self.docker)['ok'])
        self.assertEqual(len(self.docker.containers), 4)

    def test_concurrent_creation_is_accepted_only_after_inspecting_ownership(self):
        base = self.docker
        def concurrent(args, **kwargs):
            result = base(args, **kwargs)
            if args[:3] == ['docker', 'container', 'create']:
                result.returncode = 1  # competitor won the same name; inspect its container
            return result
        self.assertTrue(image_guard.guard(self.root, ensure=True, run=concurrent)['ok'])

    def test_successful_create_with_wrong_container_is_not_reported_protected(self):
        base = self.docker
        def wrong_container(args, **kwargs):
            result = base(args, **kwargs)
            if args[:3] == ['docker', 'container', 'create']:
                name = args[args.index('--name') + 1]
                base.containers[name]['Image'] = 'sha256:' + '9' * 64
            return result
        result = image_guard.guard(self.root, ensure=True, run=wrong_container)
        self.assertFalse(result['ok'])
        self.assertEqual(result['images'][0]['status'], 'conflict')

    def test_cli_emits_json_and_failing_exit_for_invalid_config_without_docker(self):
        (self.root / 'control/config.json').write_text('{invalid')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = image_guard.main(['--root', str(self.root), 'status'])
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(output.getvalue())['ok'])

    def test_inspection_failure_and_malformed_output_fail_closed(self):
        for response in (subprocess.CompletedProcess([], 1, '', 'denied'),
                         subprocess.CompletedProcess([], 0, '{}', ''),
                         subprocess.CompletedProcess([], 0, 'null', '')):
            with self.subTest(response=response):
                def bad_inspect(args, **kwargs):
                    if args[:3] == ['docker', 'container', 'ls']:
                        return response
                    return self.docker(args, **kwargs)
                if response.returncode:
                    with self.assertRaises(image_guard.GuardError):
                        image_guard.guard(self.root, ensure=True, run=bad_inspect)
                else:
                    with self.assertRaises(image_guard.GuardError):
                        image_guard.guard(self.root, ensure=True, run=lambda *a, **k: response)
        self.assertFalse(self.docker.containers)

    def test_external_controller_retains_executor_without_requiring_a_brain(self):
        self.config['controller'] = {'mode': 'external_grok'}
        self.write_config()
        result = self.check(ensure=True)
        self.assertTrue(result['ok'])
        self.assertEqual([row['role'] for row in result['images']], ['executor'])

    def test_subscription_controller_without_brain_fails_before_docker(self):
        self.config['controller'] = {'mode': 'subscriptions'}
        self.write_config()
        with self.assertRaises(image_guard.GuardError):
            self.check(ensure=True)
        self.assertFalse(self.docker.calls)

    def test_pending_release_config_is_retained_using_installation_scope(self):
        pending = self.root / 'release-config.json'
        replacement = 'sha256:' + '4' * 64
        self.docker.images[replacement] = {'Id': replacement, 'Config': {'Volumes': None}}
        config = copy.deepcopy(self.config)
        config['controller']['image'] = replacement
        pending.write_text(json.dumps(config))
        result = image_guard.guard(self.root, ensure=True, run=self.docker, config_path=pending)
        self.assertTrue(result['ok'])
        self.assertEqual({c['Image'] for c in self.docker.containers.values()}, {replacement, EXECUTOR_ID})
        # The active control/config.json is never rewritten by retention.
        self.assertEqual(json.loads((self.root / 'control/config.json').read_text()), self.config)
        self.config = config
        self.write_config()
        self.docker.calls.clear()
        self.assertTrue(self.check(ensure=True)['ok'])
        self.assertFalse(any(a[:3] == ['docker', 'container', 'create'] for a in self.docker.calls))


if __name__ == '__main__':
    unittest.main()
