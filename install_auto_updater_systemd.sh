#!/usr/bin/env bash
# install_auto_updater_systemd.sh
# Cài đặt systemd service cho Auto Credential Updater trên Linux

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVICE_NAME="auto-credential-updater.service"
SERVICE_FILE="$SCRIPT_DIR/$SERVICE_NAME"
SYSTEMD_DIR="/etc/systemd/system"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄 Cài đặt Systemd Service cho Auto Credential Updater"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Kiểm tra quyền root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Script này cần quyền root. Vui lòng chạy với sudo."
    exit 1
fi

# Tạo thư mục logs nếu chưa có
mkdir -p "$SCRIPT_DIR/logs"

# Stop service cũ nếu đang chạy
if systemctl is-active --quiet auto-credential-updater.service 2>/dev/null; then
    echo "🛑 Dừng service cũ..."
    systemctl stop auto-credential-updater.service || true
fi

# Copy service file
echo "📋 Copy service file..."
cp "$SERVICE_FILE" "$SYSTEMD_DIR/$SERVICE_NAME"

# Reload systemd
echo "🔄 Reload systemd daemon..."
systemctl daemon-reload

# Enable service
echo "✅ Enable service..."
systemctl enable auto-credential-updater.service

# Start service
echo "🚀 Start service..."
systemctl start auto-credential-updater.service

# Verify
sleep 2
if systemctl is-active --quiet auto-credential-updater.service; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ Auto Credential Updater systemd service đã được cài đặt thành công!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📝 Thông tin:"
    echo "   • Service sẽ tự động khởi động khi boot"
    echo "   • Service file: $SYSTEMD_DIR/$SERVICE_NAME"
    echo "   • Logs: $SCRIPT_DIR/logs/auto_updater.log"
    echo ""
    echo "🔧 Chức năng:"
    echo "   • Tự động cập nhật ProtonVPN credentials mỗi 30 giây"
    echo "   • Tự động dọn dẹp Gost services không sử dụng mỗi 5 phút"
    echo ""
    echo "🔧 Lệnh quản lý:"
    echo "   • Kiểm tra status: systemctl status auto-credential-updater"
    echo "   • Xem logs: journalctl -u auto-credential-updater -f"
    echo "   • Xem logs file: tail -f $SCRIPT_DIR/logs/auto_updater.log"
    echo "   • Stop service: systemctl stop auto-credential-updater"
    echo "   • Start service: systemctl start auto-credential-updater"
    echo "   • Restart service: systemctl restart auto-credential-updater"
    echo "   • Disable autostart: systemctl disable auto-credential-updater"
    echo ""
else
    echo "❌ Service không chạy. Kiểm tra logs:"
    echo "   journalctl -u auto-credential-updater -n 50"
    exit 1
fi

