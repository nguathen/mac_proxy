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

# Unload service cũ nếu có (dùng bootout cho macOS mới)
if launchctl list | grep -q "$PLIST_NAME"; then
    echo "🛑 Dừng service cũ..."
    launchctl bootout "gui/$(id -u)/$PLIST_NAME" 2>/dev/null || \
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
fi

# Copy plist file
echo "📋 Copy plist file..."
cp "$PLIST_SOURCE" "$PLIST_DEST"

# Load service (dùng bootstrap cho macOS mới)
echo "🔄 Load service..."
if launchctl bootstrap "gui/$(id -u)" "$PLIST_DEST" 2>/dev/null; then
    echo "✅ Service đã được load bằng launchctl bootstrap"
elif launchctl load "$PLIST_DEST" 2>/dev/null; then
    echo "✅ Service đã được load bằng launchctl load (legacy)"
else
    echo "❌ Không thể load service"
    exit 1
fi

# Cài đặt Gost Monitor autostart
echo ""
echo "🛡️  Cài đặt Gost Monitor autostart..."
if [ -f "$SCRIPT_DIR/install_gostmonitor_autostart.sh" ]; then
    chmod +x "$SCRIPT_DIR/install_gostmonitor_autostart.sh"
    "$SCRIPT_DIR/install_gostmonitor_autostart.sh" 2>/dev/null || echo "⚠️  Gost Monitor autostart có thể đã được cài đặt"
else
    echo "⚠️  Gost Monitor install script not found"
fi

# Verify (kiểm tra file plist và service)
sleep 1
if [ -f "$PLIST_DEST" ]; then
    # Kiểm tra service đã được load chưa (thử nhiều cách)
    if launchctl list | grep -q "com.macproxy.startup" || \
       launchctl print "gui/$(id -u)/com.macproxy.startup" &>/dev/null || \
       launchctl print "gui/$(id -u)" 2>/dev/null | grep -q "com.macproxy.startup"; then
    # Thử start ngay để test
    echo "🧪 Testing service..."
    launchctl start "gui/$(id -u)/com.macproxy.startup" 2>/dev/null || \
    launchctl start "com.macproxy.startup" 2>/dev/null || true
    sleep 1
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
    echo "   • Start ngay: launchctl start gui/$(id -u)/com.macproxy.startup"
    echo "   • Bootout: launchctl bootout gui/$(id -u)/com.macproxy.startup"
    echo ""
    echo "⚠️  Lưu ý:"
    echo "   • LaunchAgent chỉ chạy khi bạn đăng nhập vào GUI"
    echo "   • Nếu muốn chạy khi system boot (trước login), cần dùng LaunchDaemon"
    echo ""
    else
        echo ""
        echo "⚠️  Service đã được load nhưng chưa xuất hiện trong list"
        echo "   Thử logout/login lại hoặc restart máy"
        echo ""
    fi
else
    echo ""
    echo "❌ Cài đặt thất bại"
    echo "   Plist file không được tạo"
    exit 1
fi

