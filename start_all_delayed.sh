#!/usr/bin/env bash
# start_all_delayed.sh
# Wrapper script với delay để đợi system sẵn sàng sau khi boot/login

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="$SCRIPT_DIR/logs/launchd.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] $*" | tee -a "$LOG_FILE"
}

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "🚀 Auto-start script triggered"
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
log "⏳ Đợi thêm 10 giây để các service khác sẵn sàng..."
sleep 10

# Kiểm tra xem hệ thống đã chạy chưa (tránh chạy trùng)
if pgrep -f "start_all.sh" | grep -v "$$" >/dev/null; then
    log "⚠️  start_all.sh đã đang chạy, bỏ qua..."
    exit 0
fi

# Chạy start_all.sh
log "🚀 Khởi động hệ thống..."
"$SCRIPT_DIR/start_all.sh" >> "$LOG_FILE" 2>&1

# Khởi động WARP monitor nếu HAProxy 7890 đang chạy
sleep 5
if lsof -i :7890 >/dev/null 2>&1; then
    log "🛡️  Khởi động WARP monitor..."
    if [ -f "$SCRIPT_DIR/services/haproxy_7890/warp_monitor.sh" ]; then
        cd "$SCRIPT_DIR/services/haproxy_7890"
        ./warp_monitor.sh start >> "$SCRIPT_DIR/logs/warp_monitor_launchd.log" 2>&1 || true
        cd "$SCRIPT_DIR"
    fi
fi

