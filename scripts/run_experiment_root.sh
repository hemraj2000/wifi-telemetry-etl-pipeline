#!/usr/bin/env bash
set -euo pipefail

OUTDIR="${1:?outdir missing}"
REQUESTS="${2:-1000}"
ROAM_AFTER="${3:-10}"

if [ "$EUID" -ne 0 ]; then
  echo "This script must run as root"
  exit 1
fi

mkdir -p "$OUTDIR"

# Clean old Mininet state before running
mn -c || true

# Run Mininet-WiFi experiment with system Python
/usr/bin/python3 -u "/home/thehemraj/dt212g_project/scripts/run_experiment.py" \
  --out "$OUTDIR" \
  --requests-per-sta "$REQUESTS" \
  --roam-after "$ROAM_AFTER"

# Fix permissions so Airflow/user can write transform, plots and report
OWNER="${SUDO_USER:-thehemraj}"
GROUP="$(id -gn "$OWNER" 2>/dev/null || echo "$OWNER")"
chown -R "$OWNER:$GROUP" "$OUTDIR" || true

echo "Experiment completed: $OUTDIR"
