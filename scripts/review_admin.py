#!/usr/bin/env python3
"""Founder approval of an Apify listing (the second key held by a human).

Use when only one AI provider is configured, or to overrule a stalled review:
  sudo python3 /opt/globalland/control/review_admin.py approve --actor NAME --digest REVIEW_DIGEST --notes "checked"
  sudo python3 /opt/globalland/control/review_admin.py approve --site NAME --digest REVIEW_DIGEST
The review_digest comes from the private build result or the site dry_run (queue/done/<TASK>.result.json).
Recorded with host_provider FOUNDER; agents cannot forge it (host_* fields are
stripped from their requests).
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import sys

from world import World


def approve(world, name, digest, notes=None, verdict='APPROVE', now=None, kind='actor'):
    stamp = (now or datetime.datetime.now(datetime.timezone.utc)).strftime('%Y%m%dT%H%M%SZ')
    if kind not in ('actor', 'site') or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', name or ''):
        raise ValueError('invalid subject')
    args = dict(op='review', reviewer='FOUNDER', subject='%s:%s' % (kind, name), digest=digest, verdict=verdict,
                notes=notes, host_turn='FOUNDER-' + stamp, host_provider='FOUNDER')
    return world.apply('FOUNDER-REVIEW-%s-%s-%s' % (kind, name, stamp), args)


def main(argv=None, root='/opt/globalland', euid=os.geteuid):
    p = argparse.ArgumentParser(description='Founder review of an Apify listing')
    p.add_argument('verdict', choices=['approve', 'reject'])
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument('--actor')
    target.add_argument('--site')
    p.add_argument('--digest', required=True)
    p.add_argument('--notes')
    args = p.parse_args(argv)
    if euid() != 0:
        raise ValueError('administrator required')
    world = World(pathlib.Path(root) / 'state' / 'private' / 'world.sqlite3')
    kind, name = ('actor', args.actor) if args.actor else ('site', args.site)
    review = approve(world, name, args.digest, args.notes, 'APPROVE' if args.verdict == 'approve' else 'NEEDS_WORK', kind=kind)
    print(json.dumps(review, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Review refused: ' + str(error), file=sys.stderr)
        sys.exit(1)
