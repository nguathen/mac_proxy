#!/usr/bin/env bash
# stop_haproxy_7890.sh
# Dừng HAProxy port 7890

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="./logs/haproxy_7890.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  HAProxy 7890 không đang chạy"
    exit 0
fi

pid=$(cat "$PID_FILE" 2>/dev/null || echo "")

if [ -z "$pid" ]; then
    echo "⚠️  Không tìm thấy PID trong file"
    rm -f "$PID_FILE"
    exit 0
fi

if ! kill -0 "$pid" 2>/dev/null; then
    echo "⚠️  Process $pid không tồn tại"
    rm -f "$PID_FILE"
    exit 0
fi

echo "🛑 Dừng HAProxy 7890 (PID: $pid)..."
kill "$pid" 2>/dev/null || true

# Đợi process dừng
for i in {1..10}; do
    if ! kill -0 "$pid" 2>/dev/null; then
        break
    fi
    sleep 0.5
done

# Force kill nếu vẫn chạy
if kill -0 "$pid" 2>/dev/null; then
    echo "⚠️  Force kill process..."
    kill -9 "$pid" 2>/dev/null || true
    sleep 1
fi

# Xóa PID file
rm -f "$PID_FILE"

# Dừng WARP monitor
if [ -f "./warp_monitor.sh" ]; then
    echo "🛑 Dừng WARP monitor..."
    ./warp_monitor.sh stop 2>/dev/null || true
fi

# Kiểm tra lại
if kill -0 "$pid" 2>/dev/null; then
    echo "❌ Không thể dừng HAProxy 7890"
    exit 1
else
    echo "✅ HAProxy 7890 đã dừng"
fi

