"""Run real installers ONLY on an explicitly opted-in disposable GitHub runner.

Not collected by unit-test discovery. It creates /opt/globalland once, and
leaves that synthetic install to disposal of the runner. No production secrets,
models, remote Git writes or productive cycles are used.
"""
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path('/opt/globalland')
CRON = pathlib.Path('/etc/cron.d/globalland')
ROTATION = pathlib.Path('/etc/logrotate.d/globalland')
LOGS = pathlib.Path('/var/log/globalland')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def guard():
    require(sys.platform == 'linux' and os.geteuid() == 0, 'Linux administrator required')
    for key, value in [('GLOBALLAND_BOOTSTRAP_SMOKE', '1'), ('GITHUB_ACTIONS', 'true'),
                       ('RUNNER_ENVIRONMENT', 'github-hosted')]:
        require(os.environ.get(key) == value, 'Disposable hosted CI opt-in required: ' + key)
    for path in (ROOT, CRON, ROTATION, LOGS, pathlib.Path('/etc/cron.d/globalland-think')):
        require(not path.exists() and not path.is_symlink(), 'Preexisting install preserved: ' + str(path))
    image = os.environ.get('GLOBALLAND_BOOTSTRAP_IMAGE', '')
    require(re.fullmatch(r'node:22-bookworm@sha256:[0-9a-f]{64}', image), 'Pinned Node image required')
    return image


def run(args, *, env, cwd=None, timeout=60, success=True):
    result = subprocess.run([str(x) for x in args], env=env, cwd=cwd,
                            capture_output=True, text=True, timeout=timeout)
    if success:
        # Do not dump installer output: it may include generated key material.
        known = ('unsafe maintenance directory', 'unsafe maintenance file',
                 'enabled executor with pinned image required', 'installed revision required',
                 'finalize the installed source and control first',
                 'custom base schedule preserved; review manual migration')
        reason = next((text for text in known if text in result.stderr), 'details withheld')
        require(result.returncode == 0, 'Command failed: ' + str(args[0]) +
                ' (exit ' + str(result.returncode) + '; ' + reason + ')')
    return result


def fingerprint(path):
    info = path.stat()
    return (hashlib.sha256(path.read_bytes()).hexdigest(), info.st_mode & 0o777, info.st_mtime_ns)


def pause_scheduler(env):
    """Pause the real daemon before it can ever observe a GlobalLand schedule.

    Never resume it on this disposable runner, including driver failure. The
    workflow also stops the entire service after this step, successful or not.
    """
    pid = int(run(['systemctl', 'show', '--property=MainPID', '--value', 'cron.service'], env=env).stdout)
    require(pid > 1 and not CRON.exists(), 'Cron must be active before new schedules exist')
    group = run(['systemctl', 'show', '--property=ControlGroup', '--value', 'cron.service'], env=env).stdout.strip()
    require(group == '/system.slice/cron.service', 'Unexpected disposable cron cgroup')
    run(['systemctl', 'kill', '--kill-whom=main', '--signal=SIGSTOP', 'cron.service'], env=env)
    for attempt in range(100):
        state = pathlib.Path('/proc/%d/status' % pid).read_text()
        if re.search(r'^State:\s+T\b', state, re.M):
            return pathlib.Path('/sys/fs/cgroup' + group + '/cgroup.procs')
        time.sleep(.01)
    raise RuntimeError('Cron daemon did not stop before schedule installation')


def delayed_child(base, group):
    """A harmless launched child waits until cleanup before trying a lock.

    Its only possible effect is a synthetic marker, never a supervisor call.
    Put it in the cron cgroup to exercise draining already launched children.
    """
    code = ('import fcntl,pathlib,sys; signal=sys.stdin.buffer.read(1); '
            'lock=open(sys.argv[1],"a"); '
            'fcntl.flock(lock,fcntl.LOCK_EX); '
            'pathlib.Path(sys.argv[2]).write_text("late") if signal==b"x" else None')
    marker = base / 'late-child'
    child = subprocess.Popen([sys.executable, '-c', code,
        str(ROOT / 'state/queue-schedule.lock'), str(marker)], stdin=subprocess.PIPE)
    group.write_text(str(child.pid))
    require(str(child.pid) in group.read_text().split(), 'Delayed child not in scheduler group')
    return child, marker


def main():
    image = guard()
    import fcntl
    source = pathlib.Path(__file__).resolve().parents[1]
    handles = []
    owned_cron = None
    delayed = None
    group = pause_scheduler(os.environ)
    with tempfile.TemporaryDirectory(prefix='globalland-bootstrap-ci-') as temporary:
        base = pathlib.Path(temporary)
        config = base / 'gitconfig'
        config.touch(mode=0o600)
        env = {**os.environ, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': str(config)}
        # Root owns the reviewed clone. Trust only the runner's source checkout
        # during local transfer; no machine-wide safe.directory change.
        run(['git', 'config', '--file', config, 'safe.directory', source], env=env)
        checkout = base / 'reviewed'
        run(['git', 'clone', '-q', '--no-local', source, checkout], env=env)
        revision = run(['git', '-C', checkout, 'rev-parse', 'HEAD'], env=env).stdout.strip()
        original = run(['git', '-C', source, 'rev-parse', 'HEAD'], env=env).stdout.strip()
        require(revision == original, 'Reviewed source revision changed')
        # The finalizer still uses Git clone. Only its transport is local;
        # the synthetic deploy key is never registered on an external account.
        run(['git', 'config', '--file', config, 'url.' + checkout.as_uri() + '.insteadOf',
             'git@github.com:mboyer1269-pixel/GlobalLand.si.git'], env=env)
        try:
            run(['bash', checkout / 'scripts/setup_vps.sh', revision, image], env=env)
            require((ROOT / 'backups').is_dir(), 'Fresh bootstrap omitted backups')
            for name in ('ssh', 'state', 'backups'):
                mode = (ROOT / name).stat().st_mode & 0o777
                require(mode == 0o700, 'Private directory mode: ' + name + ' got ' + oct(mode))
            for name in ('ssh/deploy_key', 'control/config.json'):
                require((ROOT / name).stat().st_mode & 0o077 == 0, 'Private file exposed: ' + name)
            controls = [p for p in (checkout / 'scripts').iterdir()
                        if p.suffix in ('.py', '.js', '.sh', '.json') and p.is_file()]
            for path in controls:
                require((ROOT / 'control' / path.name).read_bytes() == path.read_bytes(),
                        'Installed control differs: ' + path.name)
            require(not CRON.exists() and not (ROOT / 'source.git').exists(),
                    'Initial setup must not schedule or finalize itself')
            initial_config = fingerprint(ROOT / 'control/config.json')
            second = run(['bash', checkout / 'scripts/setup_vps.sh', revision, image],
                         env=env, success=False)
            require(second.returncode != 0, 'Second setup overwrote an existing install')
            require(fingerprint(ROOT / 'control/config.json') == initial_config, 'Existing config changed')
            # Only a fixture for the local transport; not a verified GitHub host key.
            hosts = ROOT / 'ssh/known_hosts'
            hosts.touch(mode=0o600)
            run(['bash', ROOT / 'control/finalize_setup.sh'], env=env)
            bare = ['git', '--git-dir=' + str(ROOT / 'source.git')]
            require(run([*bare, 'rev-parse', '--is-bare-repository'], env=env).stdout.strip() == 'true',
                    'Finalized source is not bare')
            require(run([*bare, 'rev-parse', 'HEAD'], env=env).stdout.strip() == revision, 'Wrong source revision')
            status = json.loads(run([sys.executable, ROOT / 'control/supervisor.py', 'status'], env=env).stdout)
            require(status['bank']['state'] == 'UNFUNDED', 'Fresh bank invented funding')
            require(status['world']['state'] == 'ACTIVE' and len(status['world']['agents']) > 0,
                    'Installed world failed to initialize')
            require(not (ROOT / 'state/private/controller-last-status.json').exists(),
                    'Bootstrap unexpectedly invoked a controller')
            for mode in ('queue', 'daily'):
                handle = (ROOT / ('state/' + mode + '-schedule.lock')).open('a')
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                handles.append(handle)
            command = [sys.executable, ROOT / 'control/install_maintenance.py']
            preview = json.loads(run(command, env=env).stdout)
            require(set(preview['changes']) == {'cron', 'rotation'} and not CRON.exists(),
                    'Preview changed or omitted maintenance')
            owned_cron = preview['templates']['cron'].encode()
            installed = json.loads(run([*command, '--apply'], env=env).stdout)
            require(set(installed['changes']) == {'cron', 'rotation'}, 'Maintenance not installed')
            before = {p: fingerprint(p) for p in (CRON, ROTATION)}
            repeat = json.loads(run([*command, '--apply'], env=env).stdout)
            require(repeat['changes'] == [] and repeat['backup'] is None, 'Maintenance not idempotent')
            require({p: fingerprint(p) for p in before} == before, 'Idempotent apply rewrote files')
            for path in [LOGS / (name + '.log') for name in ('queue', 'daily', 'think')] + [
                    ROOT / 'state/private/mail-cron.log']:
                require(path.stat().st_mode & 0o777 == 0o600, 'Diagnostic log exposed')
            require(fingerprint(ROOT / 'control/config.json') == initial_config, 'Maintenance changed configuration')
            require(run([*bare, 'rev-parse', 'HEAD'], env=env).stdout.strip() == revision,
                    'An unexpected cycle changed the source')
            delayed, marker = delayed_child(base, group)
            report = dict(state='VERIFIED', revision=revision, control_files=len(controls),
                bank='UNFUNDED', git_transport='local_fixture', maintenance='idempotent',
                productive_cycles=0, production_restore='NOT_TESTED')
        finally:
            # Remove only the schedule this test reviewed, before unlocking.
            # Never delete a previous installation or any unrelated cron.
            if owned_cron is not None and CRON.exists():
                require(not CRON.is_symlink() and CRON.read_bytes() == owned_cron,
                        'Unexpected cron retained; runner must be disposed')
                CRON.unlink()
            for handle in handles:
                handle.close()
        if delayed is not None:
            try:
                delayed.stdin.write(b'x'); delayed.stdin.flush()
            except BrokenPipeError:
                pass
            delayed.wait(timeout=5)
            require(not marker.exists(), 'Delayed cron child ran after cleanup released its lock')
        print(json.dumps(report))


if __name__ == '__main__':
    main()
