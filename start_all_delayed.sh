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

# Cấu hình WARP nếu đã cài đặt
if command -v warp-cli &> /dev/null; then
    log "🔐 Cấu hình Cloudflare WARP..."
    
    # Đợi WARP daemon sẵn sàng
    WAIT_COUNT=0
    MAX_WAIT=30
    while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
        if warp-cli --accept-tos status &>/dev/null 2>&1; then
            break
        fi
        sleep 1
        WAIT_COUNT=$((WAIT_COUNT + 1))
    done
    
    if [ $WAIT_COUNT -lt $MAX_WAIT ]; then
        # Cấu hình WARP
        warp-cli --accept-tos mode proxy >/dev/null 2>&1 || true
        sleep 1
        warp-cli --accept-tos proxy port 8111 >/dev/null 2>&1 || true
        sleep 1
        warp-cli --accept-tos connect >/dev/null 2>&1 || true
        log "✅ WARP đã được cấu hình"
    else
        log "⚠️  WARP daemon chưa sẵn sàng, bỏ qua cấu hình WARP"
    fi
fi

# Kiểm tra xem hệ thống đã chạy chưa (tránh chạy trùng)
if pgrep -f "start_all.sh" | grep -v "$$" >/dev/null; then
    log "⚠️  start_all.sh đã đang chạy, bỏ qua..."
    exit 0
fi

# Chạy start_all.sh
log "🚀 Khởi động hệ thống..."
"$SCRIPT_DIR/start_all.sh" >> "$LOG_FILE" 2>&1


