#!/usr/bin/env bash
# Run interactively on the VPS; never paste generated auth tokens in chat or GitHub.
set -euo pipefail
PROVIDER=${1:?Usage: login_subscriptions.sh codex|claude|cursor IMMUTABLE_IMAGE}
IMAGE=${2:?Supply the built image ID (sha256:...) or repository@sha256:...}
[[ $EUID -eq 0 ]] || { echo 'Run with sudo'; exit 1; }
[[ $PROVIDER == codex || $PROVIDER == claude || $PROVIDER == cursor ]] || exit 1
[[ $IMAGE =~ ^([a-zA-Z0-9./:_-]+@)?sha256:[0-9a-f]{64}$ ]] || exit 1
CREDENTIALS="/opt/globalland/credentials/$PROVIDER"
install -d -m 700 -o 1000 -g 1000 "$CREDENTIALS"
if [[ $PROVIDER == codex ]]; then
 docker run --rm -it --user 1000:1000 --cap-drop ALL --security-opt no-new-privileges:true \
  --mount "type=bind,src=$CREDENTIALS,dst=/home/node/.codex" \
  --workdir /tmp "$IMAGE" codex login --device-auth
elif [[ $PROVIDER == claude ]]; then
 docker run --rm -it --user 1000:1000 --cap-drop ALL --security-opt no-new-privileges:true \
  --env CLAUDE_CONFIG_DIR=/home/node/.claude \
  --mount "type=bind,src=$CREDENTIALS,dst=/home/node/.claude" \
  --workdir /tmp "$IMAGE" claude auth login
else
 install -d -m 700 -o 1000 -g 1000 "$CREDENTIALS/.cursor"
 docker run --rm -it --user 1000:1000 --cap-drop ALL --security-opt no-new-privileges:true \
  --env NO_OPEN_BROWSER=1 --env CURSOR_CONFIG_DIR=/home/node/.cursor \
  --mount "type=bind,src=$CREDENTIALS,dst=/home/node" \
  --workdir /tmp "$IMAGE" cursor-agent login
fi
