# 📬 PROTOCOL.md — File d'instructions du VPS (GlobalLand)

> Seul canal permettant aux agents de déclencher des tâches sur le serveur du monde. Les agents ne touchent jamais au VPS directement : ils poussent un fichier de tâche ici, le VPS l'exécute et publie le résultat.

## Cycle de vie d'une tâche

```text
queue/inbox/TASK-XXXX.json   →   exécution (conteneur globalland-core)   →   queue/done/TASK-XXXX.result.json
                                  (si refusée ou échouée)                    queue/failed/TASK-XXXX.result.json
```

1. L'agent pousse `queue/inbox/TASK-XXXX.json` (commit + push).
2. Le VPS détecte la tâche (vérification toutes les 5 minutes via `scripts/queue_runner.sh`).
3. `scripts/run_task.js` valide puis exécute la tâche **dans le conteneur isolé**.
4. Le résultat est publié dans `queue/done/` ou `queue/failed/` — l'agent le lit au prochain pull.

## Schéma du fichier de tâche (type SHELL — défaut)

```json
{
  "id": "TASK-0002",
  "submitted_by": "AGENT_BUILDER",
  "created_at": "2026-10-31T12:00:00Z",
  "action": "node products/mon-outil.js",
  "description": "Exécuter l'outil de génération pour la vente du jour",
  "estimated_cost_cad": 0.00,
  "approved_by": null
}
```

## Schéma du fichier de tâche (type AGENT_CODE — Claude Code / Codex)

Pour envoyer un agent de code (Claude Code ou Codex) travailler dans le dépôt, sur le VPS :

```json
{
  "id": "TASK-0005",
  "type": "AGENT_CODE",
  "submitted_by": "DIRECTEUR_SI_OP",
  "created_at": "2026-10-31T12:00:00Z",
  "agent": "claude-code",
  "prompt": "Corrige le bug de calcul du runway dans scripts/audit.js et ajoute un test rapide.",
  "description": "Correction du bug runway",
  "estimated_cost_cad": 0.50,
  "approved_by": "CEO"
}
```

Règles spécifiques aux tâches `AGENT_CODE` :

* `"agent"` : `"claude-code"` ou `"codex"` (toute autre valeur est refusée).
* `"prompt"` : instructions en langage naturel (min. 10 caractères) — exécuté sans shell, aucune injection possible.
* `"estimated_cost_cad"` : **obligatoire et > 0,00** — un agent de code consomme de l'API réelle (les clés vivent dans `/opt/globalland/.env` sur le VPS, jamais dans le dépôt).
* `"approved_by": "CEO"` : **obligatoire** — votre veto s'applique automatiquement, le garde-fou refuse sans.
* L'agent exécute dans le répertoire du dépôt (15 min max) ; ses modifications de fichiers sont commitées et poussées par le runner dans le même cycle, avec son rapport dans le `.result.json`.
* Après exécution, la transaction `REAL_EXPENSE` correspondante doit être inscrite au `ledger.json`.

## Règles du garde-fou (non négociables)

* **Liste blanche d'actions** : la tâche doit commencer par `node `, `bash scripts/`, `bash products/` ou `npm run `. Tout le reste est refusé.
* **Motifs interdits** : réseau (`curl`, `wget`, `ssh`), secrets (`.env`, clés), destruction (`rm -rf`, `sudo`, `shutdown`) — refus automatique.
* **Coût** : si `estimated_cost_cad` > 0,00, la tâche exige `"approved_by": "CEO"` — sinon refus.
* **Timeout** : 5 minutes par tâche ; sortie plafonnée à 8 000 caractères dans le résultat.
* **Journalisation** : chaque cycle est tracé dans `logs/tasks.log`.

## Convention d'ID

Format `TASK-NNNN` croissant (vérifiez le dernier ID dans `queue/done/` et `queue/failed/` avant de soumettre). Toute tâche ayant un impact financier doit **aussi** être inscrite au `ledger.json` dans le même commit (voir `CURSOR.md`).
