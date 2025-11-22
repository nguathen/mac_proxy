#!/usr/bin/env bash
# start_all.sh
# Khởi động Gost proxy services

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Starting Gost Proxy System"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Tạo thư mục cần thiết
mkdir -p config logs

# Kiểm tra Gost
if ! command -v gost &> /dev/null; then
    # Thử tìm trong thư mục bin local
    if [ -f "$SCRIPT_DIR/bin/gost" ]; then
        export PATH="$SCRIPT_DIR/bin:$PATH"
        echo "✅ Sử dụng Gost từ thư mục bin local"
    else
        echo "❌ Gost chưa được cài đặt"
        echo "   Chạy: brew install gost"
        exit 1
    fi
fi

# Đảm bảo config cho port 7890 tồn tại (WARP service)
echo ""
echo "🛡️  Ensuring Gost 7890 config exists..."
mkdir -p config
if [ ! -f "config/gost_7890.config" ]; then
    cat > config/gost_7890.config <<EOF
{
    "port": "7890",
    "provider": "warp",
    "country": "cloudflare",
    "proxy_url": "socks5://127.0.0.1:8111",
    "proxy_host": "127.0.0.1",
    "proxy_port": "8111",
    "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
    echo "✅ Gost 7890 config created"
fi

# Khởi động Gost
echo ""
echo "🔐 Starting Gost instances..."
chmod +x manage_gost.sh

# Cấu hình mặc định nếu chưa có
echo "📋 Checking gost configurations..."
if [ ! -f "config/gost_7891.config" ]; then
    echo "   ⚠️  No default configuration found for instance 7891"
    echo "   💡 Bạn có thể cấu hình qua Web UI tại http://localhost:5000"
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


# Khởi động Gost Monitor
echo ""
echo "🛡️  Starting Gost 7890 Monitor..."
if [ -f "gost_7890_monitor.sh" ]; then
    chmod +x gost_7890_monitor.sh
    ./gost_7890_monitor.sh start 2>/dev/null || true
    echo "✅ Gost 7890 Monitor started"
else
    echo "⚠️  Gost 7890 Monitor script not found"
fi

echo ""
echo "🛡️  Starting Gost Monitor..."
if [ -f "gost_monitor.sh" ]; then
    chmod +x gost_monitor.sh
    ./gost_monitor.sh start 2>/dev/null || true
    echo "✅ Gost Monitor started"
else
    echo "⚠️  Gost Monitor script not found"
fi

# Hiển thị trạng thái
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Hệ thống đã khởi động"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Thông tin proxy:"
for config_file in config/gost_*.config; do
    if [ -f "$config_file" ]; then
        port=$(basename "$config_file" .config | sed 's/gost_//')
        echo "   • Gost $port (SOCKS5): socks5://0.0.0.0:$port"
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
echo "🛡️  Gost Monitor:"
echo "   • Tự động kiểm tra và restart gost khi connection fail"
echo "   • Check interval: 10 giây (restart sau 2 lần thất bại)"
echo "   • Log: logs/gost_monitor.log"
echo ""
echo "📝 Lệnh hữu ích:"
echo "   • Kiểm tra trạng thái: ./status_all.sh"
echo "   • Dừng hệ thống: ./stop_all.sh"
echo "   • Xem logs: tail -f logs/gost_*.log"
for config_file in config/gost_*.config; do
    if [ -f "$config_file" ]; then
        port=$(basename "$config_file" .config | sed 's/gost_//')
        echo "   • Test SOCKS5 proxy $port: curl -x socks5h://127.0.0.1:$port https://api.ipify.org"
    fi
done
echo ""

