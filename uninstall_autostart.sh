#!/usr/bin/env bash
# uninstall_autostart.sh
# Gỡ cài đặt auto start

set -euo pipefail

PLIST_NAME="com.macproxy.startup.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗑️  Gỡ cài đặt Auto Start"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Unload service (dùng bootout cho macOS mới)
if launchctl list | grep -q "$PLIST_NAME"; then
    echo "🛑 Dừng service..."
    launchctl bootout "gui/$(id -u)/$PLIST_NAME" 2>/dev/null || \
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# Remove plist file
if [ -f "$PLIST_DEST" ]; then
    echo "🗑️  Xóa plist file..."
    rm -f "$PLIST_DEST"
fi

# Gỡ cài đặt Gost Monitor autostart
echo ""
echo "🛡️  Gỡ cài đặt Gost Monitor autostart..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/uninstall_gostmonitor_autostart.sh" ]; then
    chmod +x "$SCRIPT_DIR/uninstall_gostmonitor_autostart.sh"
    "$SCRIPT_DIR/uninstall_gostmonitor_autostart.sh" 2>/dev/null || true
fi

# Verify
if launchctl list | grep -q "com.macproxy.startup"; then
    echo ""
    echo "❌ Gỡ cài đặt thất bại"
    echo "   Service vẫn còn chạy"
    exit 1
else
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ Auto start đã được gỡ cài đặt"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
fi

