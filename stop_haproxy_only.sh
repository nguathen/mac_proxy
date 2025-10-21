#!/usr/bin/env bash
# stop_haproxy_only.sh
# Chỉ dừng HAProxy instances, không dừng Web UI

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🛑 Stopping HAProxy Instances Only"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Dừng health monitors
echo ""
echo "🛑 Stopping health monitors..."
if [ -f "logs/health_7891.pid" ]; then
    pid=$(cat logs/health_7891.pid)
    kill "$pid" 2>/dev/null && echo "✓ Stopped health monitor for instance 1 (PID $pid)" || true
    rm -f logs/health_7891.pid
fi

if [ -f "logs/health_7892.pid" ]; then
    pid=$(cat logs/health_7892.pid)
    kill "$pid" 2>/dev/null && echo "✓ Stopped health monitor for instance 2 (PID $pid)" || true
    rm -f logs/health_7892.pid
fi

# Dừng HAProxy processes
echo ""
echo "🛑 Stopping HAProxy processes..."
if [ -f "logs/haproxy_7891.pid" ]; then
    pid=$(cat logs/haproxy_7891.pid)
    kill "$pid" 2>/dev/null && echo "✓ Stopped HAProxy instance 1 (PID $pid)" || true
    rm -f logs/haproxy_7891.pid
fi

if [ -f "logs/haproxy_7892.pid" ]; then
    pid=$(cat logs/haproxy_7892.pid)
    kill "$pid" 2>/dev/null && echo "✓ Stopped HAProxy instance 2 (PID $pid)" || true
    rm -f logs/haproxy_7892.pid
fi

# Cleanup any remaining processes
pkill -f "haproxy.*haproxy_7891.cfg" 2>/dev/null || true
pkill -f "haproxy.*haproxy_7892.cfg" 2>/dev/null || true
pkill -f "setup_haproxy.sh" 2>/dev/null || true

sleep 1

# Verify
echo ""
echo "🔍 Verifying shutdown..."
still_running=false

if pgrep -f "haproxy.*haproxy_789[12].cfg" > /dev/null; then
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
    echo "✅ All HAProxy processes stopped successfully"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ HAProxy stopped (Web UI still running)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
