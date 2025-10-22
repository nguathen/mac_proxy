#!/usr/bin/env bash
# start_haproxy_only.sh
# Chỉ khởi động HAProxy instances, không khởi động Web UI

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Starting HAProxy Instances Only"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Tạo thư mục cần thiết
mkdir -p config logs

# Kiểm tra HAProxy
if ! command -v haproxy &> /dev/null; then
    echo "❌ HAProxy chưa được cài đặt"
    echo "   Chạy: brew install haproxy"
    exit 1
fi

# Dynamic discovery: Start HAProxy services based on gost config files
echo ""
echo "🔍 Checking for gost config files to start corresponding HAProxy services..."

# Dừng các instance cũ nếu có
echo "🛑 Stopping existing HAProxy services..."
pkill -f "setup_haproxy.sh" || true
sleep 2

chmod +x setup_haproxy.sh

for config_file in ./logs/gost_*.config; do
    if [ -f "$config_file" ]; then
        # Extract port from config file name
        gost_port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
        
        # Calculate corresponding HAProxy port (gost_port - 10000)
        haproxy_port=$((gost_port - 10000))
        stats_port=$((haproxy_port + 200))
        
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "🚀 Starting HAProxy Service (Port $haproxy_port)"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        ./setup_haproxy.sh \
          --sock-port $haproxy_port \
          --stats-port $stats_port \
          --gost-ports $gost_port \
          --host-proxy 127.0.0.1:8111 \
          --stats-auth admin:admin123 \
          --health-interval 10 \
          --daemon
        
        sleep 2
    fi
done

sleep 2

# Hiển thị trạng thái
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ HAProxy instances đã khởi động"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Thông tin proxy:"
for config_file in ./logs/gost_*.config; do
    if [ -f "$config_file" ]; then
        gost_port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
        haproxy_port=$((gost_port - 10000))
        echo "   • HAProxy $haproxy_port (SOCKS5): socks5://0.0.0.0:$haproxy_port"
    fi
done
echo ""
echo "📈 HAProxy Stats:"
for config_file in ./logs/gost_*.config; do
    if [ -f "$config_file" ]; then
        gost_port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
        haproxy_port=$((gost_port - 10000))
        stats_port=$((haproxy_port + 200))
        echo "   • HAProxy $haproxy_port: http://0.0.0.0:$stats_port/haproxy?stats"
    fi
done
echo "   • Auth: admin:admin123"
echo ""
echo "🔄 Cấu trúc fallback:"
for config_file in ./logs/gost_*.config; do
    if [ -f "$config_file" ]; then
        gost_port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
        haproxy_port=$((gost_port - 10000))
        echo "   • HAProxy $haproxy_port: Gost $gost_port → Cloudflare WARP 8111"
    fi
done
echo ""
echo "📝 Lệnh hữu ích:"
echo "   • Kiểm tra trạng thái: ./status_all.sh"
echo "   • Dừng HAProxy: ./stop_haproxy_only.sh"
echo "   • Xem logs: tail -f logs/haproxy_health_*.log"
echo "   • Test Commands:"
for config_file in ./logs/gost_*.config; do
    if [ -f "$config_file" ]; then
        gost_port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
        haproxy_port=$((gost_port - 10000))
        echo "     - Test $haproxy_port: curl -x socks5h://127.0.0.1:$haproxy_port https://api.ipify.org"
    fi
done
echo ""
