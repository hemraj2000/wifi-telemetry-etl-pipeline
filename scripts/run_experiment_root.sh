#!/usr/bin/env bash
set -euo pipefail

OUTDIR="${1:?outdir missing}"

exec /usr/bin/python3 -u "/home/thehemraj/dt212g_project/scripts/run_experiment.py" \
  --out "$OUTDIR" \
  --requests-per-sta 1000
