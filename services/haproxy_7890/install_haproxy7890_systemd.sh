#!/usr/bin/env bash
# install_haproxy7890_systemd.sh
# Cài đặt systemd service cho HAProxy 7890 trên Linux

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVICE_NAME="haproxy-7890.service"
SERVICE_FILE="$SCRIPT_DIR/$SERVICE_NAME"
SYSTEMD_DIR="/etc/systemd/system"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Cài đặt Systemd Service cho HAProxy 7890"
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
if systemctl is-active --quiet haproxy-7890.service 2>/dev/null; then
    echo "🛑 Dừng service cũ..."
    systemctl stop haproxy-7890.service || true
fi

# Copy service file
echo "📋 Copy service file..."
cp "$SERVICE_FILE" "$SYSTEMD_DIR/$SERVICE_NAME"

# Reload systemd
echo "🔄 Reload systemd daemon..."
systemctl daemon-reload

# Enable service
echo "✅ Enable service..."
systemctl enable haproxy-7890.service

# Start service
echo "🚀 Start service..."
systemctl start haproxy-7890.service

# Verify
sleep 3
if systemctl is-active --quiet haproxy-7890.service; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ HAProxy 7890 systemd service đã được cài đặt thành công!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📝 Thông tin:"
    echo "   • Service sẽ tự động khởi động khi boot"
    echo "   • Service file: $SYSTEMD_DIR/$SERVICE_NAME"
    echo "   • Logs: $SCRIPT_DIR/logs/haproxy_7890.log"
    echo "   • SOCKS5 Proxy: socks5://0.0.0.0:7890"
    echo "   • Backend: Cloudflare WARP (127.0.0.1:8111)"
    echo ""
    echo "🔧 Lệnh quản lý:"
    echo "   • Kiểm tra status: systemctl status haproxy-7890"
    echo "   • Xem logs: journalctl -u haproxy-7890 -f"
    echo "   • Xem logs file: tail -f $SCRIPT_DIR/logs/haproxy_7890.log"
    echo "   • Stop service: systemctl stop haproxy-7890"
    echo "   • Start service: systemctl start haproxy-7890"
    echo "   • Restart service: systemctl restart haproxy-7890"
    echo "   • Disable autostart: systemctl disable haproxy-7890"
    echo ""
    echo "🧪 Test proxy:"
    echo "   curl -x socks5h://127.0.0.1:7890 https://api.ipify.org"
    echo ""
else
    echo "❌ Service không chạy. Kiểm tra logs:"
    echo "   journalctl -u haproxy-7890 -n 50"
    exit 1
fi

