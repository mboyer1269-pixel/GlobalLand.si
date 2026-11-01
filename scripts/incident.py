#!/usr/bin/env python3
"""Triage of a silent or blocked world on the VPS: read-only, one command, output safe to share.

  sudo python3 scripts/incident.py /opt/globalland

Runs from any checkout (standard library only): it does not need the new code to
be installed, so it works on the version that is failing. It never prints file
contents, log lines, tokens or account names: only fixed failure codes from the
installed controller, ages, counts, container names and the exact fix for each
finding. It changes nothing (the supervisor lock is probed without waiting and
released at once).
"""
import datetime
import fcntl
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

KNOWN_KINDS = ('TimeoutError', 'FileNotFoundError', 'PermissionError', 'ValueError', 'OSError', 'RuntimeError', 'Exception')
# Fixed codes written by the installed controller (supervisor.FAILURE_DEFAULTS and FAILURE_MESSAGES).
FIXES = {
    'all_subscription_providers_failed': (
        'Chaque fournisseur a échoué à ce cycle (détail dans attempts). Vérifier la connexion et le quota de chacun : '
        'sudo python3 /opt/globalland/control/diagnose_subscriptions.py --image <image> --provider codex (puis claude). '
        'Session expirée : sudo bash /opt/globalland/control/login_subscriptions.sh <fournisseur>. Quota hebdomadaire épuisé : attendre sa remise à zéro.'),
    'provider_timeout': (
        'Le fournisseur n\'a pas répondu à temps : quota épuisé, file d\'attente du fournisseur ou VPS saturé. '
        'Vérifier avec diagnose_subscriptions.py, puis relancer un cycle : sudo python3 /opt/globalland/control/supervisor.py think'),
    'invalid_provider_structured_output': (
        'La CLI a répondu autre chose que du JSON de décision : message de quota, déconnexion ou changement de version de la CLI. '
        'diagnose_subscriptions.py montre l\'état de connexion et les options acceptées.'),
    'provider_or_decision_validation_failed': (
        'Réponse refusée par la validation (souvent un texte de quota ou de connexion au lieu du JSON). Même vérification que ci-dessus.'),
    'invalid_controller_decision': 'Décision mal formée par le modèle. Si tous les fournisseurs échouent ainsi, installer la PR #5 (guide d\'outils et schéma à jour).',
    'invalid_controller_action': 'Action hors protocole proposée par le modèle. Même correction : installer la PR #5.',
    'invalid_task_path': 'Chemin de fichier refusé dans la décision. Même correction : installer la PR #5.',
    'secret_detected': (
        'Un motif de secret a été détecté : publication bloquée volontairement. Ne pas relancer à l\'aveugle ; chercher un token copié dans '
        'products/ ou world/ et le révoquer chez son fournisseur.'),
    'container_cleanup_unverified': 'Un conteneur cerveau n\'a pas pu être supprimé : voir le constat sur les conteneurs, puis docker rm -f <nom>.',
    'runtime_dependency_missing': 'Programme ou image introuvable : vérifier docker et l\'image (docker image inspect <image du contrôleur>).',
    'runtime_permission_denied': 'Permission refusée : vérifier les propriétaires de /opt/globalland/state et /opt/globalland/credentials (root, 0700).',
    'runtime_io_failure': 'Erreur d\'entrée-sortie : vérifier l\'espace disque (df -h) et la santé de Docker.',
    'runtime_failure': 'Erreur d\'exécution non classée : lancer un cycle à la main pour voir le message (sudo python3 /opt/globalland/control/supervisor.py think).',
    'unexpected_planner_failure': 'Erreur inattendue : lancer un cycle à la main pour voir le message.',
}
SAFE_NAME = re.compile(r'[A-Za-z0-9_.-]{1,64}')
STAMP = re.compile(r'\d{4}-\d\d-\d\dT[0-9:.+Z-]{8,32}')


def _json(path):
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _code(value):
    return value if isinstance(value, str) and value in FIXES else ('unknown' if value is not None else None)


def _kind(value):
    return value if value in KNOWN_KINDS else ('unknown' if value is not None else None)


def _stamp(value):
    return value if isinstance(value, str) and STAMP.fullmatch(value) else None


def _age_minutes(path, now):
    try:
        return round((now - path.stat().st_mtime) / 60, 1)
    except OSError:
        return None


def collect(root, cron=pathlib.Path('/etc/cron.d/globalland-think'), log=pathlib.Path('/var/log/globalland/think.log'),
            run=subprocess.run, now=None, disk=shutil.disk_usage):
    root = pathlib.Path(root)
    now = now if now is not None else datetime.datetime.now(datetime.timezone.utc).timestamp()
    facts = {}
    private = root / 'state' / 'private'
    try:
        revision = (root / 'control' / 'REVISION').read_text().strip()
        facts['installed_revision'] = revision if re.fullmatch(r'[0-9a-f]{7,40}', revision) else 'unreadable'
    except OSError:
        facts['installed_revision'] = None

    failure = _json(private / 'controller-failure.json')
    if failure is not None:
        facts['failure'] = dict(at=_stamp(failure.get('at')), stage=failure.get('stage') if failure.get('stage') == 'planner.tick' else None,
                                exception_type=_kind(failure.get('exception_type')), reason=_code(failure.get('reason')),
                                providers=[p for p in failure.get('providers') or [] if p in ('codex', 'claude', 'cursor')])
    status = _json(private / 'controller-run.json')
    if status is not None:
        attempts = []
        for item in status.get('attempts') or []:
            if isinstance(item, dict) and item.get('provider') in ('codex', 'claude', 'cursor'):
                attempts.append(dict(provider=item['provider'], status=item.get('status') if item.get('status') in ('FAILED', 'SUCCEEDED') else None,
                                     exception_type=_kind(item.get('exception_type')), reason=_code(item.get('reason'))))
        facts['last_turn'] = dict(turn=status.get('turn') if isinstance(status.get('turn'), str) and re.fullmatch(r'THINK-\d{1,10}', status['turn']) else None,
                                  at=_stamp(status.get('at')), state=status.get('state') if status.get('state') in ('RETRYING', 'BLOCKED', 'DECISION_READY') else None,
                                  attempts=attempts[:3])

    pending = 0
    for path in (root / 'state' / 'controller').glob('THINK-*.json'):
        saved = _json(path)
        if saved is not None and saved.get('published') is not True:
            pending += 1
    facts['unpublished_turns'] = pending

    facts['cron_installed'] = cron.is_file()
    backups = sorted((root / 'backups').glob('upgrade-*/cron-globalland-think')) if (root / 'backups').is_dir() else []
    facts['cron_backup'] = str(backups[-1]) if backups else None
    facts['log_age_minutes'] = _age_minutes(log, now)

    lock = root / 'state' / 'supervisor.lock'
    facts['lock_held'] = None
    if lock.exists():
        try:
            with open(lock, 'r') as handle:
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(handle, fcntl.LOCK_UN)
                    facts['lock_held'] = False
                except BlockingIOError:
                    facts['lock_held'] = True
        except OSError:
            pass
    facts['supervisor_processes'] = []
    try:
        ps = run(['ps', '-eo', 'pid=,etimes=,args='], capture_output=True, text=True, timeout=20)
        for line in ps.stdout.splitlines():
            parts = line.split(None, 2)
            if len(parts) == 3 and 'supervisor.py' in parts[2] and parts[0].isdigit() and parts[1].isdigit():
                mode = next((m for m in ('think', 'queue', 'daily') if m in parts[2].split()), 'other')
                facts['supervisor_processes'].append(dict(pid=int(parts[0]), minutes=round(int(parts[1]) / 60, 1), mode=mode))
    except (OSError, subprocess.TimeoutExpired):
        pass

    try:
        info = run(['docker', 'info', '--format', '{{.ServerVersion}}'], capture_output=True, text=True, timeout=20)
        facts['docker_ok'] = info.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        facts['docker_ok'] = False
    facts['brain_containers'] = []
    if facts['docker_ok']:
        try:
            listing = run(['docker', 'ps', '-a', '--filter', 'name=globalland', '--format', '{{.Names}}'], capture_output=True, text=True, timeout=20)
            facts['brain_containers'] = [n for n in listing.stdout.split() if SAFE_NAME.fullmatch(n)][:20]
        except (OSError, subprocess.TimeoutExpired):
            pass

    try:
        facts['disk_free_gb'] = round(disk(str(root)).free / 1e9, 1)
    except OSError:
        facts['disk_free_gb'] = None
    providers = (facts.get('failure') or {}).get('providers') or ['codex', 'claude']
    facts['credentials_present'] = {}
    for provider in providers:
        directory = root / 'credentials' / provider
        try:
            facts['credentials_present'][provider] = directory.is_dir() and any(directory.iterdir())
        except OSError:
            facts['credentials_present'][provider] = None
    return facts


def diagnose(facts):
    findings = []

    def add(code, severity, evidence, fix):
        findings.append(dict(code=code, severity=severity, evidence=evidence, fix=fix))

    stuck = [p for p in facts.get('supervisor_processes', []) if p['minutes'] > 60]
    if facts.get('lock_held') and stuck:
        add('SUPERVISOR_STUCK', 'CRITIQUE', 'verrou du superviseur tenu ; processus actifs depuis plus de 60 min : %s' % stuck,
            'Un cycle est bloqué et empêche tous les suivants. Après accord, arrêter le processus : sudo kill <pid> ; '
            'ne pas supprimer state/ ni les journaux.')
    if not facts.get('cron_installed'):
        if facts.get('cron_backup'):
            add('CRON_PAUSED_BY_UPGRADE', 'CRITIQUE', 'horaire absent de /etc/cron.d, copie trouvée : ' + facts['cron_backup'],
                'Une mise à jour interrompue a laissé les cycles en pause. Restaurer : sudo install -m 644 %s /etc/cron.d/globalland-think' % facts['cron_backup'])
        else:
            add('CRON_MISSING', 'CRITIQUE', 'aucun horaire /etc/cron.d/globalland-think', 'Réactiver les cycles : sudo python3 /opt/globalland/control/start_autonomy.py')
    elif facts.get('log_age_minutes') is not None and facts['log_age_minutes'] > 45:
        add('CRON_NOT_RUNNING', 'CRITIQUE', 'journal think.log muet depuis %s min alors que l\'horaire existe' % facts['log_age_minutes'],
            'Le service cron ne lance plus rien : sudo systemctl status cron, puis sudo systemctl restart cron.')
    if facts.get('docker_ok') is False:
        add('DOCKER_DOWN', 'CRITIQUE', 'docker info échoue', 'Démarrer Docker : sudo systemctl start docker (sans toucher aux conteneurs d\'Oria).')
    if facts.get('brain_containers'):
        add('LEFTOVER_CONTAINERS', 'HAUTE', 'conteneurs restants : ' + ', '.join(facts['brain_containers']),
            'Vérifier qu\'aucun cycle ne tourne (processus ci-dessus), puis : sudo docker rm -f <nom>.')
    if facts.get('disk_free_gb') is not None and facts['disk_free_gb'] < 2:
        add('DISK_LOW', 'HAUTE', '%s Go libres' % facts['disk_free_gb'], 'Libérer de l\'espace : sudo docker image prune ; anciennes releases et sauvegardes.')
    for provider, present in (facts.get('credentials_present') or {}).items():
        if present is False:
            add('CREDENTIALS_MISSING', 'HAUTE', 'aucune connexion enregistrée pour ' + provider,
                'Reconnecter : sudo bash /opt/globalland/control/login_subscriptions.sh ' + provider)
    failure = facts.get('failure')
    if failure and failure.get('reason'):
        add('PLANNER_' + failure['reason'].upper(), 'CRITIQUE', 'dernier échec du planificateur à %s (%s)' % (failure.get('at'), failure.get('exception_type')),
            FIXES.get(failure['reason'], 'Code inconnu de cet outil : lancer un cycle à la main pour voir le message.'))
    for attempt in (facts.get('last_turn') or {}).get('attempts', []):
        if attempt.get('status') == 'FAILED' and attempt.get('reason') and (not failure or attempt['reason'] != failure.get('reason')):
            add('PROVIDER_' + attempt['provider'].upper() + '_' + attempt['reason'].upper(), 'HAUTE',
                '%s a échoué (%s)' % (attempt['provider'], attempt.get('exception_type')), FIXES.get(attempt['reason'], 'Code inconnu.'))
    if facts.get('unpublished_turns'):
        add('UNPUBLISHED_TURNS', 'INFO', '%d décision(s) prête(s) non publiée(s)' % facts['unpublished_turns'],
            'Elles seront publiées au prochain cycle réussi ; ne pas les supprimer.')
    if not findings:
        add('NO_CAUSE_FOUND', 'INFO', 'aucun constat automatique', 'Lancer un cycle à la main et lire le message : sudo python3 /opt/globalland/control/supervisor.py think')
    order = {'CRITIQUE': 0, 'HAUTE': 1, 'INFO': 2}
    return sorted(findings, key=lambda f: order[f['severity']])


def main(argv):
    root = argv[1] if len(argv) > 1 else '/opt/globalland'
    facts = collect(root)
    print(json.dumps(dict(safe_to_share=True, facts=facts, findings=diagnose(facts)), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
