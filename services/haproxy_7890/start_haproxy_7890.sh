#!/usr/bin/env bash
# start_haproxy_7890.sh
# Khởi động HAProxy port 7890 với backend Cloudflare WARP

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Find HAProxy binary (Linux and macOS compatible)
HAPROXY_BIN=""
if command -v haproxy &> /dev/null; then
    HAPROXY_BIN="$(command -v haproxy)"
elif [ -f "/usr/sbin/haproxy" ]; then
    HAPROXY_BIN="/usr/sbin/haproxy"
elif [ -f "/usr/bin/haproxy" ]; then
    HAPROXY_BIN="/usr/bin/haproxy"
elif [ -f "/opt/homebrew/sbin/haproxy" ]; then
    HAPROXY_BIN="/opt/homebrew/sbin/haproxy"
else
    echo "❌ HAProxy chưa được cài đặt"
    echo "   Linux: sudo apt-get install haproxy hoặc sudo yum install haproxy"
    echo "   macOS: brew install haproxy"
    exit 1
fi

CFG_FILE="./config/haproxy_7890.cfg"
PID_FILE="./logs/haproxy_7890.pid"
LOG_DIR="./logs"

mkdir -p "$LOG_DIR" config

# Kiểm tra và auto-reconnect Cloudflare WARP
echo "🔍 Kiểm tra Cloudflare WARP..."
warp_ok=false

# Kiểm tra WARP status và proxy functionality
if command -v warp-cli &> /dev/null; then
    WARP_STATUS=$(warp-cli status 2>/dev/null || echo "")
    if echo "$WARP_STATUS" | grep -qi "connected" && \
       nc -z 127.0.0.1 8111 2>/dev/null && \
       curl -s --connect-timeout 3 --max-time 5 -x "socks5h://127.0.0.1:8111" https://api.ipify.org >/dev/null 2>&1; then
        echo "✅ Cloudflare WARP proxy đang hoạt động (port 8111)"
        warp_ok=true
    else
        echo "⚠️  Cloudflare WARP không hoạt động, đang thử reconnect..."
        # Linux WARP CLI syntax
        if warp-cli proxy --help 2>/dev/null | grep -q "proxy"; then
            # Linux: use proxy enable/disable
            warp-cli proxy disable 2>/dev/null || true
            sleep 1
            warp-cli proxy enable 2>/dev/null || true
        else
            # macOS: use disconnect/connect
            warp-cli disconnect 2>/dev/null || true
            sleep 2
            warp-cli connect 2>/dev/null || true
        fi
        sleep 3
        
        # Kiểm tra lại sau khi reconnect
        WARP_STATUS=$(warp-cli status 2>/dev/null || echo "")
        if echo "$WARP_STATUS" | grep -qi "connected" && \
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

# Kiểm tra port đã được sử dụng chưa (Linux and macOS compatible)
PORT_IN_USE=false
if command -v lsof &> /dev/null; then
    if lsof -i :7890 >/dev/null 2>&1; then
        PORT_IN_USE=true
        echo "⚠️  Port 7890 đã được sử dụng:"
        lsof -i :7890
    fi
elif command -v ss &> /dev/null; then
    if ss -tlnp | grep -q ":7890 "; then
        PORT_IN_USE=true
        echo "⚠️  Port 7890 đã được sử dụng:"
        ss -tlnp | grep ":7890 "
    fi
elif command -v netstat &> /dev/null; then
    if netstat -tlnp 2>/dev/null | grep -q ":7890 "; then
        PORT_IN_USE=true
        echo "⚠️  Port 7890 đã được sử dụng:"
        netstat -tlnp 2>/dev/null | grep ":7890 "
    fi
fi

if [ "$PORT_IN_USE" = true ]; then
    exit 1
fi

# Kiểm tra và tạo config file nếu chưa có
if [ ! -f "$CFG_FILE" ]; then
    echo "📝 Creating HAProxy config file..."
    cat > "$CFG_FILE" <<'EOF'
global
    daemon
    maxconn 4096
    log /dev/log local0
    chroot /var/lib/haproxy
    stats socket /run/haproxy/admin.sock mode 660 level admin
    stats timeout 30s
    user haproxy
    group haproxy

defaults
    mode tcp
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms
    log global
    option tcplog

# SOCKS5 proxy on port 7890 forwarding to WARP on 8111
frontend socks5_frontend
    bind 0.0.0.0:7890
    default_backend warp_backend

backend warp_backend
    server warp1 127.0.0.1:8111 check
EOF
    echo "✅ Config file created"
fi

# Validate config file
if ! "$HAPROXY_BIN" -f "$CFG_FILE" -c >/dev/null 2>&1; then
    echo "⚠️  Config validation failed, but continuing..."
    # Try without chroot/user/group for Linux compatibility
    sed -i.bak 's/^[[:space:]]*chroot.*/    # chroot disabled/' "$CFG_FILE" 2>/dev/null || true
    sed -i.bak 's/^[[:space:]]*user.*/    # user disabled/' "$CFG_FILE" 2>/dev/null || true
    sed -i.bak 's/^[[:space:]]*group.*/    # group disabled/' "$CFG_FILE" 2>/dev/null || true
fi

# Khởi động HAProxy
echo ""
echo "🚀 Khởi động HAProxy 7890..."
# Use -D for daemon mode (Linux compatible)
"$HAPROXY_BIN" -f "$CFG_FILE" -p "$PID_FILE" -D 2>&1 || {
    # If -D fails, try without daemon flag (some versions)
    echo "⚠️  Daemon mode failed, trying foreground mode..."
    nohup "$HAPROXY_BIN" -f "$CFG_FILE" -p "$PID_FILE" > "$LOG_DIR/haproxy_7890.log" 2>&1 &
    echo $! > "$PID_FILE"
}

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

