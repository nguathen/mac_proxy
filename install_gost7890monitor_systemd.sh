#!/usr/bin/env bash
# install_gost7890monitor_systemd.sh
# Cài đặt systemd service cho Gost 7890 Monitor trên Linux

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVICE_NAME="gost-7890-monitor.service"
SERVICE_FILE="$SCRIPT_DIR/$SERVICE_NAME"
SYSTEMD_DIR="/etc/systemd/system"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Cài đặt Systemd Service cho Gost 7890 Monitor"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Kiểm tra quyền root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Script này cần quyền root. Vui lòng chạy với sudo."
    exit 1
fi

# Tạo thư mục logs nếu chưa có
mkdir -p "$SCRIPT_DIR/logs"
mkdir -p "$SCRIPT_DIR/config"

# Stop service cũ nếu đang chạy
if systemctl is-active --quiet gost-7890-monitor.service 2>/dev/null; then
    echo "🛑 Dừng service cũ..."
    systemctl stop gost-7890-monitor.service || true
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
systemctl enable gost-7890-monitor.service

# Start service
echo "🚀 Start service..."
systemctl start gost-7890-monitor.service

# Verify
sleep 3
if systemctl is-active --quiet gost-7890-monitor.service; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ Gost 7890 Monitor systemd service đã được cài đặt thành công!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📝 Thông tin:"
    echo "   • Service sẽ tự động khởi động khi boot"
    echo "   • Service file: $SYSTEMD_DIR/$SERVICE_NAME"
    echo "   • Logs: $SCRIPT_DIR/logs/gost_7890_monitor.log"
    echo "   • SOCKS5 Proxy: socks5://0.0.0.0:7890"
    echo "   • Backend: Cloudflare WARP (127.0.0.1:8111)"
    echo ""
    echo "🔧 Lệnh quản lý:"
    echo "   • Kiểm tra status: systemctl status gost-7890-monitor"
    echo "   • Xem logs: journalctl -u gost-7890-monitor -f"
    echo "   • Xem logs file: tail -f $SCRIPT_DIR/logs/gost_7890_monitor.log"
    echo "   • Stop service: systemctl stop gost-7890-monitor"
    echo "   • Start service: systemctl start gost-7890-monitor"
    echo "   • Restart service: systemctl restart gost-7890-monitor"
    echo "   • Disable autostart: systemctl disable gost-7890-monitor"
    echo ""
    echo "🧪 Test proxy:"
    echo "   curl -x socks5h://127.0.0.1:7890 https://ipinfo.io/ip"
    echo ""
else
    echo "❌ Service không chạy. Kiểm tra logs:"
    echo "   journalctl -u gost-7890-monitor -n 50"
    exit 1
fi

