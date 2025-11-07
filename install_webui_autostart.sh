#!/usr/bin/env bash
# install_webui_autostart.sh
# Cài đặt auto start cho Web UI

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PLIST_NAME="com.macproxy.webui.plist"
PLIST_SOURCE="$SCRIPT_DIR/$PLIST_NAME"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Cài đặt Auto Start cho Web UI"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Tạo thư mục LaunchAgents nếu chưa có
mkdir -p "$HOME/Library/LaunchAgents"

# Tạo thư mục logs nếu chưa có
mkdir -p "$SCRIPT_DIR/logs"

# Unload service cũ nếu có
if launchctl list | grep -q "$PLIST_NAME"; then
    echo "🛑 Dừng service cũ..."
    launchctl bootout "gui/$(id -u)/$PLIST_NAME" 2>/dev/null || \
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    sleep 1
fi

# Copy plist file
echo "📋 Copy plist file..."
cp "$PLIST_SOURCE" "$PLIST_DEST"

# Load service
echo "🔄 Load service..."
if launchctl bootstrap "gui/$(id -u)" "$PLIST_DEST" 2>/dev/null; then
    echo "✅ Service đã được load bằng launchctl bootstrap"
elif launchctl load "$PLIST_DEST" 2>/dev/null; then
    echo "✅ Service đã được load bằng launchctl load (legacy)"
else
    echo "❌ Không thể load service"
    exit 1
fi

# Verify
sleep 2
if [ -f "$PLIST_DEST" ]; then
    if launchctl list | grep -q "com.macproxy.webui" || \
       launchctl print "gui/$(id -u)/com.macproxy.webui" &>/dev/null; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "✅ Web UI auto start đã được cài đặt thành công!"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "📝 Thông tin:"
        echo "   • Service sẽ tự động khởi động khi đăng nhập"
        echo "   • Plist file: $PLIST_DEST"
        echo "   • Logs: $SCRIPT_DIR/logs/webui_launchd.log"
        echo "   • Web UI: http://127.0.0.1:5000"
        echo ""
        echo "🔧 Lệnh quản lý:"
        echo "   • Kiểm tra status: launchctl list | grep webui"
        echo "   • Xem logs: tail -f $SCRIPT_DIR/logs/webui_launchd.log"
        echo "   • Start ngay: launchctl start gui/$(id -u)/com.macproxy.webui"
        echo "   • Bootout: launchctl bootout gui/$(id -u)/com.macproxy.webui"
        echo ""
    else
        echo "⚠️  Service đã được load nhưng chưa xuất hiện trong list"
        echo "   Thử logout/login lại hoặc restart máy"
    fi
else
    echo "❌ Cài đặt thất bại"
    exit 1
fi

