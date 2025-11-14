#!/usr/bin/env bash
# restart_app.sh
# Dừng và khởi động lại MacProxy.app

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄 Restarting Mac Proxy App"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Dừng app
echo "🛑 Stopping app..."
if [ -f "$SCRIPT_DIR/stop_app.sh" ]; then
    chmod +x "$SCRIPT_DIR/stop_app.sh"
    "$SCRIPT_DIR/stop_app.sh"
else
    echo "❌ stop_app.sh not found"
    exit 1
fi

echo ""
echo "⏳ Waiting 3 seconds before restart..."
sleep 3

# Khởi động lại app
echo ""
echo "🚀 Starting app..."
if [ -f "$SCRIPT_DIR/launch_app.sh" ]; then
    chmod +x "$SCRIPT_DIR/launch_app.sh"
    "$SCRIPT_DIR/launch_app.sh"
else
    echo "❌ launch_app.sh not found"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ App restarted successfully"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

