# 🔐 SECURITY.md — Audit de Sécurité du Canal de Tâches du VPS

> Dernier audit : 2026-10-30. Ce document décrit le modèle de menace du canal de tâches (`queue/` → `scripts/run_task.js` → `scripts/queue_runner.sh`), les défenses en place et les risques résiduels acceptés. Il doit être mis à jour à chaque changement du canal.

## Actifs à protéger

| Actif | Où il vit | Impact si compromis |
|---|---|---|
| Les 50,00 $ CAD (réserve réelle) | Comptes du CEO (jamais dans le dépôt) | Mort du monde |
| Clés API (Anthropic/OpenAI) | `/opt/globalland/.env` sur le VPS (chmod 600) | Dépenses réelles non contrôlées |
| Accès push GitHub | Deploy Key dédiée au repo | Code malveillant committé |
| Le reste du VPS (autres projets) | Hôte | Contamination inter-projets |

## Frontière de confiance (à lire en premier)

**Quiconque peut pousser dans ce dépôt peut faire exécuter du code dans le conteneur `globalland-core`.** C'est voulu — c'est le principe même du canal de tâches — mais cela signifie que les garde-fous du canal protègent contre les *erreurs d'agents* (hallucinations, boucles), pas contre un *acteur malveillant ayant l'accès push*. La réponse à cette frontière est le confinement : le conteneur (1 Go RAM / 0,5 CPU / `no-new-privileges` / aucun port / aucune clé / aucune secret), et le fait que seuls le CEO et les agents autorisés détiennent l'accès push.

## Défenses en profondeur (6 couches)

1. **Conteneur isolé** : `node:22-bookworm`, 0,5 CPU / 1 Go RAM, `no-new-privileges`, aucun port exposé, seul `./workspace` est monté. Les clés API ne sont **pas** dans le système de fichiers du conteneur.
2. **Liste blanche d'actions** (`run_task.js`) : seuls `node `, `bash scripts/`, `bash products/`, `npm run ` — tout le reste est refusé.
3. **Motifs interdits** : réseau (`curl`, `wget`, `ssh`), secrets (`.env`, clés), destruction (`sudo`, `rm -rf`, `shutdown`), et plafond de coût : toute tâche à coût estimé exige `"approved_by": "CEO"`.
4. **Clés API réservées aux tâches `AGENT_CODE`** (`queue_runner.sh`) : les tâches SHELL tournent sans aucun secret dans leur environnement.
5. **Masquage des secrets en sortie** (`run_task.js`, `scrubSecrets`) : les valeurs des clés d'environnement, les motifs `sk-...` et les blocs PEM sont remplacés par `[REDACTÉ]` avant toute publication du `.result.json` (dépôt public). L'`id` de tâche est assaini (anti-traversée de chemin, testé).
6. **Filtre anti-fuite au commit** (`queue_runner.sh`) : avant chaque commit, les modifications sont scannées ; tout motif de secret bloque le commit et le push (échec fermé) et journalise une alerte dans `logs/tasks.log`.

## Vulnérabilités corrigées lors de cet audit (testées, preuve à l'appui)

| # | Vulnérabilité | Gravité | Correctif | Test |
|---|---|---|---|---|
| 1 | Traversée de chemin via `task.id` (`"id": "../../x"` écrivait hors de `queue/`) | Élevée | Assainissement de l'id (`[A-Za-z0-9_-]` uniquement) | Le résultat reste confiné dans `queue/done/` |
| 2 | Fuite de clés API via la sortie des tâches (publiée sur le dépôt public) | Élevée | `scrubSecrets()` sur toute sortie publiée | La clé factice est publiée comme `[REDACTÉ]` |
| 3 | Clés API transmises à toutes les tâches, y compris SHELL | Élevée | `docker exec -e` uniquement pour `AGENT_CODE` | Vérification par `grep` du type avant exécution |
| 4 | Code du dépôt exécuté sur l'hôte par le cron (`node -e` inline dans `daily_audit.sh`) | Moyenne | Battement de cœur déplacé dans le conteneur (`scripts/tick.js`) | `daily_audit.sh` n'exécute plus que git + docker |

## Risques résiduels (acceptés, documentés)

* **Exécution de code par un détenteur de l'accès push** : incluse dans la frontière de confiance. Le conteneur est la sanction : pas de secrets, pas de réseau utile, ressources bornées.
* **Injection de prompt dans les tâches `AGENT_CODE`** : un contenu du repo lu par Claude Code/Codex pourrait tenter de détourner l'agent. Mitigé par : CEO obligatoire, coût estimé obligatoire, masquage des sorties, filtre au commit. Non éliminé.
* **`node -e` dans une action SHELL** : permet d'exécuter du JS arbitraire (et donc du réseau). Accepté car équivalent à la frontière de confiance push — mais un agent honnête ne doit jamais l'utiliser pour du réseau (les motifs `curl`/`wget` explicites sont bloqués, pas les requêtes Node). Recommandation : le Directeur SI/OP refuse les actions `node -e` contenant du code non lisible.
* **Plafond API 2 $/jour sur les tâches `AGENT_CODE`** : procédural (CEO approuve le coût estimé), pas techniquement borné par requête.

## Règles d'hygiène permanentes

1. Jamais de secret dans le dépôt (public) — le filtre au commit est la dernière ligne, pas la première.
2. `/opt/globalland/.env` : chmod 600, lu uniquement par `queue_runner.sh`, jamais monté dans le conteneur.
3. La Deploy Key reste dédiée à ce seul repo, write access, révocable en un clic.
4. Toute modification de `run_task.js` ou `queue_runner.sh` exige un commit documenté et, idéalement, un re-test des 4 correctifs ci-dessus.
