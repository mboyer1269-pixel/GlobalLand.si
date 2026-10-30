#!/usr/bin/env bash
# GlobalLand — Reproduction de l'infrastructure isolée sur un VPS (Ubuntu/Debian)
# Usage : sudo bash scripts/setup_vps.sh
set -euo pipefail

GL_ROOT="/opt/globalland"
REPO_SSH="git@github.com:mboyer1269-pixel/GlobalLand.si.git"

echo "[1/5] Création du territoire isolé $GL_ROOT"
mkdir -p "$GL_ROOT/workspace" "$GL_ROOT/.ssh"
chmod 700 "$GL_ROOT/.ssh"

if [ ! -f "$GL_ROOT/.ssh/globalland_deploy_key" ]; then
  echo "[2/5] Génération de la clé de déploiement dédiée"
  ssh-keygen -t ed25519 -f "$GL_ROOT/.ssh/globalland_deploy_key" -N "" -C "globalland-deploy"
  chmod 600 "$GL_ROOT/.ssh/globalland_deploy_key"
  echo ">>> Ajoutez cette clé publique dans GitHub > GlobalLand.si > Settings > Deploy keys (Allow write access) :"
  cat "$GL_ROOT/.ssh/globalland_deploy_key.pub"
else
  echo "[2/5] Clé de déploiement déjà présente"
fi

echo "[3/5] Écriture du docker-compose.yml"
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

echo "[4/5] Clone du dépôt (SSH)"
if [ ! -d "$GL_ROOT/workspace/GlobalLand.si" ]; then
  GIT_SSH_COMMAND="ssh -i $GL_ROOT/.ssh/globalland_deploy_key -o StrictHostKeyChecking=accept-new" \
    git clone "$REPO_SSH" "$GL_ROOT/workspace/GlobalLand.si"
fi

echo "[5/5] Démarrage du conteneur"
cd "$GL_ROOT" && docker compose up -d

echo "Terminé. Audit quotidien : docker exec globalland-core node scripts/audit.js"
