#!/usr/bin/env python3
"""Go-live checklist for the VPS: read-only, prints GO or NO-GO with the exact gaps.

  sudo python3 /opt/globalland/control/preflight.py

Never prints a secret, never changes anything, never calls a paid API. Each
check says what to do when it fails. Exit code 0 only when every REQUIRED check
passes; OPTIONAL checks (Apify, Cloudflare, broker) are reported separately.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

DIGEST = re.compile(r'(?:[A-Za-z0-9./:_-]+@)?sha256:[0-9a-f]{64}')


def _private_file(path):
    return path.is_file() and not path.is_symlink() and not (path.stat().st_mode & 0o077)


def checks(root, run=subprocess.run, disk=shutil.disk_usage):
    root = pathlib.Path(root)
    out = []

    def add(name, ok, fix, level='REQUIRED', detail=None):
        out.append(dict(check=name, ok=bool(ok), level=level, fix=None if ok else fix, detail=detail))

    config_path = root / 'control' / 'config.json'
    try:
        config = json.loads(config_path.read_text())
    except (OSError, ValueError):
        config = None
    add('config.json lisible', config is not None, 'Réinstaller le contrôle avec upgrade_vps.sh.')
    config = config or {}
    revision = root / 'control' / 'REVISION'
    add('Révision installée connue', revision.is_file(), 'Installer depuis un SHA revu (upgrade_vps.sh).',
        detail=revision.read_text().strip()[:40] if revision.is_file() else None)
    controller = config.get('controller') or {}
    add('Contrôleur sur abonnements', controller.get('mode') == 'subscriptions',
        'configure_subscriptions.py --image … --providers codex,claude --confirm-extra-usage-disabled')
    providers = controller.get('providers') or []
    add('Au moins deux fournisseurs (bascule et revue croisée)', len(set(providers) & {'codex', 'claude', 'cursor'}) >= 2,
        'Configurer --providers codex,claude : un seul fournisseur empêche la règle des deux clés sans le fondateur.')
    add('Image du cerveau épinglée', bool(DIGEST.fullmatch(str(controller.get('image', '')))), 'Construire l\'image et passer --image sha256:…')
    for provider in providers:
        cred = root / 'credentials' / provider
        add('Connexion %s présente' % provider, cred.is_dir() and any(cred.iterdir()) if cred.is_dir() else False,
            'login_subscriptions.sh %s' % provider)
    add('Exécuteur configuré', config.get('executor_enabled') is True and bool(DIGEST.fullmatch(str(config.get('executor_image', '')))),
        'upgrade_vps.sh fixe executor_enabled et executor_image.')
    try:
        docker = run(['docker', 'info', '--format', '{{.ServerVersion}}'], capture_output=True, text=True, timeout=20)
        docker_ok = docker.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        docker_ok = False
    add('Docker joignable', docker_ok, 'Démarrer Docker ; GlobalLand ne touche pas aux conteneurs d\'Oria.')
    cron = pathlib.Path('/etc/cron.d/globalland-think')
    add('Horaire des cycles de réflexion installé', cron.is_file() or (root / 'state' / 'cron-test').exists(), 'start_autonomy.py (voir INSTALL.md).')
    try:
        free_gb = disk(str(root)).free / 1e9
    except OSError:
        free_gb = 0
    add('Espace disque ≥ 2 Go', free_gb >= 2, 'Libérer de l\'espace (images Docker inutilisées, anciennes releases).', detail='%.1f Go libres' % free_gb)
    state = root / 'state'
    add('État privé protégé (0700)', (state / 'private').is_dir() and not ((state / 'private').stat().st_mode & 0o077),
        'chmod 700 /opt/globalland/state/private')

    broker = controller.get('broker') or {}
    add('Courtier MCP activé', broker.get('enabled') is True, 'configure_subscriptions.py … --broker on', level='OPTIONAL')
    apify = config.get('apify') or {}
    add('Apify activé', apify.get('enabled') is True, 'Ajouter le bloc "apify" (INSTALL.md).', level='OPTIONAL')
    add('Token Apify privé (600)', _private_file(root / 'credentials' / 'apify' / 'token'),
        'Installer /opt/globalland/credentials/apify/token en mode 600.', level='OPTIONAL')
    cloudflare = config.get('cloudflare') or {}
    add('Cloudflare activé', cloudflare.get('enabled') is True and bool(re.fullmatch(r'[0-9a-f]{32}', str(cloudflare.get('account_id', '')))),
        'Ajouter le bloc "cloudflare" avec account_id (INSTALL.md).', level='OPTIONAL')
    add('Token Cloudflare privé (600)', _private_file(root / 'credentials' / 'cloudflare' / 'token'),
        'Installer /opt/globalland/credentials/cloudflare/token en mode 600.', level='OPTIONAL')
    return out


def verdict(results):
    required = [r for r in results if r['level'] == 'REQUIRED']
    return 'GO' if all(r['ok'] for r in required) else 'NO-GO'


def main(root='/opt/globalland'):
    results = checks(root)
    print(json.dumps(dict(verdict=verdict(results), checks=results), ensure_ascii=False, indent=2))
    return 0 if verdict(results) == 'GO' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else '/opt/globalland'))
