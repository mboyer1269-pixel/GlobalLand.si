#!/usr/bin/env bash
# GlobalLand — Installation de l'infrastructure isolée sur un VPS (Ubuntu/Debian, Docker requis)
# Usage : sudo bash scripts/setup_vps.sh
set -euo pipefail

GL_ROOT="/opt/globalland"
REPO_DIR="$GL_ROOT/workspace/GlobalLand.si"
REPO_HTTPS="https://github.com/mboyer1269-pixel/GlobalLand.si.git"
REPO_SSH="git@github.com:mboyer1269-pixel/GlobalLand.si.git"

echo "[1/6] Création du territoire isolé $GL_ROOT"
mkdir -p "$GL_ROOT/workspace" "$GL_ROOT/.ssh"
chmod 700 "$GL_ROOT/.ssh"

echo "[2/6] Génération de la clé de déploiement dédiée (si absente)"
if [ ! -f "$GL_ROOT/.ssh/globalland_deploy_key" ]; then
  ssh-keygen -t ed25519 -f "$GL_ROOT/.ssh/globalland_deploy_key" -N "" -C "globalland-deploy" -q
  chmod 600 "$GL_ROOT/.ssh/globalland_deploy_key"
  echo ""
  echo ">>> ACTION REQUISE : ajoutez cette clé publique dans GitHub > mboyer1269-pixel/GlobalLand.si >"
  echo ">>> Settings > Deploy keys > Add deploy key > cochez 'Allow write access' :"
  echo ""
  cat "$GL_ROOT/.ssh/globalland_deploy_key.pub"
  echo ""
else
  echo "    Clé déjà présente."
fi

echo "[3/6] Écriture du docker-compose.yml (conteneur isolé : 0,5 CPU, 1 Go RAM, aucun port)"
cat > "$GL_ROOT/docker-compose.yml" << 'YAML'
services:
  globalland-core:
    image: node:22-bookworm
    container_name: globalland-core
    working_dir: /workspace/GlobalLand.si
    command: tail -f /dev/null
    restart: unless-stopped
    cpus: "0.50"
    memory: 1024M
    security_opt:
      - no-new-privileges:true
    volumes:
      - ./workspace:/workspace
YAML

echo "[4/6] Clone du dépôt (HTTPS en lecture, Deploy Key pour l'écriture)"
if [ ! -d "$REPO_DIR/.git" ]; then
  git clone "$REPO_HTTPS" "$REPO_DIR"
fi
cd "$REPO_DIR"
git remote set-url origin "$REPO_HTTPS"
git remote set-url --push origin "$REPO_SSH"
git config core.sshCommand "ssh -i $GL_ROOT/.ssh/globalland_deploy_key -o StrictHostKeyChecking=accept-new"

echo "[5/6] Fichier d'environnement pour les clés API des agents de code (Claude Code / Codex)"
if [ ! -f "$GL_ROOT/.env" ]; then
  cat > "$GL_ROOT/.env" << 'ENVEOF'
# Clés API des agents de code — chmod 600, JAMAIS commité dans le dépôt.
# Décommentez et remplissez si vous voulez utiliser les tâches AGENT_CODE :
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
ENVEOF
  chmod 600 "$GL_ROOT/.env"
  echo "    /opt/globalland/.env créé (vide) — remplissez-le pour activer les agents de code."
else
  echo "    /opt/globalland/.env déjà présent."
fi

echo "[6/6] Démarrage du conteneur"
docker compose -f "$GL_ROOT/docker-compose.yml" --project-directory "$GL_ROOT" up -d

echo ""
echo "=== Installation terminée ==="
echo "Prochaines étapes :"
echo "  1. Enregistrer la clé publique ci-dessus dans GitHub (Deploy keys, write access)."
echo "  2. Ajouter les deux lignes cron (audit quotidien + file d'instructions) : crontab -e"
echo "     0 8 * * * $REPO_DIR/scripts/daily_audit.sh >> $REPO_DIR/logs/audit_cron.log 2>&1"
echo "     */5 * * * * $REPO_DIR/scripts/queue_runner.sh >> $REPO_DIR/logs/queue_cron.log 2>&1"
echo "  3. Vérifier le monde : docker exec globalland-core node scripts/audit.js"
