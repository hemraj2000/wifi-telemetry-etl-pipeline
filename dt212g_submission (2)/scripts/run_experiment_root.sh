#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${1:?run_id missing}"
SCRIPT="/home/thehemraj/dt212g_project/scripts/run_experiment.py"

exec /usr/bin/python3 "$SCRIPT" --run-id "$RUN_ID"
