#!/usr/bin/env bash
# uninstall_gostmonitor_autostart.sh
# Gỡ cài đặt auto start cho Gost Monitor

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PLIST_NAME="com.macproxy.gostmonitor.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗑️  Gỡ cài đặt Gost Monitor Auto Start"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Stop monitor nếu đang chạy
if [ -f "$SCRIPT_DIR/gost_monitor.sh" ]; then
    echo "🛑 Dừng Gost Monitor..."
    chmod +x "$SCRIPT_DIR/gost_monitor.sh"
    "$SCRIPT_DIR/gost_monitor.sh" stop 2>/dev/null || true
fi

# Unload service (dùng bootout cho macOS mới)
if launchctl list | grep -q "$PLIST_NAME" || \
   launchctl print "gui/$(id -u)/$PLIST_NAME" &>/dev/null 2>&1; then
    echo "🛑 Unload service..."
    launchctl bootout "gui/$(id -u)/$PLIST_NAME" 2>/dev/null || \
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# Remove plist file
if [ -f "$PLIST_DEST" ]; then
    echo "🗑️  Xóa plist file..."
    rm -f "$PLIST_DEST"
fi

# Verify
if launchctl list | grep -q "com.macproxy.gostmonitor" || \
   launchctl print "gui/$(id -u)/com.macproxy.gostmonitor" &>/dev/null 2>&1; then
    echo ""
    echo "⚠️  Service vẫn còn trong launchctl, thử logout/login lại"
else
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ Gost Monitor auto start đã được gỡ cài đặt"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
fi

