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

# Khởi động Gost
echo ""
echo "🔐 Starting Gost instances..."
chmod +x manage_gost.sh

# Cấu hình mặc định nếu chưa có
echo "📋 Checking gost configurations..."
if [ ! -f "config/gost_18181.config" ]; then
    echo "   Setting up default configuration for instance 18181..."
    ./manage_gost.sh config 18181 protonvpn "node-uk-29.protonvpn.net" "node-uk-29.protonvpn.net" "4443"
fi

./manage_gost.sh start


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
for config_file in config/haproxy_*.cfg; do
    if [ -f "$config_file" ]; then
        port=$(basename "$config_file" .cfg | sed 's/haproxy_//')
        pkill -f "setup_haproxy.sh.*--sock-port $port" || true
    fi
done
sleep 2

# Tự động quét và khởi động các HAProxy instances có config
echo ""
echo "🔍 Scanning for HAProxy config files..."
chmod +x setup_haproxy.sh

# Quét tất cả file config haproxy_*.cfg
for config_file in config/haproxy_*.cfg; do
    if [ -f "$config_file" ]; then
        # Trích xuất port từ tên file (haproxy_7891.cfg -> 7891)
        port=$(basename "$config_file" .cfg | sed 's/haproxy_//')
        stats_port=$((port + 200))
        
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "🚀 Starting HAProxy Instance (Port: $port)"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        # Tạo gost ports dựa trên port (7891 -> 18181, 7892 -> 18182, etc.)
        gost_port=$((port - 6000))
        
        ./setup_haproxy.sh \
          --sock-port "$port" \
          --stats-port "$stats_port" \
          --gost-ports "$gost_port" \
          --host-proxy 127.0.0.1:8111 \
          --stats-auth admin:admin123 \
          --health-interval 10 \
          --daemon
        
        sleep 2
    fi
done

# Kiểm tra nếu không có config nào
if [ ! -f config/haproxy_*.cfg ]; then
    echo ""
    echo "⚠️  No HAProxy config files found in config/ directory"
    echo "   Create config files like: config/haproxy_7891.cfg, config/haproxy_7892.cfg, etc."
fi

# Khởi động Auto Credential Updater
echo ""
echo "🔄 Starting Auto Credential Updater..."
chmod +x start_auto_updater.sh
./start_auto_updater.sh start

# Khởi động Web UI
echo ""
echo "🌐 Starting Web UI..."
chmod +x start_webui_daemon.sh
./start_webui_daemon.sh

# Hiển thị trạng thái
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Hệ thống đã khởi động"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Thông tin proxy:"
for config_file in config/haproxy_*.cfg; do
    if [ -f "$config_file" ]; then
        port=$(basename "$config_file" .cfg | sed 's/haproxy_//')
        echo "   • HAProxy $port (SOCKS5): socks5://0.0.0.0:$port"
    fi
done
echo ""
echo "📈 HAProxy Stats:"
for config_file in config/haproxy_*.cfg; do
    if [ -f "$config_file" ]; then
        port=$(basename "$config_file" .cfg | sed 's/haproxy_//')
        stats_port=$((port + 200))
        echo "   • Instance $port: http://0.0.0.0:$stats_port/haproxy?stats"
    fi
done
echo "   • Auth: admin:admin123"
echo ""
echo "🔄 Cấu trúc fallback:"
for config_file in config/haproxy_*.cfg; do
    if [ -f "$config_file" ]; then
        port=$(basename "$config_file" .cfg | sed 's/haproxy_//')
        gost_port=$((port - 6000))
        echo "   • HAProxy $port: Wiresock $gost_port → Cloudflare WARP 8111"
    fi
done
echo ""
echo "🌐 Web UI:"
echo "   • URL: http://127.0.0.1:5000"
echo "   • Quản lý toàn bộ hệ thống qua giao diện web"
echo ""
echo "🔄 Auto Credential Updater:"
echo "   • Tự động cập nhật credentials mỗi 30 giây"
echo "   • Tự động dọn dẹp services không sử dụng mỗi 5 phút"
echo "   • Log: logs/auto_updater.log"
echo ""
echo "📝 Lệnh hữu ích:"
echo "   • Kiểm tra trạng thái: ./status_all.sh"
echo "   • Dừng hệ thống: ./stop_all.sh"
echo "   • Xem logs: tail -f logs/haproxy_health_*.log"
for config_file in config/haproxy_*.cfg; do
    if [ -f "$config_file" ]; then
        port=$(basename "$config_file" .cfg | sed 's/haproxy_//')
        echo "   • Test SOCKS5 proxy $port: curl -x socks5h://127.0.0.1:$port https://api.ipify.org"
    fi
done
echo ""

