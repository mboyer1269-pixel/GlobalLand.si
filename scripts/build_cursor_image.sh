#!/usr/bin/env bash
# Dockerfile FROM requires an image reference; a bare local image ID is not one.
set -euo pipefail
HERE=$(cd "$(dirname "$0")/.." && pwd)
BASE_FILE=${1:-/opt/globalland/state/private/brain-image.txt}
CURSOR_FILE=${2:-/opt/globalland/state/private/cursor-image.txt}
umask 077
BASE_ID=$(cat "$BASE_FILE")
[[ $BASE_ID =~ ^sha256:[0-9a-f]{64}$ ]] || { echo 'Expected a full local brain image ID' >&2; exit 1; }
[[ $(docker image inspect "$BASE_ID" --format '{{.Id}}') == "$BASE_ID" ]] || { echo 'Original brain image unavailable' >&2; exit 1; }
BASE_TAG="globalland-brain:cursor-base-${BASE_ID#sha256:}"
docker image tag "$BASE_ID" "$BASE_TAG"
[[ $(docker image inspect "$BASE_TAG" --format '{{.Id}}') == "$BASE_ID" ]] || { echo 'Local base tag mismatch' >&2; exit 1; }
TEMP_FILE=$(mktemp "${CURSOR_FILE}.XXXXXX")
trap 'rm -f "$TEMP_FILE"' EXIT
docker build --pull=false --iidfile "$TEMP_FILE" \
 --build-arg "EXISTING_BRAIN_IMAGE=$BASE_TAG" \
 -f "$HERE/docker/Cursor.Brain.Dockerfile" \
 -t globalland-brain:cursor "$HERE"
[[ $(docker image inspect "$BASE_TAG" --format '{{.Id}}') == "$BASE_ID" ]] || { echo 'Local base tag changed during build' >&2; exit 1; }
CURSOR_ID=$(cat "$TEMP_FILE")
[[ $CURSOR_ID =~ ^sha256:[0-9a-f]{64}$ ]] || exit 1
docker run --rm --network none "$CURSOR_ID" cursor-agent --version
printf '%s\n' "$CURSOR_ID" > "$TEMP_FILE"
mv "$TEMP_FILE" "$CURSOR_FILE"
