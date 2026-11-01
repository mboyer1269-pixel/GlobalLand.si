#!/usr/bin/env python3
"""Dead man's switch for GlobalLand, run by GitHub Actions (independent of the VPS).

The world can stop silently: a blocked controller publishes one READINESS
commit and then nothing, because identical states produce no commit. On
2026-11-01 the world stayed blocked for hours without anyone noticing.

This script reads the checked-out main branch and reports ALERT when:
- the supervisor has not committed for more than --max-silence-hours;
- world/controller.json says CONTROLLER_BLOCKED, STALE or DEGRADED;
- world/blockers.json has open actions for the founder.

Output: one JSON object on stdout. The workflow opens, updates or closes a
GitHub issue from it, so the founder gets an e-mail. No secret is read.
"""
import argparse
import json
import pathlib
import subprocess
import sys
import time

SUPERVISOR = 'globalland-supervisor'
BAD_STATES = ('CONTROLLER_BLOCKED', 'STALE', 'DEGRADED')


def last_supervisor_commit(repo):
    out = subprocess.run(['git', '-C', str(repo), 'log', '-1', '--author=' + SUPERVISOR, '--format=%ct'],
                         capture_output=True, text=True, check=True).stdout.strip()
    return int(out) if out else None


def read_json(repo, name):
    path = pathlib.Path(repo) / name
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def check(repo, now=None, max_silence_hours=2.0):
    now = time.time() if now is None else now
    reasons = []
    last = last_supervisor_commit(repo)
    age_hours = None if last is None else round((now - last) / 3600, 2)
    if last is None:
        reasons.append('Aucun commit du superviseur trouvé.')
    elif age_hours > max_silence_hours:
        reasons.append('Le superviseur ne publie plus rien depuis %.1f h (seuil %.1f h).' % (age_hours, max_silence_hours))
    controller = read_json(repo, 'world/controller.json') or {}
    state = controller.get('state')
    if state in BAD_STATES:
        reasons.append('Contrôleur dans l\'état %s : %s' % (state, controller.get('reason_code') or controller.get('reason') or 'voir world/controller.json'))
    blockers = read_json(repo, 'world/blockers.json') or {}
    founder = [c for c in blockers.get('open', []) if c.get('owner') == 'FOUNDER']
    if founder:
        reasons.append('%d action(s) attendent le fondateur : %s' % (len(founder), '; '.join(c.get('title', c.get('id', '?')) for c in founder[:5])))
    return dict(status='ALERT' if reasons else 'OK', reasons=reasons, last_supervisor_commit_age_hours=age_hours,
                controller_state=state, founder_actions=len(founder))


def issue_body(report):
    lines = ['GlobalLand a besoin d\'attention.', '']
    lines += ['- ' + r for r in report['reasons']]
    lines += ['', 'Que faire, dans l\'ordre :',
              '1. Sur le VPS : `sudo python3 /opt/globalland/control/supervisor.py status` et lire `state/private/controller-failure.json` (cause exacte, jamais publiée).',
              '2. Vérifier les connexions des abonnements (quota atteint, session expirée) : voir INSTALL.md.',
              '3. Lire `world/blockers.json` pour les actions qui t\'attendent.',
              '', 'Cette issue est ouverte et mise à jour chaque heure par le workflow `watchdog` ; elle se ferme seule au rétablissement.']
    return '\n'.join(lines)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--repo', default='.')
    p.add_argument('--max-silence-hours', type=float, default=2.0)
    p.add_argument('--body', action='store_true', help='print the issue body instead of JSON')
    args = p.parse_args(argv)
    report = check(args.repo, max_silence_hours=args.max_silence_hours)
    print(issue_body(report) if args.body else json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
