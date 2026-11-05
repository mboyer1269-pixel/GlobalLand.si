"""Allowlisted, read-only projection of a single public Git revision."""
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import PurePosixPath
from urllib.parse import quote

GITHUB = 'https://github.com/mboyer1269-pixel/GlobalLand.si'
SHA = re.compile(r'[a-f0-9]{40}\Z')
TASK = re.compile(r'TASK-[0-9]{4,12}\Z')
AGENT = re.compile(r'[A-Z0-9_-]{1,64}\Z')
MISSION = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z')
PRODUCT = re.compile(r'products/(?:[A-Za-z0-9_-][A-Za-z0-9_.-]*/)*[A-Za-z0-9_-][A-Za-z0-9_.-]*\Z')
RESULT = re.compile(r'queue/(?:done|failed)/(TASK-[0-9]{4,12})\.result\.json\Z')
HISTORY_COMMITS = 150
RESULT_LIMIT = 100
MAX_JSON_BYTES = 1024 * 1024
STATES = {'OPEN': 'Ouverte', 'RUNNING': 'En cours', 'COMPLETED': 'Terminée', 'FAILED': 'En échec'}
CONTROLLER_STATES = {'OPERATIONAL': 'En activité', 'DEGRADED': 'Activité dégradée',
                     'STALE': 'Cycle en retard', 'CONTROLLER_BLOCKED': 'Contrôleur bloqué'}
TITLES = {'EXEC': 'Exécuter un travail', 'FETCH': 'Consulter une source publique',
          'create_mission': 'Ouvrir une mission', 'claim_mission': 'Prendre une mission',
          'complete_mission': 'Clore une mission', 'fail_mission': 'Signaler un échec',
          'message': 'Transmettre un message', 'review': 'Évaluer une réalisation',
          'record_lesson': 'Consigner une leçon', 'PUBLISH_SITE': 'Publier un site'}
KINDS = {'DONE': 'done', 'FAILED': 'failed', 'REJECTED': 'rejected',
         'TIMEOUT': 'timeout', 'INTERRUPTED': 'interrupted'}


def git(repo, *args, timeout=10):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, timeout=timeout,
                            env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'Never'})
    if result.returncode:
        raise RuntimeError('Lecture du dépôt indisponible.')
    return result.stdout


def blob(repo, revision, path):
    size = int(git(repo, 'cat-file', '-s', f'{revision}:{path}'))
    if size > MAX_JSON_BYTES:
        raise ValueError('Donnée de projection trop volumineuse.')
    return git(repo, 'show', f'{revision}:{path}')


def document(repo, revision, path):
    value = json.loads(blob(repo, revision, path))
    if not isinstance(value, dict):
        raise ValueError('Document de projection invalide.')
    return value


def text(value, limit=4096):
    if not isinstance(value, str):
        return ''
    return value if len(value) <= limit else value[:limit] + '…'


def timestamp(seconds):
    return datetime.fromtimestamp(int(seconds), timezone.utc).isoformat()


def source_url(revision, path):
    return f'{GITHUB}/blob/{revision}/{quote(path, safe="/")}'


def collection(repo, revision, overview, name):
    projection = overview.get('projection')
    if 'projection' not in overview:
        values = overview.get(name)
        if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
            raise ValueError('Collection invalide.')
        return values
    if not isinstance(projection, dict) or not re.fullmatch(r'[a-f0-9]{64}', str(projection.get('snapshot_sha256', ''))):
        raise ValueError('Version de page absente ou invalide.')
    info = projection.get('collections', {}).get(name)
    if not isinstance(info, dict):
        raise ValueError('Métadonnées de page absentes.')
    count, total = info.get('pages'), info.get('total')
    if type(count) is not int or not 1 <= count <= 128 or type(total) is not int or total < 0:
        raise ValueError('Nombre de pages invalide.')
    expected_path = 'world/pages/' + name + '-{page}.json'
    if info.get('path') != expected_path:
        raise ValueError('Chemin de page invalide.')
    values = []
    for i in range(count):
        page = document(repo, revision, expected_path.format(page=i))
        expected = dict(collection=name, page=i, total=total, pages=count,
                        next_page=i+1 if i+1 < count else None,
                        snapshot_sha256=projection.get('snapshot_sha256'))
        if any(page.get(key) != value for key, value in expected.items()) or not isinstance(page.get('items'), list):
            raise ValueError('Pages de projection incohérentes.')
        values.extend(page['items'])
    if len(values) != total or any(not isinstance(item, dict) for item in values):
        raise ValueError('Contenu de page incomplet.')
    return values


def result_publications(repo, revision):
    """Newest publication of each result in an explicitly bounded history window."""
    raw = git(repo, 'log', '--first-parent', '--diff-merges=first-parent', f'-{HISTORY_COMMITS}',
              '--format=%H%x09%ct', '--name-only', revision, '--', 'queue/done', 'queue/failed')
    found = {}; commit = date = None
    for line in raw.decode().splitlines():
        if re.fullmatch(r'[a-f0-9]{40}\t[0-9]+', line):
            commit, date = line.split('\t'); continue
        match = RESULT.fullmatch(line)
        if match and commit and match[1] not in found:
            found[match[1]] = (commit, date, line)
    return list(found.items())[:RESULT_LIMIT], len(found) > RESULT_LIMIT


def verified_request(repo, commit, result):
    ident = result['id']
    request = result.get('request')
    decision_url = None
    if isinstance(request, dict):
        raw = (json.dumps(request, ensure_ascii=False, sort_keys=True) + '\n').encode()
    else:
        parent = git(repo, 'rev-parse', commit+'^').decode().strip()
        path = f'queue/inbox/{ident}.json'
        raw = blob(repo, parent, path)
        request = json.loads(raw)
        decision_url = source_url(parent, path)
    if (not isinstance(request, dict) or request.get('id') != ident
            or request.get('type') != 'TOOL' or not isinstance(request.get('action'), str)
            or not isinstance(request.get('args'), dict)
            or (request.get('action') == 'WORLD' and not isinstance(request['args'].get('op'), str))
            or hashlib.sha256(raw).hexdigest() != result.get('input_sha256')):
        return None, None
    return request, decision_url


def task_fields(task, agents, missions):
    if not isinstance(task.get('action'), str) or not isinstance(task.get('args'), dict):
        raise ValueError('Demande invalide.')
    args = task.get('args') if isinstance(task.get('args'), dict) else {}
    actor = task.get('submitted_by')
    actor = actor if isinstance(actor, str) and AGENT.fullmatch(actor) else None
    if actor and actor not in agents:
        agents[actor] = dict(role='Contribution archivée', bio='Identité attribuée par une demande vérifiée.')
    mission = args.get('mission_id')
    mission = mission if isinstance(mission, str) and mission in missions else None
    action = args.get('op') if task.get('action') == 'WORLD' else task.get('action')
    if not isinstance(action, str):
        raise ValueError('Action invalide.')
    title = TITLES.get(action, 'Action publiée')
    if action == 'PUBLISH_SITE' and args.get('dry_run') is True:
        title = 'Vérifier une publication sans déployer'
    return dict(agent=actor, mission=mission, title=title,
                detail=text(task.get('description')) or title)


def snapshot(repo, revision=None):
    revision = revision or git(repo, 'rev-parse', 'refs/remotes/origin/main').decode().strip()
    if not SHA.fullmatch(revision):
        raise ValueError('Révision invalide.')
    world = document(repo, revision, 'world/status.json')
    if 'projection' not in world and git(repo, 'ls-tree', revision, '--', 'world/pages').strip():
        raise ValueError('Métadonnées de pagination absentes.')
    controller = document(repo, revision, 'world/controller.json')
    agents = {}; missions = {}; warnings = []
    for item in collection(repo, revision, world, 'agents'):
        ident = item.get('agent_id')
        if not isinstance(ident, str) or not AGENT.fullmatch(ident) or ident in agents:
            raise ValueError('Identité de résident invalide ou dupliquée.')
        agents[ident] = dict(role=text(item.get('role'), 128) or 'Contribution',
                             bio='Résident du monde · ' + text(item.get('status'), 64))
    for item in collection(repo, revision, world, 'missions'):
        ident = item.get('mission_id')
        if not isinstance(ident, str) or not MISSION.fullmatch(ident) or ident in missions:
            raise ValueError('Mission invalide ou dupliquée.')
        assigned = item.get('agent_id')
        missions[ident] = dict(title=ident, goal=text(item.get('goal')),
                              status=STATES.get(item.get('status'), 'État à vérifier'),
                              agents=[assigned] if isinstance(assigned, str) and assigned in agents else [])
    blockers = collection(repo, revision, world, 'blockers')
    for item in blockers:
        mission = item.get('mission_id')
        if isinstance(mission, str) and mission in missions and item.get('status') == 'OPEN':
            description = text(item.get('title')) + ' — ' + text(item.get('detail'))
            missions[mission]['blocker'] = (missions[mission].get('blocker', '') + '\n' + description).strip()
    events = []; artifacts = {}
    publications, limited = result_publications(repo, revision)
    for ident, (commit, date, path) in publications:
        try:
            result = document(repo, commit, path)
            if (result.get('id') != ident or not isinstance(result.get('status'), str)
                    or result['status'] not in KINDS):
                raise ValueError('Résultat invalide.')
        except (ValueError, RuntimeError):
            warnings.append('Résultat illisible : ' + ident); continue
        event = dict(id=ident, at=timestamp(date), kind=KINDS[result['status']], agent=None, mission=None,
                     title='Résultat publié', detail='Résultat disponible ; attribution non vérifiée.',
                     resultUrl=source_url(commit, path))
        try:
            request, decision_url = verified_request(repo, commit, result)
        except (ValueError, RuntimeError):
            request, decision_url = None, None
        if request:
            event.update(task_fields(request, agents, missions))
            if decision_url:
                event['decisionUrl'] = decision_url
            else:
                event['decisionUrl'] = event['resultUrl']
            paths = result.get('artifacts', [])
            paths = paths if isinstance(paths, list) else []
            if request.get('action') == 'FETCH' and isinstance(request.get('args'), dict):
                paths = [request['args'].get('output'), *paths]
            event['artifacts'] = []
            for output in dict.fromkeys(p for p in paths if isinstance(p, str)):
                if result['status'] != 'DONE' or not PRODUCT.fullmatch(output) or output.startswith('products/receipts/'):
                    continue
                try:
                    entry = git(repo, 'ls-tree', commit, '--', output).decode().split('\t', 1)
                    if len(entry) != 2 or entry[0].split()[:2] not in (['100644', 'blob'], ['100755', 'blob']):
                        raise RuntimeError('Le livrable n’est pas un fichier ordinaire.')
                except RuntimeError:
                    warnings.append('Livrable introuvable : ' + ident); continue
                aid = ident + '-' + str(len(event['artifacts']))
                artifacts[aid] = dict(title=PurePosixPath(output).name, event=ident,
                                      sourceUrl=source_url(commit, output))
                event['artifacts'].append(aid)
            if event['artifacts']:
                event['artifact'] = event['artifacts'][0]
        events.append(event)
    completed = {event['id'] for event in events}
    pending = git(repo, 'ls-tree', '-r', '--name-only', revision, '--', 'queue/inbox').decode().splitlines()
    valid_pending = [path for path in pending if re.fullmatch(r'queue/inbox/TASK-[0-9]{4,12}\.json', path)]
    for path in valid_pending[:RESULT_LIMIT]:
        ident = PurePosixPath(path).stem
        if ident in completed:
            continue
        try:
            task = document(repo, revision, path)
            if task.get('id') != ident:
                raise ValueError('Demande invalide.')
            planned_at = git(repo, 'log', '-1', '--format=%ct', revision, '--', path).decode().strip()
            event = dict(id=ident, at=timestamp(planned_at), kind='planned', decisionUrl=source_url(revision, path),
                         **task_fields(task, agents, missions))
            events.append(event)
            if event['agent']:
                agents[event['agent']].setdefault('next', ident)
        except (RuntimeError, ValueError):
            warnings.append('Demande illisible : ' + ident)
    events.sort(key=lambda event: (event['at'], event['id']), reverse=True)
    for event in events:
        if event['mission'] and event['agent'] and event['agent'] not in missions[event['mission']]['agents']:
            missions[event['mission']]['agents'].append(event['agent'])
    journey = next((dict(agent=e['agent'], mission=e['mission'], artifact=e['artifact']) for e in events
                    if e['agent'] and e['mission'] and e.get('artifact')), None)
    return dict(revision=revision, publishedAt=timestamp(git(repo, 'show', '-s', '--format=%ct', revision)),
                controller=CONTROLLER_STATES.get(controller.get('state'), 'État à vérifier'),
                agents=agents, missions=missions, events=events, artifacts=artifacts, journey=journey,
                coverage=dict(world_complete=True, history_commit_limit=HISTORY_COMMITS, result_limit=RESULT_LIMIT,
                              result_count=len(publications), results_limited=limited,
                              pending_limited=len(valid_pending) > RESULT_LIMIT, warnings=warnings))
