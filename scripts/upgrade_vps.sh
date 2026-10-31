#!/usr/bin/env bash
# Administrative upgrade, never invoked by a task. Existing cron and state are preserved.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo'; exit 1; }
REV=${1:?Usage: upgrade_vps.sh REVIEWED_FULL_SHA}
[[ $REV =~ ^[0-9a-f]{40}$ ]] || exit 1
HERE=$(cd -- "$(dirname -- "$0")/.." && pwd)
[[ $(git -C "$HERE" rev-parse HEAD) == "$REV" && -z $(git -C "$HERE" status --porcelain) ]] || { echo 'Exact reviewed clean checkout required'; exit 1; }
ROOT=/opt/globalland
[[ -d $ROOT/control && -d $ROOT/source.git ]] || { echo 'Existing v2 installation required'; exit 1; }
[[ ! -e $ROOT/releases/$REV ]] || { echo 'Release already present; inspect status instead of repeating'; exit 1; }
umask 077
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP="$ROOT/backups/upgrade-$STAMP"
install -d -m 700 "$BACKUP"
CRON_BACKUP="$BACKUP/cron"
if [[ -f /etc/cron.d/globalland ]]; then mv /etc/cron.d/globalland "$CRON_BACKUP"; fi
restore_cron() { if [[ -f $CRON_BACKUP ]]; then install -m 644 "$CRON_BACKUP" /etc/cron.d/globalland; fi; }
trap restore_cron EXIT
exec 9>"$ROOT/state/supervisor.lock"
flock -x 9
# SQLite and task journals are quiescent under the same supervisor lock.
install -d -m 755 "$ROOT/releases"
tar -czf "$BACKUP/state-before.tgz" -C "$ROOT" control state source.git ssh releases
RELEASE="$ROOT/releases/$REV"
install -d -m 755 "$ROOT/releases" "$RELEASE"
for file in "$HERE"/scripts/*.py "$HERE"/scripts/*.js "$HERE"/scripts/*.sh "$HERE"/scripts/decision.schema.json; do install -m 644 "$file" "$RELEASE/$(basename "$file")"; done
printf '%s\n' "$REV" > "$RELEASE/REVISION"
install -m 644 "$ROOT/control/compose.yml" "$RELEASE/compose.yml"
python3 - "$ROOT" "$RELEASE" <<'PY'
import json,pathlib,re,sys
root,release=map(pathlib.Path,sys.argv[1:]);old=root/'control/config.json'
config=json.loads(old.read_text()) if old.exists() else {}
image=re.search(r'^\s*image:\s*(\S+)',(release/'compose.yml').read_text(),re.M)
if not image:raise SystemExit('Existing image missing')
config.update(executor_enabled=True,executor_image=image.group(1))
config.setdefault('controller',{'mode':'external_grok'})
(release/'config.json').write_text(json.dumps(config,indent=2)+'\n')
PY
python3 -m py_compile "$RELEASE"/*.py
docker compose -f "$RELEASE/compose.yml" config --quiet
# Keep previous installed code for rollback, including configs. No credentials are moved.
if [[ -L $ROOT/control ]]; then cp -a "$ROOT/control" "$BACKUP/control-link"; rm "$ROOT/control"; else mv "$ROOT/control" "$BACKUP/control"; fi
ln -s "$RELEASE" "$ROOT/control"
restore_cron
trap - EXIT
printf 'GlobalLand control upgraded. Previous control: %s\n' "$BACKUP"
printf 'No subscription login, inference or funding performed. Run status and manual v3 smoke tests before enabling think cron.\n'
