#!/usr/bin/env python3
"""Dead man's switch for GlobalLand, run by GitHub Actions (independent of the VPS).

The world can stop silently: a blocked controller publishes one READINESS
commit and then nothing, because identical states produce no commit. On
2026-11-01 the world stayed blocked for hours without anyone noticing.

This script reads the checked-out main branch and reports ALERT when:
- the supervisor has not committed for more than --max-silence-hours;
- world/controller.json is absent/invalid or not OPERATIONAL;
- no recent successful plan is evidenced, independently of Git publications;
- world/blockers.json has open actions for the founder.

Output: one JSON object on stdout. The workflow opens, updates or closes a
GitHub issue from it, so the founder gets an e-mail. No secret is read.
"""
import argparse
import datetime
import json
import pathlib
import subprocess
import sys
import time

SUPERVISOR = 'globalland-supervisor'


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
    controller = read_json(repo, 'world/controller.json')
    if not isinstance(controller, dict) or not controller:
        reasons.append('Statut du contrôleur absent, illisible ou invalide : world/controller.json.')
        controller = {}
    state = controller.get('state')
    if state != 'OPERATIONAL':
        reasons.append('Contrôleur dans l\'état %s : %s' % (state, controller.get('reason_code') or controller.get('reason') or 'voir world/controller.json'))
    # Publication is a heartbeat, not evidence that a model produced a valid plan.
    # This timestamp deliberately does not claim successful task execution/revenue.
    success = controller.get('last_successful_plan') or controller.get('last_turn')
    success_age = None
    success_at = None
    if isinstance(success, dict) and success.get('state') == 'DECISION_READY':
        try:
            success_at = success['at']
            at = datetime.datetime.strptime(success_at, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).timestamp()
            success_age = (now - at) / 3600
        except (KeyError, TypeError, ValueError, OverflowError):
            success_at = None
    if success_age is None:
        reasons.append('Aucune date valide de dernier plan réussi du contrôleur.')
    elif success_age < 0:
        reasons.append('La date du dernier plan réussi est dans le futur ; vérifier les horloges.')
    elif success_age > max_silence_hours:
        reasons.append('Aucun plan réussi du contrôleur depuis %.1f h (seuil %.1f h).' % (success_age, max_silence_hours))
    blockers = read_json(repo, 'world/blockers.json') or {}
    founder = [c for c in blockers.get('open', []) if c.get('owner') == 'FOUNDER']
    if founder:
        reasons.append('%d action(s) attendent le fondateur : %s' % (len(founder), '; '.join(c.get('title', c.get('id', '?')) for c in founder[:5])))
    return dict(status='ALERT' if reasons else 'OK', reasons=reasons, last_supervisor_commit_age_hours=age_hours,
                controller_state=state, founder_actions=len(founder), last_successful_plan_at=success_at,
                last_successful_plan_age_hours=None if success_age is None else round(success_age, 2))


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
