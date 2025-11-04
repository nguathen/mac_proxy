#!/usr/bin/env bash
# uninstall_haproxy7890_autostart.sh
# Gỡ cài đặt autostart cho HAProxy 7890

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PLIST_FILE="com.macproxy.haproxy7890.plist"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
LAUNCHD_FILE="$LAUNCHD_DIR/$PLIST_FILE"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗑️  Gỡ cài đặt autostart cho HAProxy 7890"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Unload service
if [ -f "$LAUNCHD_FILE" ]; then
    echo "🛑 Dừng service..."
    launchctl unload "$LAUNCHD_FILE" 2>/dev/null || true
    sleep 1
    
    echo "🗑️  Xóa plist file..."
    rm -f "$LAUNCHD_FILE"
    
    echo "✅ Đã gỡ cài đặt autostart cho HAProxy 7890"
else
    echo "⚠️  Service chưa được cài đặt"
fi

