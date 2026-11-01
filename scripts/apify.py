"""Apify Store publication: the first revenue rail (pay-per-event Actors).

Agents write an Actor under products/actors/<name>/ and ask PUBLISH_ACTOR.
The installed host control, never the agents' sandbox, holds the API token
(/opt/globalland/credentials/apify/token, mode 600) and talks to
https://api.apify.com. Every publication is journaled under
state/apify/<actor>-<source digest>.json before the first external call and
resumed from its last completed step: a crash or a later task with the same
source never creates a second Actor or a second build. Listing and pricing
are applied by an idempotent final update from the current request.

Limits enforced here, not by the agents:
- only text files under the Actor directory, bounded in count and size,
  secret-scanned; `actor-config/` is published as Apify's `.actor/` folder
  (dot directories cannot live in products/);
- the README must state that the Actor is built and maintained by autonomous
  AI agents (GlobalLand transparency rule);
- pay-per-event prices in integer micro-USD, capped by `apify.max_event_price_usd`;
- a Store listing only after a successful build, and only if the founder
  allowed public listings (`apify.allow_public`).

Revenue shown by ACTOR_STATS is an estimate from charged events. Only a
verified Apify payout credits the bank.
"""
import hashlib
import json
import pathlib
import re
import time
import urllib.error
import urllib.request

from supervisor import atomic_json, check_secrets

API = 'https://api.apify.com'
NAME = re.compile(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?')
EVENT = re.compile(r'[a-z0-9][a-z0-9-]{0,39}')
VERSION = re.compile(r'(?:[0-9]|[1-9][0-9])\.(?:[0-9]|[1-9][0-9])')
CONFIG_DIR = 'actor-config'
MAX_FILES, MAX_FILE, MAX_TOTAL = 100, 512 * 1024, 2 * 1024 * 1024
DISCLOSURE = re.compile(r'autonomous\s+AI\s+agents?|agents?\s+IA\s+autonomes?', re.I)


class ApifyError(ValueError):
    """A refusal or remote failure whose message is safe to return to agents.

    Messages are built only from code literals, validated names and HTTP
    status codes, never from response bodies or the token."""
    safe_message = True


def settings(config):
    c = config.get('apify') or {}
    if not isinstance(c, dict) or c.get('enabled') is not True:
        return None
    cap = c.get('max_event_price_usd', 0.05)
    floor = c.get('min_event_price_usd', 0.0005)
    wait = c.get('build_wait_seconds', 240)
    if (type(cap) not in (int, float) or not 0 < cap <= 10 or type(floor) not in (int, float) or not 0 < floor <= cap
            or type(wait) is not int or not 60 <= wait <= 600):
        raise ValueError('invalid apify configuration')
    # The floor exists because a lone seller agent gives discounts too easily
    # (Anthropic Project Vend) and an event priced under Apify's platform cost
    # loses money on every run.
    return dict(max_price_micro=int(round(cap * 1_000_000)), min_price_micro=int(round(floor * 1_000_000)),
                allow_public=c.get('allow_public') is True,
                build_wait_seconds=wait, require_review=c.get('require_review', True) is not False)


def review_digest(source_digest, args):
    """What a reviewer approves: the exact code AND the listing it will carry."""
    listing = {'source': source_digest, 'title': args.get('title'), 'description': args.get('description'),
               'events': args.get('events') or []}
    return hashlib.sha256(json.dumps(listing, sort_keys=True).encode()).hexdigest()


def approved_by_other(reviews, actor, digest, author, origin=None):
    return approved(reviews, 'actor:' + actor, digest, author, origin)


def approved(reviews, subject, digest, author, origin=None):
    """Two-key rule with host-bound identities.

    The latest review of this exact listing must be an APPROVE whose provenance
    was recorded by the host (not chosen by the brain) and differs from the
    publishing request: another provider in another turn, an external principal
    (e.g. Grok through GitHub) or the founder. Agent names alone prove nothing:
    one brain can type any of them."""
    relevant = [r for r in reviews or [] if r.get('subject') == subject and r.get('digest') == digest]
    if not relevant:
        return False
    latest = max(relevant, key=lambda r: (r.get('at') or 0, r.get('seq') or 0))
    if latest.get('verdict') != 'APPROVE' or latest.get('reviewer') == author:
        return False
    turn, provider = origin or (None, None)
    if latest.get('host_provider') == 'FOUNDER':
        return True
    if not latest.get('host_provider') or not latest.get('host_turn'):
        return False
    return latest['host_provider'] != provider and latest['host_turn'] != turn


def read_token(root):
    path = pathlib.Path(root) / 'credentials' / 'apify' / 'token'
    if not path.is_file() or path.is_symlink():
        raise ApifyError('No Apify integration configured; the founder must install an API token')
    if path.stat().st_mode & 0o077:
        raise ApifyError('Apify token file must be readable by its owner only')
    token = path.read_text().strip()
    if not token or len(token) > 512 or any(ch.isspace() for ch in token):
        raise ApifyError('Apify token file is invalid')
    return token


def load_source(work, actor):
    """Actor files as Apify sourceFiles, with the digest of their exact content."""
    if not isinstance(actor, str) or not NAME.fullmatch(actor):
        raise ApifyError('Invalid actor name: lowercase letters, digits and hyphens')
    base = pathlib.Path(work) / 'products' / 'actors' / actor
    if base.is_symlink() or not base.is_dir():
        raise ApifyError('Actor source not found under products/actors/' + actor)
    files, total = [], 0
    for path in sorted(base.rglob('*')):
        if path.is_symlink():
            raise ApifyError('symlinked actor file refused')
        if not path.is_file():
            continue
        rel = path.relative_to(base).as_posix()
        if 'receipts' in rel.split('/'):
            continue
        raw = path.read_bytes()
        total += len(raw)
        if len(files) >= MAX_FILES or len(raw) > MAX_FILE or total > MAX_TOTAL:
            raise ApifyError('Actor source too large (100 files, 512 KiB each, 2 MiB total)')
        check_secrets(raw)
        try:
            content = raw.decode('utf-8')
        except UnicodeDecodeError:
            raise ApifyError('Actor files must be UTF-8 text') from None
        name = '.actor/' + rel[len(CONFIG_DIR) + 1:] if rel.startswith(CONFIG_DIR + '/') else rel
        files.append({'name': name, 'format': 'TEXT', 'content': content})
    by_name = {f['name']: f['content'] for f in files}
    for required in ('.actor/actor.json', 'Dockerfile', 'README.md'):
        if required not in by_name:
            raise ApifyError('Actor source must contain ' + (CONFIG_DIR + '/actor.json' if required.startswith('.actor') else required))
    try:
        definition = json.loads(by_name['.actor/actor.json'])
    except ValueError:
        raise ApifyError('actor-config/actor.json must be valid JSON') from None
    if not isinstance(definition, dict) or definition.get('actorSpecification') != 1 or definition.get('name') != actor:
        raise ApifyError('actor.json needs actorSpecification 1 and name equal to the actor')
    version = definition.get('version', '0.0')
    if not isinstance(version, str) or not VERSION.fullmatch(version):
        raise ApifyError('actor.json version must be MAJOR.MINOR')
    if not DISCLOSURE.search(by_name['README.md']):
        raise ApifyError('README.md must state that the Actor is built and maintained by autonomous AI agents')
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return files, version, digest


def pricing(events, max_price_micro, min_price_micro=1):
    """Pay-per-event pricing records; an empty list keeps the Actor free."""
    if not events:
        return []
    if not isinstance(events, list) or len(events) > 5:
        raise ApifyError('At most 5 chargeable events')
    charge, seen = {}, set()
    for event in events:
        name, price = event.get('name'), event.get('price_microusd')
        if not isinstance(name, str) or not EVENT.fullmatch(name) or name in seen:
            raise ApifyError('Invalid or duplicate event name')
        if type(price) is not int or not min_price_micro <= price <= max_price_micro:
            raise ApifyError('Event price outside the host range (configured floor to configured cap, in micro-USD)')
        seen.add(name)
        charge[name] = {'eventTitle': event['title'], 'eventDescription': event['description'],
                        'eventPriceUsd': price / 1_000_000}
    first = events[0]['name']
    charge[first]['isPrimaryEvent'] = True
    return [{'pricingModel': 'PAY_PER_EVENT', 'pricingPerEvent': {'actorChargeEvents': charge}}]


class Client:
    """Minimal Apify REST client. The token never leaves this object."""

    def __init__(self, token, transport=None):
        self._token = token
        self.transport = transport or self._urllib

    def _urllib(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(API + path, data=data, method=method, headers={
            'Authorization': 'Bearer ' + self._token, 'Content-Type': 'application/json',
            'User-Agent': 'GlobalLand/3 host publisher'})
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                raw = response.read(8 * 1024 * 1024)
                return response.status, (json.loads(raw) if raw and raw[:1] in b'{[' else raw.decode('utf-8', 'replace'))
        except urllib.error.HTTPError as error:
            return error.code, None

    def call(self, method, path, body=None, ok=(200, 201)):
        status, value = self.transport(method, path, body)
        if status not in ok:
            raise ApifyError('Apify API %s %s returned HTTP %d' % (method, path.split('?')[0], status))
        return value.get('data', value) if isinstance(value, dict) else value


class Publisher:
    def __init__(self, root, config, client=None, sleep=time.sleep, reviews=None, origin=None):
        self.root = pathlib.Path(root)
        self.settings = settings(config)
        self.client = client
        self.sleep = sleep
        self.reviews = reviews or []
        self.origin = origin

    def _client(self):
        if self.settings is None:
            raise ApifyError('Apify integration not enabled by the founder')
        if self.client is None:
            self.client = Client(read_token(self.root))
        return self.client

    def _journal(self, actor, digest):
        path = self.root / 'state' / 'apify' / ('%s-%s.json' % (actor, digest[:24]))
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        return path

    def publish(self, task):
        args = task['args']
        api = self._client()
        files, version, digest = load_source(self.root / 'work', args['actor'])
        prices = pricing(args.get('events'), self.settings['max_price_micro'], self.settings['min_price_micro'])
        want_public = args.get('public') is True
        if want_public and not self.settings['allow_public']:
            raise ApifyError('Public Store listing not allowed by the founder yet; publish privately first')
        listing = review_digest(digest, args)
        if want_public and self.settings['require_review'] and not approved_by_other(self.reviews, args['actor'], listing, task.get('submitted_by'), self.origin):
            raise ApifyError('Public listing needs a WORLD review APPROVE of actor:%s for the review_digest returned by the private build with the same title, description and events, recorded in another turn by another provider, by Grok through GitHub or by the founder'
                             % args['actor'])
        path = self._journal(args['actor'], digest)
        record = json.loads(path.read_text()) if path.exists() else None
        if record and record['step'] == 'BUILD_FAILED':
            return dict(record['result'], note='This exact source already failed to build; change it before publishing again.')
        if record is None:
            record = dict(actor=args['actor'], digest=digest, version=version, step='STARTED', tasks=[])
        record['tasks'] = (record.get('tasks') or []) + [task['id']]
        atomic_json(path, record)  # recorded before any external call

        if 'actor_id' not in record:
            user = api.call('GET', '/v2/users/me')
            username = user.get('username')
            if not isinstance(username, str) or not username:
                raise ApifyError('Apify account has no username; set one in the Apify console')
            definition = self._definition(args, files, version, public=False)
            status, existing = api.transport('GET', '/v2/acts/%s~%s' % (username, args['actor']))
            if status == 200 and isinstance(existing, dict):
                actor_id = existing.get('data', existing)['id']
                api.call('PUT', '/v2/acts/' + actor_id, definition)
            elif status == 404:
                actor_id = api.call('POST', '/v2/acts', definition)['id']
            else:
                raise ApifyError('Apify API GET actor returned HTTP %d' % status)
            record.update(actor_id=actor_id, username=username, step='SOURCE_UPLOADED')
            atomic_json(path, record)

        if record['step'] in ('BUILT', 'DONE'):
            status = 'SUCCEEDED'
        elif 'build_id' not in record:
            build = api.call('POST', '/v2/acts/%s/builds?version=%s&tag=latest&waitForFinish=60' % (record['actor_id'], record['version']))
            record.update(build_id=build['id'], step='BUILDING')
            atomic_json(path, record)
            status = build.get('status')
        else:
            status = None  # resume polling the recorded build, never rebuild
        deadline = time.monotonic() + self.settings['build_wait_seconds']
        while status not in ('SUCCEEDED', 'FAILED', 'TIMED-OUT', 'ABORTED'):
            if time.monotonic() > deadline:
                return dict(status='PENDING', actor_id=record['actor_id'], build_id=record['build_id'],
                            note='Build still running; publish the same source again later to resume without rebuilding.')
            status = api.call('GET', '/v2/actor-builds/%s?waitForFinish=60' % record['build_id']).get('status')
        if status != 'SUCCEEDED':
            log = api.call('GET', '/v2/logs/' + record['build_id'])
            tail = log[-4000:] if isinstance(log, str) else ''
            try:
                check_secrets(tail.encode())
            except ValueError:
                tail = '[build log withheld: secret pattern detected]'
            result = dict(status='BUILD_FAILED', actor_id=record['actor_id'], build_id=record['build_id'],
                          build_status=status, log_tail=tail)
            record.update(step='BUILD_FAILED', result=result)
            atomic_json(path, record)
            return result

        if record['step'] != 'DONE':
            record['step'] = 'BUILT'
            atomic_json(path, record)
        definition = self._definition(args, files, record['version'], public=want_public)
        if prices:
            definition['pricingInfos'] = prices
        api.call('PUT', '/v2/acts/' + record['actor_id'], definition)
        result = dict(status='PUBLISHED' if want_public else 'PRIVATE_BUILD_READY', actor_id=record['actor_id'],
                      source_digest=digest, review_digest=listing,
                      build_id=record['build_id'], public=want_public,
                      store_url='https://apify.com/%s/%s' % (record['username'], record['actor']) if want_public else None,
                      events={e['name']: e['price_microusd'] for e in args.get('events') or []},
                      note='Price increases and new paid events take effect after a 14-day notice once the Actor has paying users.')
        record.update(step='DONE', result=result)
        atomic_json(path, record)
        return result

    @staticmethod
    def task_status(result):
        """Map a publication result onto the queue's task statuses."""
        return {'PUBLISHED': 'DONE', 'PRIVATE_BUILD_READY': 'DONE', 'PENDING': 'TIMEOUT'}.get(result.get('status'), 'FAILED')

    @staticmethod
    def _definition(args, files, version, public):
        return {'name': args['actor'], 'title': args['title'], 'description': args['description'],
                'isPublic': public,
                'versions': [{'versionNumber': version, 'sourceType': 'SOURCE_FILES', 'buildTag': 'latest',
                              'sourceFiles': files}]}

    def stats(self, task):
        """Observed usage and an ESTIMATE of gross event charges (not settled revenue)."""
        api = self._client()
        actor = task['args']['actor']
        if not NAME.fullmatch(actor):
            raise ApifyError('Invalid actor name: lowercase letters, digits and hyphens')
        user = api.call('GET', '/v2/users/me')
        info = api.call('GET', '/v2/acts/%s~%s' % (user['username'], actor))
        runs = api.call('GET', '/v2/acts/%s/runs?desc=1&limit=100' % info['id'])
        items = runs.get('items', []) if isinstance(runs, dict) else []
        prices = {}
        for record in info.get('pricingInfos') or []:
            for name, event in ((record.get('pricingPerEvent') or {}).get('actorChargeEvents') or {}).items():
                if isinstance(event.get('eventPriceUsd'), (int, float)):
                    prices[name] = event['eventPriceUsd']
        events, estimate = {}, 0.0
        for run in items:
            for name, count in (run.get('chargedEventCounts') or {}).items():
                if isinstance(count, int):
                    events[name] = events.get(name, 0) + count
                    estimate += count * prices.get(name, 0)
        return dict(actor=actor, is_public=info.get('isPublic'), stats=info.get('stats'),
                    recent_runs=len(items), recent_succeeded=sum(1 for r in items if r.get('status') == 'SUCCEEDED'),
                    charged_events=events, gross_charges_estimate_usd=round(estimate, 6),
                    note='Not revenue: estimate of gross charges before Apify commission (20%) and platform costs; only a verified payout credits the bank.')
