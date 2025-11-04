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

# Kiểm tra Cloudflare WARP
echo "🔍 Kiểm tra Cloudflare WARP..."
if ! nc -z 127.0.0.1 8111 2>/dev/null; then
    echo "⚠️  Cloudflare WARP proxy (port 8111) không hoạt động"
    echo "   Vui lòng cấu hình WARP:"
    echo "   warp-cli set-mode proxy"
    echo "   warp-cli set-proxy-port 8111"
    echo "   warp-cli connect"
    exit 1
else
    echo "✅ Cloudflare WARP proxy đang chạy (port 8111)"
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

