#!/usr/bin/env bash
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "This cleanup script must run as root"
  exit 1
fi

mn -c || true
pkill -f "python3 -m http.server" || true
pkill -f "simple_http_server" || true

echo "Mininet cleanup completed"
