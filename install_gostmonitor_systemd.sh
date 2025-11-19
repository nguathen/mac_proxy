#!/usr/bin/env bash
# install_gostmonitor_systemd.sh
# Cài đặt systemd service cho Gost Monitor trên Linux

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVICE_NAME="gost-monitor.service"
SERVICE_FILE="$SCRIPT_DIR/$SERVICE_NAME"
SYSTEMD_DIR="/etc/systemd/system"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🛡️  Cài đặt Systemd Service cho Gost Monitor"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Kiểm tra quyền root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Script này cần quyền root. Vui lòng chạy với sudo."
    exit 1
fi

# Tạo thư mục logs nếu chưa có
mkdir -p "$SCRIPT_DIR/logs"

# Stop service cũ nếu đang chạy
if systemctl is-active --quiet gost-monitor.service 2>/dev/null; then
    echo "🛑 Dừng service cũ..."
    systemctl stop gost-monitor.service || true
fi

# Copy service file và cập nhật đường dẫn
echo "📋 Copy service file..."
TEMP_SERVICE="/tmp/${SERVICE_NAME}.tmp"
sed "s|/project_proxy/mac_proxy|$SCRIPT_DIR|g" "$SERVICE_FILE" > "$TEMP_SERVICE"
cp "$TEMP_SERVICE" "$SYSTEMD_DIR/$SERVICE_NAME"
rm -f "$TEMP_SERVICE"

# Reload systemd
echo "🔄 Reload systemd daemon..."
systemctl daemon-reload

# Enable service
echo "✅ Enable service..."
systemctl enable gost-monitor.service

# Start service
echo "🚀 Start service..."
systemctl start gost-monitor.service

# Verify
sleep 2
if systemctl is-active --quiet gost-monitor.service; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ Gost Monitor systemd service đã được cài đặt thành công!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📝 Thông tin:"
    echo "   • Service sẽ tự động khởi động khi boot"
    echo "   • Service file: $SYSTEMD_DIR/$SERVICE_NAME"
    echo "   • Logs: $SCRIPT_DIR/logs/gost_monitor.log"
    echo ""
    echo "🔧 Lệnh quản lý:"
    echo "   • Kiểm tra status: systemctl status gost-monitor"
    echo "   • Xem logs: journalctl -u gost-monitor -f"
    echo "   • Xem logs file: tail -f $SCRIPT_DIR/logs/gost_monitor.log"
    echo "   • Stop service: systemctl stop gost-monitor"
    echo "   • Start service: systemctl start gost-monitor"
    echo "   • Restart service: systemctl restart gost-monitor"
    echo "   • Disable autostart: systemctl disable gost-monitor"
    echo ""
else
    echo "❌ Service không chạy. Kiểm tra logs:"
    echo "   journalctl -u gost-monitor -n 50"
    exit 1
fi

