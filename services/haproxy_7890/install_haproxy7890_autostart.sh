#!/usr/bin/env bash
# install_haproxy7890_autostart.sh
# Cài đặt autostart cho HAProxy 7890 trên macOS

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PLIST_FILE="com.macproxy.haproxy7890.plist"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
LAUNCHD_FILE="$LAUNCHD_DIR/$PLIST_FILE"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 Cài đặt autostart cho HAProxy 7890"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Kiểm tra file plist
if [ ! -f "$PLIST_FILE" ]; then
    echo "❌ Không tìm thấy file $PLIST_FILE"
    exit 1
fi

# Tạo thư mục LaunchAgents nếu chưa có
mkdir -p "$LAUNCHD_DIR"

# Unload service cũ nếu có
if [ -f "$LAUNCHD_FILE" ]; then
    echo "🛑 Dừng service cũ..."
    launchctl unload "$LAUNCHD_FILE" 2>/dev/null || true
    sleep 1
fi

# Copy file plist
echo "📋 Copy plist file..."
cp "$PLIST_FILE" "$LAUNCHD_FILE"

# Load service
echo "🚀 Khởi động service..."
launchctl load "$LAUNCHD_FILE"

sleep 2

# Kiểm tra trạng thái
if launchctl list | grep -q "com.macproxy.haproxy7890"; then
    echo "✅ Service đã được cài đặt và khởi động thành công"
    echo ""
    echo "📝 Thông tin service:"
    echo "   • Label: com.macproxy.haproxy7890"
    echo "   • Plist: $LAUNCHD_FILE"
    echo ""
    echo "🔧 Lệnh quản lý:"
    echo "   • Kiểm tra: launchctl list | grep haproxy7890"
    echo "   • Dừng: launchctl unload $LAUNCHD_FILE"
    echo "   • Khởi động lại: launchctl load $LAUNCHD_FILE"
    echo "   • Gỡ cài đặt: ./uninstall_haproxy7890_autostart.sh"
else
    echo "⚠️  Service đã được cài đặt nhưng có thể chưa khởi động"
    echo "   Kiểm tra log: tail -f $SCRIPT_DIR/logs/haproxy_7890_launchd.log"
fi

