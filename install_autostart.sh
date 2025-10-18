#!/usr/bin/env bash
# install_autostart.sh
# Cài đặt auto start cho hệ thống proxy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PLIST_NAME="com.macproxy.startup.plist"
PLIST_SOURCE="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Cài đặt Auto Start cho Mac Proxy"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Tạo thư mục LaunchAgents nếu chưa có
mkdir -p "$HOME/Library/LaunchAgents"

# Tạo thư mục logs nếu chưa có
mkdir -p "$SCRIPT_DIR/logs"

# Unload service cũ nếu có
if launchctl list | grep -q "$PLIST_NAME"; then
    echo "🛑 Dừng service cũ..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# Copy plist file
echo "📋 Copy plist file..."
cp "$PLIST_SOURCE" "$PLIST_DEST"

# Load service
echo "🔄 Load service..."
launchctl load "$PLIST_DEST"

# Verify
if launchctl list | grep -q "com.macproxy.startup"; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ Auto start đã được cài đặt thành công!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📝 Thông tin:"
    echo "   • Service sẽ tự động khởi động khi đăng nhập"
    echo "   • Plist file: $PLIST_DEST"
    echo "   • Logs: $SCRIPT_DIR/logs/launchd.log"
    echo ""
    echo "🔧 Lệnh quản lý:"
    echo "   • Kiểm tra status: launchctl list | grep macproxy"
    echo "   • Xem logs: tail -f $SCRIPT_DIR/logs/launchd.log"
    echo "   • Gỡ cài đặt: ./uninstall_autostart.sh"
    echo "   • Start ngay: launchctl start com.macproxy.startup"
    echo ""
else
    echo ""
    echo "❌ Cài đặt thất bại"
    echo "   Kiểm tra logs: tail -f $SCRIPT_DIR/logs/launchd.error.log"
    exit 1
fi

