#!/usr/bin/env bash
# uninstall_autostart.sh
# Gỡ cài đặt auto start

set -euo pipefail

PLIST_NAME="com.macproxy.startup.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗑️  Gỡ cài đặt Auto Start"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Unload service
if launchctl list | grep -q "$PLIST_NAME"; then
    echo "🛑 Dừng service..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# Remove plist file
if [ -f "$PLIST_DEST" ]; then
    echo "🗑️  Xóa plist file..."
    rm -f "$PLIST_DEST"
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

