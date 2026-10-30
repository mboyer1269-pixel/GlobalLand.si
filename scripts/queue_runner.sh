#!/usr/bin/env bash
# GlobalLand — Surveillant de la file d'instructions (s'exécute sur le VPS hôte)
# Boucle : git pull -> exécuter les tâches en attente dans le conteneur -> publier les résultats
# Crontab (vérification toutes les 5 minutes) :
#   */5 * * * * /opt/globalland/workspace/GlobalLand.si/scripts/queue_runner.sh >> /opt/globalland/workspace/GlobalLand.si/logs/queue_cron.log 2>&1
set -uo pipefail

GL_ROOT="/opt/globalland"
REPO="$GL_ROOT/workspace/GlobalLand.si"
SSH_KEY="$GL_ROOT/.ssh/globalland_deploy_key"
CONTAINER="globalland-core"
ENV_FILE="$GL_ROOT/.env" # clés API des agents de code (chmod 600, jamais commité)
export GIT_SSH_COMMAND="ssh -i $SSH_KEY -o StrictHostKeyChecking=accept-new"

# Verrou : une seule exécution à la fois
exec 9>/tmp/globalland-queue.lock
flock -n 9 || { echo "[queue_runner] une exécution est déjà en cours, abandon"; exit 0; }

echo "[queue_runner] $(date -Iseconds) — cycle"

cd "$REPO" || exit 1
git pull --ff-only origin main || { echo "[queue_runner] git pull impossible, abandon du cycle"; exit 1; }

shopt -s nullglob
tasks=(queue/inbox/*.json)
if [ ${#tasks[@]} -eq 0 ]; then
  echo "[queue_runner] aucune tâche en attente"
  exit 0
fi

# Transmet les clés API (si présentes dans /opt/globalland/.env) au conteneur, sans jamais les écrire dans le dépôt
EXEC_ENV=()
if [ -f "$ENV_FILE" ]; then
  while IFS='=' read -r k v; do
    case "$k" in ''|\#*) continue ;; esac
    EXEC_ENV+=(-e "$k=$v")
  done < "$ENV_FILE"
fi

for task in "${tasks[@]}"; do
  echo "[queue_runner] exécution de $task"
  # Les clés API ne sont transmises qu'aux tâches AGENT_CODE — les tâches SHELL n'en ont pas besoin.
  if grep -q '"type": "AGENT_CODE"' "$task"; then
    docker exec "${EXEC_ENV[@]}" "$CONTAINER" node scripts/run_task.js "$task" || \
      echo "[queue_runner] échec de l'exécuteur sur $task (conteneur éteint ?)"
  else
    docker exec "$CONTAINER" node scripts/run_task.js "$task" || \
      echo "[queue_runner] échec de l'exécuteur sur $task (conteneur éteint ?)"
  fi
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | QUEUE | $(basename "$task" .json) | traitée" >> logs/tasks.log

  # Un agent de code peut avoir modifié le dépôt : on archive son travail dans le même cycle.
  # FILTRE ANTI-FUITE : aucun secret ne doit jamais être committé (le dépôt est public).
  git add -A
  if git diff --cached | grep -qE 'sk-[a-zA-Z0-9_-]{10,}|BEGIN [A-Z ]*PRIVATE KEY|ANTHROPIC_API_KEY=sk|OPENAI_API_KEY=sk'; then
    git reset >/dev/null
    echo "[queue_runner] ALERTE SÉCURITÉ : motif de secret détecté dans les modifications — commit et push BLOQUÉS (échec fermé)."
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) | ALERTE | $(basename "$task" .json) | secret détecté, commit bloqué" >> logs/tasks.log
  else
    git -c user.name="globalland-runner" -c user.email="runner@globalland.local" \
      commit -m "ops(queue): $(basename "$task" .json) — tâche exécutée" --quiet || true
  fi
done

# Publication des résultats sur GitHub (les agents lisent queue/done/ et queue/failed/)
git push origin main || echo "[queue_runner] push refusé (Deploy Key sans write access ?)"

echo "[queue_runner] $(date -Iseconds) — cycle terminé"
