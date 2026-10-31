#!/usr/bin/env bash
set -euo pipefail
exec /usr/bin/python3 /opt/globalland/control/supervisor.py daily
