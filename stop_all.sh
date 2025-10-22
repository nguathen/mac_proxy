#!/usr/bin/env bash
# stop_all.sh
# Dừng tất cả HAProxy và Wireproxy instances

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🛑 Stopping HAProxy Multi-Instance System"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Dừng Web UI
echo ""
#echo "🛑 Stopping Web UI..."
#if [ -f "stop_webui.sh" ]; then
#    chmod +x stop_webui.sh
#    ./stop_webui.sh
#fi

# Dừng Gost
echo ""
echo "🛑 Stopping gost instances..."
if [ -f "manage_gost.sh" ]; then
    chmod +x manage_gost.sh
    ./manage_gost.sh stop
fi


# Dừng health monitors
echo ""
echo "🛑 Stopping health monitors..."
for pid_file in logs/health_*.pid; do
    if [ -f "$pid_file" ]; then
        port=$(basename "$pid_file" .pid | sed 's/health_//')
        pid=$(cat "$pid_file")
        kill "$pid" 2>/dev/null && echo "✓ Stopped health monitor for port $port (PID $pid)" || true
        rm -f "$pid_file"
    fi
done

# Dừng HAProxy processes
echo ""
echo "🛑 Stopping HAProxy processes..."
for pid_file in logs/haproxy_*.pid; do
    if [ -f "$pid_file" ]; then
        port=$(basename "$pid_file" .pid | sed 's/haproxy_//')
        pid=$(cat "$pid_file")
        kill "$pid" 2>/dev/null && echo "✓ Stopped HAProxy instance $port (PID $pid)" || true
        rm -f "$pid_file"
    fi
done

# Cleanup any remaining processes
pkill -f "haproxy.*config/haproxy_" 2>/dev/null || true
pkill -f "setup_haproxy.sh" 2>/dev/null || true

sleep 1

# Verify
echo ""
echo "🔍 Verifying shutdown..."
still_running=false

if pgrep -f "haproxy.*config/haproxy_" > /dev/null; then
    echo "⚠️  Some HAProxy processes still running"
    still_running=true
fi

if pgrep -f "setup_haproxy.sh" > /dev/null; then
    echo "⚠️  Some health monitor processes still running"
    still_running=true
fi

if [ "$still_running" = true ]; then
    echo ""
    echo "💡 Use force kill: pkill -9 -f haproxy"
else
    echo "✅ All processes stopped successfully"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ System stopped"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

