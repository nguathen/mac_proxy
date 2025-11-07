#!/usr/bin/env bash
# start_webui_delayed.sh
# Wrapper script với delay để đợi system sẵn sàng trước khi khởi động Web UI

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="$SCRIPT_DIR/logs/webui_launchd.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] $*" | tee -a "$LOG_FILE"
}

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "🌐 Web UI auto-start script triggered"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Đợi network sẵn sàng (tối đa 60 giây)
log "⏳ Đợi network sẵn sàng..."
max_wait=60
waited=0
while [ $waited -lt $max_wait ]; do
    if ping -c 1 -W 1000 8.8.8.8 >/dev/null 2>&1 || \
       ping -c 1 -W 1000 1.1.1.1 >/dev/null 2>&1; then
        log "✅ Network đã sẵn sàng (sau ${waited}s)"
        break
    fi
    sleep 2
    waited=$((waited + 2))
done

if [ $waited -ge $max_wait ]; then
    log "⚠️  Network chưa sẵn sàng sau ${max_wait}s, tiếp tục anyway..."
fi

# Đợi thêm một chút để các service khác sẵn sàng
log "⏳ Đợi thêm 15 giây để các service khác sẵn sàng..."
sleep 15

# Kiểm tra xem Web UI đã chạy chưa (tránh chạy trùng)
if lsof -i :5000 >/dev/null 2>&1; then
    log "⚠️  Web UI đã đang chạy trên port 5000, bỏ qua..."
    exit 0
fi

if [ -f "./logs/webui.pid" ]; then
    pid=$(cat "./logs/webui.pid" 2>/dev/null || echo "")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        log "⚠️  Web UI đã đang chạy (PID: $pid), bỏ qua..."
        exit 0
    fi
fi

# Chạy start_webui_daemon.sh
log "🚀 Khởi động Web UI..."
exec "$SCRIPT_DIR/start_webui_daemon.sh" >> "$LOG_FILE" 2>&1

