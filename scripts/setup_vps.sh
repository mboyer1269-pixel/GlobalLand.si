#!/usr/bin/env bash
# Run only from a reviewed checkout at the exact SHA supplied below.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo'; exit 1; }
REV=${1:?Usage: setup_vps.sh FULL_COMMIT_SHA node:22-bookworm@sha256:DIGEST}
IMAGE=${2:?Supply an independently verified Node 22 image digest}
[[ $REV =~ ^[0-9a-f]{40}$ && $IMAGE =~ ^node:22-bookworm@sha256:[0-9a-f]{64}$ ]] || { echo 'Invalid commit/image digest'; exit 1; }
HERE=$(cd -- "$(dirname -- "$0")/.." && pwd)
[[ $(git -C "$HERE" rev-parse HEAD) == "$REV" ]] || { echo 'Checkout SHA mismatch'; exit 1; }
[[ -z $(git -C "$HERE" status --porcelain) ]] || { echo 'Checkout must be clean'; exit 1; }
for tool in git docker python3 ssh-keygen; do command -v "$tool" >/dev/null; done
docker compose version >/dev/null
GL_ROOT=/opt/globalland
[[ ! -e $GL_ROOT ]] || { echo 'Existing installation: stop and follow INSTALL.md upgrade/rollback procedure'; exit 1; }
umask 077
mkdir -p "$GL_ROOT"/{control,ssh,state,work,backups}
chmod 755 "$GL_ROOT" "$GL_ROOT/control" "$GL_ROOT/work"
for file in "$HERE"/scripts/*.py "$HERE"/scripts/*.js "$HERE"/scripts/*.sh "$HERE"/scripts/*.json; do
 install -m 644 "$file" "$GL_ROOT/control/$(basename "$file")"
done
printf '%s\n' "$REV" > "$GL_ROOT/control/REVISION"
cat > "$GL_ROOT/control/compose.yml" <<YAML
services:
  core:
    image: $IMAGE
    user: "65534:65534"
    working_dir: /workspace
    read_only: true
    network_mode: none
    cpus: 0.5
    mem_limit: 1024m
    pids_limit: 64
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    tmpfs: ["/tmp:rw,noexec,nosuid,size=64m"]
    volumes:
      - $GL_ROOT/work:/workspace:ro
      - $GL_ROOT/control:/control:ro
YAML
chmod 644 "$GL_ROOT/control/compose.yml"
python3 - "$GL_ROOT/control/config.json" "$IMAGE" <<'PYCONF'
import json,pathlib,sys
pathlib.Path(sys.argv[1]).write_text(json.dumps({'executor_enabled':True,'executor_image':sys.argv[2],'controller':{'mode':'external_grok'}},indent=2)+'\n')
PYCONF
docker compose -f "$GL_ROOT/control/compose.yml" config --quiet
ssh-keygen -t ed25519 -f "$GL_ROOT/ssh/deploy_key" -N '' -C globalland-vps -q
printf '\nRegister this PUBLIC key as a repo-only write Deploy Key:\n'
cat "$GL_ROOT/ssh/deploy_key.pub"
printf '\nInstall verified GitHub host keys in %s/ssh/known_hosts (600).\n' "$GL_ROOT"
printf 'After the public key and verified host keys are installed, run: bash /opt/globalland/control/finalize_setup.sh\n'
printf 'Control installed. No container, inference or cron started. See INSTALL.md.\n'
