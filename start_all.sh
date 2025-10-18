#!/usr/bin/env bash
# start_all.sh
# Khởi động wireproxy và HAProxy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Starting HAProxy Multi-Instance System"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Tạo thư mục cần thiết
mkdir -p config logs

# Kiểm tra HAProxy
if ! command -v haproxy &> /dev/null; then
    echo "❌ HAProxy chưa được cài đặt"
    echo "   Chạy: brew install haproxy"
    exit 1
fi

# Khởi động Wireproxy
echo ""
echo "🔐 Starting Wireproxy instances..."
chmod +x manage_wireproxy.sh
./manage_wireproxy.sh start

# Kiểm tra Cloudflare WARP
echo ""
echo "🔍 Kiểm tra Cloudflare WARP..."
if ! nc -z 127.0.0.1 8111 2>/dev/null; then
    echo "⚠️  Cloudflare WARP proxy (port 8111) không hoạt động"
    echo "   Vui lòng cấu hình WARP:"
    echo "   warp-cli set-mode proxy"
    echo "   warp-cli set-proxy-port 8111"
    echo "   warp-cli connect"
else
    echo "✅ Cloudflare WARP proxy đang chạy (port 8111)"
fi

# Dừng các instance cũ nếu có
echo ""
echo "🛑 Dừng các HAProxy instance cũ..."
pkill -f "setup_haproxy.sh.*--sock-port 7891" || true
pkill -f "setup_haproxy.sh.*--sock-port 7892" || true
sleep 2

# Khởi động HAProxy Instance 1
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Starting HAProxy Instance 1"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
chmod +x setup_haproxy.sh
./setup_haproxy.sh \
  --sock-port 7891 \
  --stats-port 8091 \
  --wg-ports 18181 \
  --host-proxy 127.0.0.1:8111 \
  --stats-auth admin:admin123 \
  --health-interval 30 \
  --daemon

sleep 2

# Khởi động HAProxy Instance 2
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Starting HAProxy Instance 2"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
./setup_haproxy.sh \
  --sock-port 7892 \
  --stats-port 8092 \
  --wg-ports 18182 \
  --host-proxy 127.0.0.1:8111 \
  --stats-auth admin:admin123 \
  --health-interval 30 \
  --daemon

sleep 2

# Hiển thị trạng thái
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Hệ thống đã khởi động"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Thông tin proxy:"
echo "   • HAProxy 1: socks5://0.0.0.0:7891"
echo "   • HAProxy 2: socks5://0.0.0.0:7892"
echo ""
echo "📈 HAProxy Stats:"
echo "   • Instance 1: http://0.0.0.0:8091/haproxy?stats"
echo "   • Instance 2: http://0.0.0.0:8092/haproxy?stats"
echo "   • Auth: admin:admin123"
echo ""
echo "🔄 Cấu trúc fallback:"
echo "   • HAProxy 1: Wiresock 18181 → Cloudflare WARP 8111"
echo "   • HAProxy 2: Wiresock 18182 → Cloudflare WARP 8111"
echo ""
echo "📝 Lệnh hữu ích:"
echo "   • Kiểm tra trạng thái: ./status_all.sh"
echo "   • Dừng hệ thống: ./stop_all.sh"
echo "   • Xem logs: tail -f logs/haproxy_health_*.log"
echo "   • Test proxy 1: curl -x socks5h://127.0.0.1:7891 https://api.ipify.org"
echo "   • Test proxy 2: curl -x socks5h://127.0.0.1:7892 https://api.ipify.org"
echo ""

