#!/usr/bin/env bash
# stop_webui.sh
# Dừng Web UI

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="./logs/webui.pid"

echo "🛑 Stopping Web UI..."

if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null && echo "✅ Stopped Web UI (PID: $pid)"
        rm -f "$PID_FILE"
    else
        echo "⚠️  Web UI not running (stale PID)"
        rm -f "$PID_FILE"
    fi
else
    echo "⚠️  Web UI not running"
fi

# Cleanup any remaining process on port 5000
lsof -ti :5000 2>/dev/null | xargs kill -9 2>/dev/null || true

echo "✅ Web UI stopped"

