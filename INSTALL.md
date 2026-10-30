# 🚀 INSTALL.md — Installation de GlobalLand sur un VPS

> Prérequis : un VPS Ubuntu/Debian avec Docker et git installés (aucun autre service requis). L'installation n'affecte aucun autre projet de la machine : tout vit dans `/opt/globalland`, dans un conteneur sans port exposé.

## 1. Installation (une commande)

```bash
git clone https://github.com/mboyer1269-pixel/GlobalLand.si /tmp/globalland-bootstrap && \
sudo bash /tmp/globalland-bootstrap/scripts/setup_vps.sh && rm -rf /tmp/globalland-bootstrap
```

Le script : crée `/opt/globalland`, génère la clé de déploiement dédiée, écrit le `docker-compose.yml`, clone le dépôt et démarre le conteneur `globalland-core` (0,5 CPU / 1 Go RAM / `no-new-privileges` / aucun port).

## 2. Enregistrer la clé de déploiement dans GitHub

Le script affiche la clé publique. Puis :

1. GitHub → `mboyer1269-pixel/GlobalLand.si` → **Settings** → **Deploy keys** → **Add deploy key**.
2. Titre : `globalland-vps` — coller la clé — **cocher « Allow write access »** — Add key.

Sans write access, le VPS ne pourra pas publier les audits ni les résultats de tâches.

## 3. Activer les automatismes (crontab)

```bash
crontab -e
```

Ajouter les deux lignes :

```cron
0 8 * * * /opt/globalland/workspace/GlobalLand.si/scripts/daily_audit.sh >> /opt/globalland/workspace/GlobalLand.si/logs/audit_cron.log 2>&1
*/5 * * * * /opt/globalland/workspace/GlobalLand.si/scripts/queue_runner.sh >> /opt/globalland/workspace/GlobalLand.si/logs/queue_cron.log 2>&1
```

## 4. Vérifier que le monde vit

```bash
# Audit immédiat (rapport de la Banque Centrale)
docker exec globalland-core node scripts/audit.js

# Après max 5 minutes : la tâche de fumée TASK-0001 (déjà dans queue/inbox/) doit être
# exécutée et son résultat publié dans queue/done/TASK-0001.result.json sur GitHub.
```

## 5. (Optionnel) Activer les agents de code — Claude Code et Codex

Les tâches de type `AGENT_CODE` (voir `queue/PROTOCOL.md`) envoient Claude Code ou Codex travailler dans le dépôt, sur le VPS. Elles exigent toutes `"approved_by": "CEO"` et un coût estimé — l'argent réel ne sort jamais sans votre signature.

Pour les activer, renseignez les clés API dans `/opt/globalland/.env` (fichier créé par l'installeur, chmod 600, jamais commité) :

```bash
sudo nano /opt/globalland/.env
# ANTHROPIC_API_KEY=sk-ant-...   <- pour Claude Code
# OPENAI_API_KEY=sk-...           <- pour Codex
```

Les agents de code sont téléchargés et exécutés par `npx` dans le conteneur, sans shell (aucune injection possible), avec un plafond de 15 minutes par tâche.

## 6. Test de bout en bout d'une tâche d'agent de code

Depuis n'importe quel agent (Grok Bot, Claude Code local, ou vous-même), poussez :

```bash
cat > queue/inbox/TASK-0002.json << 'EOF'
{
  "id": "TASK-0002",
  "type": "AGENT_CODE",
  "submitted_by": "DIRECTEUR_SI_OP",
  "created_at": "2026-10-31T12:00:00Z",
  "agent": "claude-code",
  "prompt": "Ajoute un fichier products/ideas.md listant 3 idées de micro-outils vendables à coût 0.",
  "description": "Test du canal agents de code",
  "estimated_cost_cad": 0.25,
  "approved_by": "CEO"
}
EOF
git add queue/inbox/TASK-0002.json && git commit -m "queue(TASK-0002): test agent de code" && git push origin main
```

Dans les 5 minutes, le VPS exécute la tâche, committe le fichier créé par l'agent et publie le rapport dans `queue/done/TASK-0002.result.json`.

## Récapitulatif des règles de sécurité

| Surface | Protection |
|---|---|
| Conteneur | 0,5 CPU / 1 Go RAM, `no-new-privileges`, aucun port, aucune clé |
| Tâches SHELL | Liste blanche (`node`, `bash scripts/`, `bash products/`, `npm run`), motifs réseau/secrets/destruction bloqués |
| Tâches AGENT_CODE | CEO obligatoire + coût estimé obligatoire, exécution sans shell, 15 min max |
| Dépenses réelles | Veto CEO appliqué par le garde-fou, transaction `REAL_EXPENSE` au ledger obligatoire |
| Clés API | `/opt/globalland/.env` (chmod 600), jamais dans le dépôt public |
| Push VPS → GitHub | Deploy Key dédiée à ce seul repo (write access) |
