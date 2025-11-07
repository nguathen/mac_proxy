#!/usr/bin/env bash
# start_haproxy_7890.sh
# Khởi động HAProxy port 7890 với backend Cloudflare WARP

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

HAPROXY_BIN="$(command -v haproxy || echo /opt/homebrew/sbin/haproxy)"
CFG_FILE="./config/haproxy_7890.cfg"
PID_FILE="./logs/haproxy_7890.pid"
LOG_DIR="./logs"

mkdir -p "$LOG_DIR" config

# Kiểm tra HAProxy
if ! command -v haproxy &> /dev/null && [ ! -f "/opt/homebrew/sbin/haproxy" ]; then
    echo "❌ HAProxy chưa được cài đặt"
    echo "   Chạy: brew install haproxy"
    exit 1
fi

# Kiểm tra và auto-reconnect Cloudflare WARP
echo "🔍 Kiểm tra Cloudflare WARP..."
warp_ok=false

# Kiểm tra WARP status và proxy functionality
if command -v warp-cli &> /dev/null; then
    if warp-cli status 2>/dev/null | grep -qi "connected" && \
       nc -z 127.0.0.1 8111 2>/dev/null && \
       curl -s --connect-timeout 3 --max-time 5 -x "socks5h://127.0.0.1:8111" https://api.ipify.org >/dev/null 2>&1; then
        echo "✅ Cloudflare WARP proxy đang hoạt động (port 8111)"
        warp_ok=true
    else
        echo "⚠️  Cloudflare WARP không hoạt động, đang thử reconnect..."
        warp-cli disconnect 2>/dev/null || true
        sleep 2
        warp-cli connect 2>/dev/null || true
        sleep 3
        
        # Kiểm tra lại sau khi reconnect
        if warp-cli status 2>/dev/null | grep -qi "connected" && \
           nc -z 127.0.0.1 8111 2>/dev/null && \
           curl -s --connect-timeout 3 --max-time 5 -x "socks5h://127.0.0.1:8111" https://api.ipify.org >/dev/null 2>&1; then
            echo "✅ Cloudflare WARP đã được reconnect thành công"
            warp_ok=true
        else
            echo "⚠️  Không thể reconnect WARP, nhưng vẫn tiếp tục..."
            echo "   Proxy có thể không hoạt động cho đến khi WARP được fix"
        fi
    fi
else
    echo "⚠️  warp-cli không tìm thấy, bỏ qua kiểm tra WARP"
    warp_ok=true  # Cho phép tiếp tục nếu không có warp-cli
fi

# Kiểm tra nếu đã chạy
if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE" 2>/dev/null || echo "")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        echo "⚠️  HAProxy 7890 đã đang chạy (PID: $pid)"
        echo "   Dừng trước khi khởi động lại: ./stop_haproxy_7890.sh hoặc cd services/haproxy_7890 && ./stop_haproxy_7890.sh"
        exit 1
    else
        rm -f "$PID_FILE"
    fi
fi

# Kiểm tra port đã được sử dụng chưa
if lsof -i :7890 >/dev/null 2>&1; then
    echo "⚠️  Port 7890 đã được sử dụng"
    lsof -i :7890
    exit 1
fi

# Khởi động HAProxy
echo ""
echo "🚀 Khởi động HAProxy 7890..."
"$HAPROXY_BIN" -f "$CFG_FILE" -p "$PID_FILE" -D

sleep 1

# Kiểm tra xem đã khởi động thành công chưa
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    pid=$(cat "$PID_FILE")
    echo "✅ HAProxy 7890 đã khởi động thành công (PID: $pid)"
    
    # Khởi động WARP monitor
    echo ""
    echo "🛡️  Khởi động WARP monitor..."
    if [ -f "./warp_monitor.sh" ]; then
        ./warp_monitor.sh start 2>/dev/null || true
    fi
    
    echo ""
    echo "📊 Thông tin proxy:"
    echo "   • SOCKS5: socks5://0.0.0.0:7890"
    echo ""
    echo "🧪 Test proxy:"
    echo "   curl -x socks5h://127.0.0.1:7890 https://api.ipify.org"
else
    echo "❌ Không thể khởi động HAProxy 7890"
    exit 1
fi

