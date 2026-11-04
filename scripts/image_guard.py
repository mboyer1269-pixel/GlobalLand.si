#!/usr/bin/env python3
"""Retain configured images using inert container references; never start or delete."""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess

PIN = re.compile(r'(?:[A-Za-z0-9./:_-]+@)?sha256:[0-9a-f]{64}')
IMAGE_ID = re.compile(r'sha256:[0-9a-f]{64}')
LABEL = 'org.globalland.image-guard'


class GuardError(Exception):
    """An inspection or configuration error; no raw Docker/config data is printed."""


def _docker(run, *args):
    try:
        return run(['docker', *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GuardError('Docker unavailable or inspection timed out; retry status.') from exc


def _object(result):
    if result.returncode:
        raise GuardError('Docker inspection failed; verify daemon access and retry status.')
    try:
        objects = json.loads(result.stdout)
        if len(objects) != 1 or not isinstance(objects[0], dict):
            raise ValueError()
        return objects[0]
    except (ValueError, TypeError, KeyError) as exc:
        raise GuardError('Docker inspection returned invalid data.') from exc


def _labels(scope, role, image_id):
    return {LABEL: 'v1', LABEL + '.scope': scope,
            LABEL + '.role': role, LABEL + '.image': image_id}


def _anchor_status(run, row, labels):
    name = row['anchor']
    result = _docker(run, 'container', 'ls', '-a', '--filter', 'name=^/' + name + '$',
                     '--format', '{{.ID}}')
    if result.returncode:
        raise GuardError('Cannot list anchor containers; verify Docker access.')
    if not result.stdout.strip():
        return 'unprotected'
    container = _object(_docker(run, 'container', 'inspect', name))
    config = container.get('Config') or {}
    host = container.get('HostConfig') or {}
    state = container.get('State') or {}
    owned = all((config.get('Labels') or {}).get(key) == value for key, value in labels.items())
    safe = (container.get('Name') == '/' + name and container.get('Image') == row['image_id']
            and state.get('Running') is False and state.get('Status') == 'created'
            and host.get('NetworkMode') == 'none' and host.get('ReadonlyRootfs') is True
            and host.get('AutoRemove') is False and not host.get('Binds')
            and (host.get('RestartPolicy') or {}).get('Name') == 'no'
            and not container.get('Mounts') and config.get('Entrypoint') == ['/bin/false']
            and config.get('User') == '65534:65534')
    return 'protected' if owned and safe else 'conflict'


def guard(root, ensure=False, run=subprocess.run, config_path=None):
    """Inspect both configured images before creating anything; return JSON-safe status."""
    root = pathlib.Path(root).resolve()
    try:
        config = json.loads(pathlib.Path(config_path or root / 'control/config.json').read_text(encoding='utf-8'))
        controller = config['controller']
        if not isinstance(controller, dict):
            raise ValueError()
        references = [('executor', config['executor_image'])]
        if controller.get('mode') != 'external_grok' or controller.get('image'):
            references.insert(0, ('brain', controller['image']))
        if any(not isinstance(ref, str) or not PIN.fullmatch(ref) for _, ref in references):
            raise ValueError()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise GuardError('control/config.json must contain pinned controller.image and executor_image.') from exc
    scope = hashlib.sha256(str(root).encode()).hexdigest()
    rows = []
    for role, ref in references:
        row = {'role': role, 'reference': ref, 'status': 'image_unavailable'}
        rows.append(row)
        result = _docker(run, 'image', 'inspect', ref)
        if result.returncode:
            continue
        image = _object(result)
        image_id = image.get('Id', '')
        if not isinstance(image_id, str) or not IMAGE_ID.fullmatch(image_id):
            raise GuardError('Docker returned an invalid image ID.')
        row['image_id'] = image_id
        row['anchor'] = 'globalland-image-guard-' + scope[:12] + '-' + role + '-' + image_id[7:]
        if (image.get('Config') or {}).get('Volumes'):
            row['status'] = 'unsafe_image'
            continue
        row['status'] = _anchor_status(run, row, _labels(scope, role, image_id))
    if ensure and all(row['status'] in ('protected', 'unprotected') for row in rows):
        for row in rows:
            if row['status'] == 'protected':
                continue
            labels = _labels(scope, row['role'], row['image_id'])
            args = ['container', 'create', '--name', row['anchor'], '--pull', 'never',
                    '--network', 'none', '--restart', 'no', '--read-only',
                    '--user', '65534:65534', '--cap-drop', 'ALL',
                    '--security-opt', 'no-new-privileges:true', '--entrypoint', '/bin/false']
            for key, value in labels.items():
                args.extend(['--label', key + '=' + value])
            args.extend([row['image_id'], 'image-retention-anchor'])
            _docker(run, *args)
            # Inspect even after failure: another invocation may have created it.
            row['status'] = _anchor_status(run, row, labels)
            if row['status'] == 'unprotected':
                row['status'] = 'create_failed'
            if row['status'] != 'protected':
                break
    return {'ok': all(row['status'] == 'protected' for row in rows), 'images': rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='/opt/globalland')
    parser.add_argument('--config', help='Pending release config; defaults to ROOT/control/config.json')
    parser.add_argument('action', choices=('status', 'ensure'))
    args = parser.parse_args(argv)
    try:
        result = guard(args.root, ensure=args.action == 'ensure', config_path=args.config)
    except GuardError as exc:
        result = {'ok': False, 'error': str(exc)}
    print(json.dumps(result, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
