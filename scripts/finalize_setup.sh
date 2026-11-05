#!/usr/bin/env bash
# After registering the generated public deploy key and verified GitHub host keys.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo'; exit 1; }
ROOT=/opt/globalland
REV=$(cat "$ROOT/control/REVISION")
[[ $REV =~ ^[0-9a-f]{40}$ ]] || exit 1
[[ -f $ROOT/ssh/known_hosts && -f $ROOT/ssh/deploy_key ]] || { echo 'Register dedicated deploy key and install verified GitHub host keys first'; exit 1; }
export GIT_SSH_COMMAND="ssh -i $ROOT/ssh/deploy_key -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$ROOT/ssh/known_hosts"
if [[ ! -d $ROOT/source.git ]]; then
 git clone --bare git@github.com:mboyer1269-pixel/GlobalLand.si.git "$ROOT/source.git"
fi
git --git-dir="$ROOT/source.git" cat-file -e "$REV^{commit}"
git --git-dir="$ROOT/source.git" update-ref refs/heads/main "$REV"
git --git-dir="$ROOT/source.git" symbolic-ref HEAD refs/heads/main
git --git-dir="$ROOT/source.git" config core.hooksPath /dev/null
printf 'Source ready at %s. No models or schedules started.\n' "$REV"
printf 'Next: verify authorized queue/daily cycles, then preview install_maintenance.py; see INSTALL.md.\n'
