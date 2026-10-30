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

## Schéma du fichier de tâche

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

## Règles du garde-fou (non négociables)

* **Liste blanche d'actions** : la tâche doit commencer par `node `, `bash scripts/`, `bash products/` ou `npm run `. Tout le reste est refusé.
* **Motifs interdits** : réseau (`curl`, `wget`, `ssh`), secrets (`.env`, clés), destruction (`rm -rf`, `sudo`, `shutdown`) — refus automatique.
* **Coût** : si `estimated_cost_cad` > 0,00, la tâche exige `"approved_by": "CEO"` — sinon refus.
* **Timeout** : 5 minutes par tâche ; sortie plafonnée à 8 000 caractères dans le résultat.
* **Journalisation** : chaque cycle est tracé dans `logs/tasks.log`.

## Convention d'ID

Format `TASK-NNNN` croissant (vérifiez le dernier ID dans `queue/done/` et `queue/failed/` avant de soumettre). Toute tâche ayant un impact financier doit **aussi** être inscrite au `ledger.json` dans le même commit (voir `CURSOR.md`).
