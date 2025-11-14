#!/usr/bin/env bash
# stop_all.sh
# Dừng tất cả HAProxy và Wireproxy instances

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🛑 Stopping Gost Proxy System"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Dừng Auto Credential Updater
echo ""
echo "🛑 Stopping Auto Credential Updater..."
if [ -f "start_auto_updater.sh" ]; then
    chmod +x start_auto_updater.sh
    ./start_auto_updater.sh stop
fi

# Dừng Web UI
echo ""
#echo "🛑 Stopping Web UI..."
#if [ -f "stop_webui.sh" ]; then
#    chmod +x stop_webui.sh
#    ./stop_webui.sh
#fi

# Dừng WARP Monitor
echo ""
echo "🛑 Stopping WARP Monitor..."
if [ -f "services/haproxy_7890/warp_monitor.sh" ]; then
    cd services/haproxy_7890
    ./warp_monitor.sh stop 2>/dev/null || true
    cd ../..
fi

# Dừng Gost Monitor
echo ""
echo "🛑 Stopping Gost Monitor..."
if [ -f "gost_monitor.sh" ]; then
    chmod +x gost_monitor.sh
    ./gost_monitor.sh stop 2>/dev/null || true
fi

# Dừng Gost
echo ""
echo "🛑 Stopping gost instances..."
if [ -f "manage_gost.sh" ]; then
    chmod +x manage_gost.sh
    ./manage_gost.sh stop
fi


# Health monitors removed - Gost runs directly

# HAProxy removed - Gost now runs directly on public ports
# Cleanup any remaining processes
pkill -f "gost.*socks5" 2>/dev/null || true

sleep 1

# Verify
echo ""
echo "🔍 Verifying shutdown..."
still_running=false

if pgrep -f "gost.*socks5" > /dev/null; then
    echo "⚠️  Some Gost processes still running"
    still_running=true
fi

if [ "$still_running" = true ]; then
    echo ""
    echo "💡 Use force kill: pkill -9 -f gost"
else
    echo "✅ All processes stopped successfully"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ System stopped"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

