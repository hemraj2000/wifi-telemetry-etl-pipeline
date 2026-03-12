#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/thehemraj/dt212g_project"
OUT_DIR="$PROJECT_DIR/artifacts/airflow_final"
MAX_TRIES=4

check_roaming() {
    local f="$1"

    [ -f "$f" ] || return 1

    sta1_count=$(awk -F, 'NR>1 && $2=="sta1" && $3!="" {print $3}' "$f" | sort -u | wc -l)
    sta2_count=$(awk -F, 'NR>1 && $2=="sta2" && $3!="" {print $3}' "$f" | sort -u | wc -l)

    if [ "$sta1_count" -ge 2 ] && [ "$sta2_count" -ge 2 ]; then
        return 0
    fi

    return 1
}

cd "$PROJECT_DIR"

for i in $(seq 1 "$MAX_TRIES"); do
    echo "=== Airflow experiment attempt $i/$MAX_TRIES ==="

    /usr/local/bin/mn -c || true
    pkill -9 -f "python3 -m http.server" || true

    rm -rf "$OUT_DIR"
    mkdir -p "$OUT_DIR"

    /usr/bin/python3 "$PROJECT_DIR/scripts/run_experiment.py" --out "$OUT_DIR" --roam-after 110

    if check_roaming "$OUT_DIR/wifi_link.csv"; then
        echo "=== Roaming detected for both stations ==="
        exit 0
    fi

    echo "=== Roaming not detected, retrying... ==="
    sleep 2
done

echo "Roaming was not detected after $MAX_TRIES attempts."
exit 1
