#!/usr/bin/env python3
"""Operator setup for the two subscription providers already proven on this VPS."""
import fcntl
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

# Runtime code comes from the installed control, not the task checkout.
sys.path.insert(0, '/opt/globalland/control')
from controller import Controller
from supervisor import atomic_json

JOB = ('*/30 * * * * root /usr/bin/python3 /opt/globalland/control/supervisor.py think '
       '>> /var/log/globalland/think.log 2>&1 && '
       '/usr/bin/python3 /opt/globalland/control/supervisor.py queue '
       '>> /var/log/globalland/think.log 2>&1\n')


def activate(root, cron, log):
    root, cron, log = map(pathlib.Path, (root, cron, log))
    subprocess.run(['systemctl', 'is-active', '--quiet', 'cron'], check=True)
    with (root / 'state/supervisor.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if cron.exists() and cron.read_text() != JOB:
            raise ValueError('existing schedule differs; review before replacing it')
        revision = (root / 'control/REVISION').read_text().strip()
        if not re.fullmatch(r'[0-9a-f]{40}', revision):
            raise ValueError('installed control revision missing')
        published = set()
        for path in (root / 'state/controller').glob('THINK-*.json'):
            turn = json.loads(path.read_text())
            if turn.get('published') is True:
                published.add(turn.get('provider'))
        if not {'codex', 'claude'} <= published:
            raise ValueError('each provider needs a published turn before scheduling')
        path = root / 'control/config.json'
        old = json.loads(path.read_text())
        config = json.loads(json.dumps(old))
        config['controller']['providers'] = ['codex', 'claude']
        controller = Controller(root, None, None, config)
        for provider in ('codex', 'claude'):
            controller.check_provider(provider)
        backup = pathlib.Path(tempfile.mkdtemp(prefix='autonomy-', dir=root / 'backups'))
        atomic_json(backup / 'config-before.json', old)
        log.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with log.open('a'):
            os.chmod(log, 0o600)
        fd, temporary = tempfile.mkstemp(prefix='.globalland-think-', dir=cron.parent)
        config_attempted = cron_replaced = False
        try:
            with os.fdopen(fd, 'w') as stream:
                stream.write(JOB)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o644)
            config_attempted = True
            atomic_json(path, config)
            os.replace(temporary, cron)
            cron_replaced = True  # A visible schedule must retain its matching config.
            directory = os.open(cron.parent, os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except Exception:
            if config_attempted and not cron_replaced:
                try:
                    atomic_json(path, old)
                except Exception as rollback_error:
                    raise RuntimeError('Activation failed; restore config from ' + str(backup)) from rollback_error
            raise
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return {'providers': ['codex', 'claude'], 'interval_minutes': 30,
            'control_revision': revision, 'backup': str(backup)}


if __name__ == '__main__':
    try:
        if os.geteuid() != 0:
            raise ValueError('Run this administrative setup as root')
        report = activate('/opt/globalland', '/etc/cron.d/globalland-think', '/var/log/globalland/think.log')
        print('Codex + Claude : horaires installes, toutes les 30 minutes.', flush=True)
        print('Configuration precedente : ' + report['backup'], flush=True)
        print('Lancement immediat en cours...', flush=True)
        for mode in ('think', 'queue'):
            subprocess.run(['/usr/bin/python3', '/opt/globalland/control/supervisor.py', mode], check=True)
        print('Lancement termine; resultats a verifier dans GitHub.', flush=True)
    except Exception as error:
        print('GlobalLand start stopped: ' + str(error), file=sys.stderr)
        sys.exit(1)
