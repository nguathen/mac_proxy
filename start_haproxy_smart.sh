#!/usr/bin/env bash
# start_haproxy_smart.sh
# Khởi động HAProxy instances một cách thông minh - chỉ khởi động những instance chưa có

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Starting HAProxy Instances (Smart Mode)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Tạo thư mục cần thiết
mkdir -p config logs

# Kiểm tra HAProxy
if ! command -v haproxy &> /dev/null; then
    echo "❌ HAProxy chưa được cài đặt"
    echo "   Chạy: brew install haproxy"
    exit 1
fi

# Function để kiểm tra instance có đang chạy không
check_instance() {
    local port=$1
    local pid_file="logs/haproxy_${port}.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            # Kiểm tra port có đang listen không
            if nc -z 127.0.0.1 "$port" 2>/dev/null; then
                return 0  # Instance đang chạy
            fi
        fi
    fi
    return 1  # Instance không chạy
}

# Function để khởi động instance
start_instance() {
    local sock_port=$1
    local stats_port=$2
    local wg_port=$3
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🚀 Starting HAProxy Instance (Port $sock_port)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    chmod +x setup_haproxy.sh
    ./setup_haproxy.sh \
      --sock-port "$sock_port" \
      --stats-port "$stats_port" \
      --wg-ports "$wg_port" \
      --host-proxy 127.0.0.1:8111 \
      --stats-auth admin:admin123 \
      --health-interval 10 \
      --daemon
    
    sleep 2
}

# Kiểm tra và khởi động Instance 1 (7891)
if check_instance 7891; then
    echo "✅ HAProxy Instance 1 (port 7891) already running"
else
    echo "🔄 Starting HAProxy Instance 1 (port 7891)..."
    start_instance 7891 8091 18181
fi

# Kiểm tra và khởi động Instance 2 (7892)
if check_instance 7892; then
    echo "✅ HAProxy Instance 2 (port 7892) already running"
else
    echo "🔄 Starting HAProxy Instance 2 (port 7892)..."
    start_instance 7892 8092 18182
fi

# Hiển thị trạng thái cuối
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ HAProxy startup completed"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Current Status:"

# Kiểm tra trạng thái cuối cùng
for port in 7891 7892; do
    if check_instance "$port"; then
        echo "   ✅ HAProxy $port: Running"
    else
        echo "   ❌ HAProxy $port: Not running"
    fi
done

echo ""
echo "📈 HAProxy Stats:"
echo "   • Instance 1: http://0.0.0.0:8091/haproxy?stats"
echo "   • Instance 2: http://0.0.0.0:8092/haproxy?stats"
echo "   • Auth: admin:admin123"
echo ""
echo "📝 Test Commands:"
echo "   • Test 7891: curl -x socks5h://127.0.0.1:7891 https://api.ipify.org"
echo "   • Test 7892: curl -x socks5h://127.0.0.1:7892 https://api.ipify.org"
echo ""
