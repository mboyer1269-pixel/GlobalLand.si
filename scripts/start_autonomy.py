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
EVENT_JOB = ('*/30 * * * * root /usr/bin/python3 /opt/globalland/control/supervisor.py think '
             '>> /var/log/globalland/think.log 2>&1\n'
             '* * * * * root /usr/bin/python3 /opt/globalland/control/supervisor.py wake '
             '>> /var/log/globalland/think.log 2>&1\n')


def _replace_schedule(cron, content):
    fd, temporary = tempfile.mkstemp(prefix='.globalland-think-', dir=cron.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            stream.write(content);stream.flush();os.fsync(stream.fileno())
        os.chmod(temporary,0o644);os.replace(temporary,cron)
        directory=os.open(cron.parent,os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def activate(root, cron, log):
    root, cron, log = map(pathlib.Path, (root, cron, log))
    subprocess.run(['systemctl', 'is-active', '--quiet', 'cron'], check=True)
    with (root / 'state/supervisor.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous_schedule=cron.read_text() if cron.exists() else None
        if previous_schedule is not None and previous_schedule not in (JOB,EVENT_JOB):
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
        from initiative import settings
        initiative=settings(old)
        schedule=EVENT_JOB if initiative['enabled'] else JOB
        config = json.loads(json.dumps(old))
        config['controller']['providers'] = ['codex', 'claude']
        controller = Controller(root, None, None, config)
        for provider in ('codex', 'claude'):
            controller.check_provider(provider)
        backup = pathlib.Path(tempfile.mkdtemp(prefix='autonomy-', dir=root / 'backups'))
        atomic_json(backup / 'config-before.json', old)
        atomic_json(backup / 'schedule-before.json', {'content':previous_schedule})
        log.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with log.open('a'):
            os.chmod(log, 0o600)
        config_attempted = schedule_attempted = False
        try:
            # Complete historical source inventory under the same admission lock
            # before publishing a schedule that enables producers.
            if initiative['enabled']:
                from initiative import Store
                Store(root,config)
            config_attempted = True
            atomic_json(path, config)
            schedule_attempted=True
            _replace_schedule(cron,schedule)
        except Exception:
            try:
                # Restore the visible pair even if rename succeeded but its
                # directory fsync failed. A replacement failure before rename
                # leaves the previous usable schedule in place.
                if schedule_attempted:
                    current=cron.read_text() if cron.exists() else None
                    if current!=previous_schedule:
                        if previous_schedule is None:
                            cron.unlink(missing_ok=True)
                            directory=os.open(cron.parent,os.O_DIRECTORY)
                            try:os.fsync(directory)
                            finally:os.close(directory)
                        else:_replace_schedule(cron,previous_schedule)
                if config_attempted:atomic_json(path,old)
            except Exception as rollback_error:
                raise RuntimeError('Activation failed; restore config and schedule from ' + str(backup)) from rollback_error
            raise
    return {'providers': ['codex', 'claude'], 'interval_minutes': 30,
            'initiative_enabled':initiative['enabled'],'wake_interval_minutes':1 if initiative['enabled'] else None,
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
