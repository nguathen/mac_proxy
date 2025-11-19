#!/usr/bin/env bash
# install_systemd_main.sh
# Cài đặt systemd service chính cho Mac Proxy System trên Linux

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVICE_NAME="mac-proxy.service"
SERVICE_FILE="$SCRIPT_DIR/$SERVICE_NAME"
SYSTEMD_DIR="/etc/systemd/system"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Cài đặt Systemd Service chính cho Mac Proxy System"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Kiểm tra quyền root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Script này cần quyền root. Vui lòng chạy với sudo."
    exit 1
fi

# Kiểm tra service file tồn tại
if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ Service file không tìm thấy: $SERVICE_FILE"
    exit 1
fi

# Tạo thư mục logs nếu chưa có
mkdir -p "$SCRIPT_DIR/logs"

# Cập nhật đường dẫn trong service file
TEMP_SERVICE="/tmp/${SERVICE_NAME}.tmp"
sed "s|/project_proxy/mac_proxy|$SCRIPT_DIR|g" "$SERVICE_FILE" > "$TEMP_SERVICE"

# Stop service cũ nếu đang chạy
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "🛑 Dừng service cũ..."
    systemctl stop "$SERVICE_NAME" || true
fi

# Disable service cũ nếu đã enable
if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "🔄 Disable service cũ..."
    systemctl disable "$SERVICE_NAME" || true
fi

# Copy service file
echo "📋 Copy service file..."
cp "$TEMP_SERVICE" "$SYSTEMD_DIR/$SERVICE_NAME"
rm -f "$TEMP_SERVICE"

# Reload systemd
echo "🔄 Reload systemd daemon..."
systemctl daemon-reload

# Enable service
echo "✅ Enable service..."
systemctl enable "$SERVICE_NAME"

# Start service
echo "🚀 Start service..."
systemctl start "$SERVICE_NAME"

# Verify
sleep 3
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ Mac Proxy System systemd service đã được cài đặt thành công!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📝 Thông tin:"
    echo "   • Service sẽ tự động khởi động khi boot"
    echo "   • Service file: $SYSTEMD_DIR/$SERVICE_NAME"
    echo "   • Logs: $SCRIPT_DIR/logs/systemd.log"
    echo ""
    echo "🔧 Lệnh quản lý:"
    echo "   • Kiểm tra status: systemctl status mac-proxy"
    echo "   • Xem logs: journalctl -u mac-proxy -f"
    echo "   • Xem logs file: tail -f $SCRIPT_DIR/logs/systemd.log"
    echo "   • Stop service: systemctl stop mac-proxy"
    echo "   • Start service: systemctl start mac-proxy"
    echo "   • Restart service: systemctl restart mac-proxy"
    echo "   • Disable autostart: systemctl disable mac-proxy"
    echo ""
else
    echo ""
    echo "⚠️  Service không chạy ngay. Kiểm tra logs:"
    echo "   journalctl -u mac-proxy -n 50"
    echo "   tail -f $SCRIPT_DIR/logs/systemd.log"
    echo ""
    echo "💡 Service có thể đang khởi động. Kiểm tra lại sau vài giây:"
    echo "   systemctl status mac-proxy"
fi

