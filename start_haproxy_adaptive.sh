#!/usr/bin/env bash
# start_haproxy_adaptive.sh
# Khởi động HAProxy instances dựa trên wireproxy có sẵn

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Starting HAProxy Instances (Adaptive Mode)"
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

# Function để kiểm tra wireproxy có sẵn không
check_wireproxy() {
    local port=$1
    if nc -z 127.0.0.1 "$port" 2>/dev/null; then
        return 0  # Wireproxy đang chạy
    fi
    return 1  # Wireproxy không chạy
}

# Function để khởi động service
start_instance() {
    local sock_port=$1
    local stats_port=$2
    local wg_port=$3
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🚀 Starting HAProxy Service (Port $sock_port)"
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

# Dynamic discovery: Check gost config files and start corresponding HAProxy services
echo "🔍 Checking available gost services..."

for config_file in ./config/gost_*.config; do
    if [ -f "$config_file" ]; then
        # Extract port from config file name
        gost_port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
        
        # Calculate corresponding HAProxy port (gost_port - 10000)
        haproxy_port=$((gost_port - 10000))
        stats_port=$((haproxy_port + 200))
        
        echo "📋 Found gost config for port $gost_port, checking availability..."
        
        # Check if gost service is available (check if port is listening)
        if check_wireproxy $gost_port; then
            echo "✅ Gost $gost_port is available"
            if check_instance $haproxy_port; then
                echo "✅ HAProxy $haproxy_port already running"
            else
                echo "🔄 Starting HAProxy $haproxy_port (for gost $gost_port)..."
                start_instance $haproxy_port $stats_port $gost_port
            fi
        else
            echo "❌ Gost $gost_port not available (port not listening)"
        fi
    fi
done

# Hiển thị trạng thái cuối
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ HAProxy startup completed"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Current Status:"

# Kiểm tra trạng thái cuối cùng dựa trên config files
for config_file in ./config/gost_*.config; do
    if [ -f "$config_file" ]; then
        gost_port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
        haproxy_port=$((gost_port - 10000))
        
        if check_instance "$haproxy_port"; then
            echo "   ✅ HAProxy $haproxy_port: Running (gost $gost_port)"
        else
            echo "   ❌ HAProxy $haproxy_port: Not running (gost $gost_port)"
        fi
    fi
done

echo ""
echo "📈 HAProxy Stats:"
for config_file in ./config/gost_*.config; do
    if [ -f "$config_file" ]; then
        gost_port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
        haproxy_port=$((gost_port - 10000))
        stats_port=$((haproxy_port + 200))
        echo "   • HAProxy $haproxy_port: http://0.0.0.0:$stats_port/haproxy?stats"
    fi
done
echo "   • Auth: admin:admin123"
echo ""
echo "📝 Test Commands:"
for config_file in ./config/gost_*.config; do
    if [ -f "$config_file" ]; then
        gost_port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
        haproxy_port=$((gost_port - 10000))
        echo "   • Test $haproxy_port: curl -x socks5h://127.0.0.1:$haproxy_port https://api.ipify.org"
    fi
done
echo ""
