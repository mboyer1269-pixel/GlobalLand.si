let agents = {};
let missions = {};
let events = [];
let artifacts = {};

const labels = { planned: 'Annoncée', done: 'Réussie', failed: 'En échec', rejected: 'Refusée', timeout: 'Délai dépassé', interrupted: 'Interrompue' };
const panel = document.querySelector('#panel');
let filter = 'all';
let lastPlace = '';
let live = null;
const eventClock = new Intl.DateTimeFormat('fr-CA', {
  timeZone: 'America/Toronto', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
});

function escapeText(value) {
  return String(value).replace(/[&<>"']/g, symbol => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[symbol]);
}

function allEvents() {
  return events;
}

function dateLabel(value) {
  return value && Number.isFinite(Date.parse(value)) ? eventClock.format(new Date(value)) : 'Heure inconnue';
}

function eventTime(event) {
  return dateLabel(event.at);
}

function sourceLink(url, label) {
  if (typeof url !== 'string' || !/^https:\/\/github\.com\/mboyer1269-pixel\/GlobalLand\.si\/blob\/[a-f0-9]{40}\//.test(url)) return '';
  return `<p class="note"><a class="text-link" href="${escapeText(url)}" target="_blank" rel="noopener noreferrer">${escapeText(label)} ↗</a></p>`;
}

function link(route, label) {
  return `<a class="text-link" href="#${escapeText(route)}">${escapeText(label)}</a>`;
}

function card(route, title, description) {
  return `<li><a href="#${escapeText(route)}"><span><b>${escapeText(title)}</b><small>${escapeText(description)}</small></span><span class="arrow" aria-hidden="true">↗</span></a></li>`;
}

function cards(items) {
  if (!items.length) return '<p class="note">Aucun élément dans cet instantané.</p>';
  return `<ul class="cards">${items.join('')}</ul>`;
}

function timeline(items) {
  if (!items.length) return '<p class="note">Aucun événement pour ce filtre. Choisis « Tout » pour revoir le journal complet.</p>';
  return `<ol class="timeline">${items.map(event => `<li data-kind="${event.kind}">
    <div class="event-meta"><time>${escapeText(eventTime(event))}</time><span class="pill ${event.kind}">${labels[event.kind]}</span></div>
    <a class="event-title" href="#tache-${event.id}">${escapeText(event.title)}</a>
    <p class="event-by">${escapeText(event.agent ?? 'Agent non attribué')}</p>
  </li>`).join('')}</ol>`;
}

function section(label) {
  return `<h3 class="section-label">${escapeText(label)}</h3>`;
}

function view(title, area, description, body, back) {
  panel.innerHTML = `<div class="panel-head"><div class="panel-top"><p class="eyebrow">${escapeText(area)}</p>${back ? link(back[0], back[1]) : ''}</div>
    <h2 id="panel-title" tabindex="-1">${escapeText(title)}</h2><p class="panel-desc">${escapeText(description)}</p></div>
    <div class="panel-body">${body}</div>`;
}

function showJournal() {
  const filters = { all: 'Tout', ...labels };
  const options = Object.entries(filters).map(([id, label]) => `<option value="${id}"${id === filter ? ' selected' : ''}>${label}</option>`);
  const items = allEvents().filter(event => filter === 'all' || event.kind === filter);
  const scope = live
    ? `${live.coverage.result_count} résultats dans une fenêtre de ${live.coverage.history_commit_limit} publications. Les missions proviennent des pages complètes.`
    : 'Aucune activité affichée avant la lecture du dépôt.';
  const warnings = live?.coverage.warnings || [];
  view('Journal de la ville', 'PUBLICATIONS · HEURE DU QUÉBEC', scope,
    (warnings.length ? `<p class="evidence">${escapeText(warnings.length)} source(s) illisible(s). Les autres résultats restent disponibles.</p>` : '') +
    `<label class="filter" for="journal-filter">Afficher <select id="journal-filter">${options.join('')}</select></label><div id="timeline">${timeline(items)}</div>`);
  panel.querySelector('#journal-filter').addEventListener('change', event => {
    filter = event.target.value;
    panel.querySelector('#timeline').innerHTML = timeline(allEvents().filter(item => filter === 'all' || item.kind === filter));
  });
}

function showAgent(id) {
  const agent = agents[id];
  const assigned = Object.entries(missions).filter(([, mission]) => mission.agents.includes(id));
  const next = agent.next ? events.find(event => event.id === agent.next) : null;
  const history = allEvents().filter(event => event.agent === id);
  view(id, `PLACE DES AGENTS · ${agent.role.toUpperCase()}`, agent.bio,
    section('Missions') + (assigned.length ? cards(assigned.map(([key, mission]) => card(`mission-${key}`, mission.title, mission.status)))
      : '<p class="note">Aucune mission attribuée dans cet instantané.</p>') +
    section('Plan de match') + `<p class="note">${next ? `${escapeText(eventTime(next))} · ${link(`tache-${next.id}`, next.title)}` : 'Aucune prochaine action annoncée dans cet instantané.'}</p>` +
    section('Activité publiée') + timeline(history), ['agents', 'Tous les agents']);
}

function showMission(id) {
  const mission = missions[id];
  const related = allEvents().filter(event => event.mission === id);
  view(mission.title, `MAISON DES MISSIONS · ${mission.status.toUpperCase()}`, mission.goal,
    (mission.blocker ? `<p class="evidence">${escapeText(mission.blocker)}</p>` : '') +
    section('Contributions') + cards(mission.agents.map(agent => card(`agent-${agent}`, agent, agents[agent].role))) +
    section('Décisions et résultats') + timeline(related), ['missions', 'Toutes les missions']);
}

function showEvent(event) {
  const agent = event.agent ? link(`agent-${event.agent}`, event.agent) : 'Agent non attribué';
  const mission = event.mission ? `<p class="note">Mission · ${link(`mission-${event.mission}`, missions[event.mission].title)}</p>`
    : '<p class="note">Aucune mission attribuable dans cet instantané.</p>';
  const evidence = event.artifacts?.length ? section('Livrables') + cards(event.artifacts.map(id => card(`preuve-${id}`, artifacts[id].title, 'Ouvrir la preuve'))) : '';
  view(event.title, `${eventTime(event)} · ${labels[event.kind].toUpperCase()}`, event.detail,
    `<p class="note">Agent · ${agent}</p>${mission}${evidence}` +
    sourceLink(event.decisionUrl, 'Voir la demande vérifiée') + sourceLink(event.resultUrl, 'Voir le résultat publié'), ['journal', 'Journal']);
}

function showArtifact(id) {
  const artifact = artifacts[id];
  const event = allEvents().find(item => item.id === artifact.event);
  const agent = event.agent ? link(`agent-${event.agent}`, event.agent) : 'Agent non attribué';
  view(artifact.title, 'ATELIER DES LIVRABLES', `Publication du ${eventTime(event)}.`,
    `<p class="note">Agent · ${agent}</p><p class="note">Tâche · ${link(`tache-${event.id}`, event.title)}</p>` +
    section('Preuve publiée') + sourceLink(artifact.sourceUrl, 'Ouvrir cette version du fichier'), ['livrables', 'Tous les livrables']);
}

function setCurrent(element, active, token = 'location') {
  if (active) element.setAttribute('aria-current', token);
  else element.removeAttribute('aria-current');
}

function render(moveFocus = false) {
  const route = location.hash.slice(1) || 'carte';
  const agent = Object.keys(agents).find(id => route === `agent-${id}`);
  const mission = Object.keys(missions).find(id => route === `mission-${id}`);
  const event = allEvents().find(item => route === `tache-${item.id}`);
  const artifact = Object.keys(artifacts).find(id => route === `preuve-${id}`);
  if (route === 'agents' || agent) lastPlace = 'agents';
  if (route === 'missions' || mission) lastPlace = 'missions';
  if (route === 'livrables' || artifact) lastPlace = 'livrables';

  if (agent) showAgent(agent);
  else if (mission) showMission(mission);
  else if (event) showEvent(event);
  else if (artifact) showArtifact(artifact);
  else if (route === 'agents') {
    view('Place des agents', 'LIEU A', 'Choisis un agent pour suivre son travail.',
      cards(Object.entries(agents).map(([id, item]) => card(`agent-${id}`, id, item.role))), ['carte', 'Retour à la carte']);
  } else if (route === 'missions') {
    view('Maison des missions', 'LIEU M', 'Retrouve les objectifs, leurs contributions et leurs blocages.',
      cards(Object.entries(missions).map(([id, item]) => card(`mission-${id}`, item.title, item.status))), ['carte', 'Retour à la carte']);
  } else if (route === 'livrables') {
    view('Atelier des livrables', 'LIEU L', 'Ouvre une preuve et remonte jusqu’à la tâche qui l’a produite.',
      cards(Object.entries(artifacts).map(([id, item]) => card(`preuve-${id}`, item.title, events.find(event => event.id === item.event)?.agent ?? 'Agent non attribué'))), ['carte', 'Retour à la carte']);
  } else showJournal();

  document.querySelectorAll('[data-place]').forEach(item => setCurrent(item, item.dataset.place === lastPlace));
  document.querySelectorAll('#journey a').forEach(item => setCurrent(item, item.hash === `#${route}`, 'step'));
  setCurrent(document.querySelector('#nav-map'), route === 'carte', 'page');
  setCurrent(document.querySelector('#nav-journal'), route === 'journal' || Boolean(event), 'page');
  if (moveFocus) {
    panel.scrollTop = 0;
    const map = document.querySelector('.map-card');
    const target = route === 'carte' ? map : document.querySelector('#panel-title');
    target.focus({ preventScroll: true });
    if (matchMedia('(max-width: 840px)').matches) {
      (route === 'carte' ? map : panel).scrollIntoView({ block: 'start' });
    }
  }
}

window.addEventListener('hashchange', () => render(true));
document.querySelector('#journey-toggle').addEventListener('click', event => {
  const toggle = event.currentTarget;
  const show = toggle.getAttribute('aria-pressed') === 'false';
  toggle.setAttribute('aria-pressed', String(show));
  document.querySelector('#journey').hidden = !show;
  document.querySelector('.map-canvas').classList.toggle('journey-active', show);
  document.querySelector('#announcement').textContent = show ? 'Itinéraire affiché : agent, mission et résultat publié.' : 'Itinéraire masqué.';
});
render();

function displaySnapshot(data) {
  const record = value => value && typeof value === 'object' && !Array.isArray(value);
  if (!data || !/^[a-f0-9]{40}$/.test(data.revision) || !Array.isArray(data.events)
      || !record(data.agents) || !record(data.missions) || !record(data.artifacts) || !record(data.coverage)
      || typeof data.controller !== 'string' || !Number.isFinite(Date.parse(data.publishedAt))) {
    throw new Error('Instantané invalide');
  }
  const ids = new Set(data.events.map(event => event?.id));
  if (ids.size !== data.events.length
      || !Number.isInteger(data.coverage.result_count) || !Number.isInteger(data.coverage.history_commit_limit)
      || !Array.isArray(data.coverage.warnings)
      || Object.values(data.agents).some(agent => !record(agent) || typeof agent.role !== 'string' || typeof agent.bio !== 'string')
      || Object.values(data.missions).some(mission => !record(mission) || typeof mission.title !== 'string'
        || typeof mission.goal !== 'string' || typeof mission.status !== 'string' || !Array.isArray(mission.agents)
        || mission.agents.some(id => !Object.hasOwn(data.agents, id)))
      || data.events.some(event => !record(event) || !/^TASK-[0-9]{4,12}$/.test(event.id)
        || !Object.hasOwn(labels, event.kind) || !Number.isFinite(Date.parse(event.at))
        || typeof event.title !== 'string' || typeof event.detail !== 'string'
        || (event.agent !== null && !Object.hasOwn(data.agents, event.agent))
        || (event.mission !== null && !Object.hasOwn(data.missions, event.mission))
        || (event.artifacts !== undefined && (!Array.isArray(event.artifacts) || event.artifacts.some(id => !Object.hasOwn(data.artifacts, id)))))
      || Object.values(data.artifacts).some(item => !record(item) || !ids.has(item.event)
        || typeof item.title !== 'string' || typeof item.sourceUrl !== 'string')) {
    throw new Error('Contenu de l’instantané invalide');
  }
  if (data.journey && (!data.agents[data.journey.agent] || !data.missions[data.journey.mission] || !data.artifacts[data.journey.artifact])) {
    throw new Error('Itinéraire invalide');
  }
  const changed = live?.revision !== data.revision;
  const focused = document.activeElement;
  const focusWithin = focused?.closest('#panel, #journey');
  const focusKey = focused?.id || focused?.getAttribute('href');
  live = data;
  document.querySelector('#data-mode').textContent = 'Données publiées · Lecture seule';
  document.querySelector('#footer-mode').textContent = data.sourceMode === 'cached' ? 'Copie Git locale' : 'Suivi du dépôt';
  document.querySelector('#demo-time').textContent = data.stale
    ? `Actualisation indisponible. Dernière publication lue : ${dateLabel(data.publishedAt)}.`
    : `Révision ${data.revision.slice(0, 7)} · Vérification ${dateLabel(data.checkedAt)} · Publication ${dateLabel(data.publishedAt)}.`;
  document.querySelector('#world-state').textContent = data.controller;
  document.querySelector('#world-dot').classList.toggle('attention', data.stale || data.controller !== 'En activité');
  document.querySelector('#last-event').textContent = dateLabel(data.events[0]?.at);
  document.querySelector('#watch-label').textContent = 'À surveiller';
  const watch = document.querySelector('#watch-link');
  const problems = data.events.filter(event => !['done', 'planned'].includes(event.kind)).length;
  const blocked = Object.values(data.missions).filter(mission => mission.blocker).length;
  watch.href = problems ? '#journal' : '#missions';
  watch.textContent = problems ? `${problems} résultats à examiner →`
    : blocked ? `${blocked} missions avec blocage →` : `${Object.keys(data.missions).length} missions →`;
  if (!changed) return;
  ({ agents, missions, events, artifacts } = data);
  const toggle = document.querySelector('#journey-toggle');
  toggle.disabled = !data.journey;
  if (data.journey) {
    const { agent, mission, artifact } = data.journey;
    document.querySelector('#journey-title').textContent = missions[mission].title;
    document.querySelector('#journey-stops').innerHTML = [
      [`agent-${agent}`, 'Agent', agent],
      [`mission-${mission}`, 'Mission', missions[mission].title],
      [`preuve-${artifact}`, 'Résultat', artifacts[artifact].title]
    ].map(([route, label, title], i) => `<li><a href="#${escapeText(route)}"><b>0${i + 1}</b><span><small>${label}</small>${escapeText(title)}</span></a></li>`).join('');
  } else {
    toggle.setAttribute('aria-pressed', 'false');
    document.querySelector('#journey').hidden = true;
    document.querySelector('#journey-stops').replaceChildren();
    document.querySelector('.map-canvas').classList.remove('journey-active');
  }
  render();
  if (focusWithin) {
    const replacement = [...focusWithin.querySelectorAll('a, select')].find(el => (el.id || el.getAttribute('href')) === focusKey);
    (replacement || document.querySelector('#panel-title')).focus({ preventScroll: true });
  }
}

async function refreshSnapshot() {
  try {
    const response = await fetch('/snapshot.json', { cache: 'no-store' });
    if (!response.ok) throw new Error('Instantané indisponible');
    displaySnapshot(await response.json());
  } catch {
    document.querySelector('#demo-time').textContent = live
      ? `Actualisation indisponible. Dernière publication lue : ${dateLabel(live.publishedAt)}.`
      : 'Lecture du dépôt indisponible. Aucune activité simulée.';
    document.querySelector('#world-dot').classList.add('attention');
    if (!live) {
      document.querySelector('#world-state').textContent = 'Indisponible';
      document.querySelector('#data-mode').textContent = 'Lecture indisponible';
    }
  } finally {
    setTimeout(refreshSnapshot, 60_000);
  }
}

if (location.protocol === 'http:' && location.hostname === '127.0.0.1') refreshSnapshot();
else document.querySelector('#demo-time').textContent = 'Démarre le lecteur local pour afficher les données du dépôt.';
