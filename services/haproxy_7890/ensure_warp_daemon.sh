#!/usr/bin/env bash
# ensure_warp_daemon.sh
# Đảm bảo WARP daemon được khởi động sau reboot

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="./logs"
LOG_FILE="$LOG_DIR/warp_daemon_ensure.log"

mkdir -p "$LOG_DIR"

timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(timestamp)] $*" | tee -a "$LOG_FILE"; }

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 Đảm bảo WARP daemon được khởi động"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "🚀 Bắt đầu ensure WARP daemon..."

# Kiểm tra WARP app
if [ ! -d "/Applications/Cloudflare WARP.app" ]; then
    echo "❌ WARP app chưa được cài đặt!"
    exit 1
fi

# Bước 1: Mở WARP app để khởi động daemon
echo ""
echo "1️⃣  Mở WARP app..."
open -a "Cloudflare WARP" 2>/dev/null || true
log "✅ Đã mở WARP app"
sleep 5

# Bước 2: Đợi daemon sẵn sàng
echo ""
echo "2️⃣  Đợi WARP daemon sẵn sàng..."
max_wait=60
wait_count=0

while [ $wait_count -lt $max_wait ]; do
    status_output=$(warp-cli status 2>&1 || echo "")
    
    if echo "$status_output" | grep -vqi "ipc error\|unable to connect\|connection refused\|cloudflarewarp daemon\|no such file"; then
        echo "   ✅ WARP daemon đã sẵn sàng!"
        log "✅ WARP daemon sẵn sàng sau ${wait_count}s"
        break
    fi
    
    if [ $((wait_count % 10)) -eq 0 ] && [ $wait_count -gt 0 ]; then
        echo "   ⏳ Đợi... (${wait_count}/${max_wait}s)"
        # Thử mở lại app nếu chưa sẵn sàng
        if [ $wait_count -eq 20 ] || [ $wait_count -eq 40 ]; then
            echo "   🔄 Thử mở lại WARP app..."
            open -a "Cloudflare WARP" 2>/dev/null || true
            sleep 3
        fi
    fi
    
    sleep 2
    wait_count=$((wait_count + 2))
done

if [ $wait_count -ge $max_wait ]; then
    echo "   ⚠️  WARP daemon chưa sẵn sàng sau ${max_wait}s"
    echo "   💡 Có thể cần:"
    echo "      - Mở WARP app thủ công và chấp nhận permissions"
    echo "      - Kiểm tra System Preferences > Security & Privacy"
    log "⚠️  WARP daemon chưa sẵn sàng sau ${max_wait}s"
    exit 1
fi

# Bước 3: Kiểm tra và register
echo ""
echo "3️⃣  Kiểm tra registration..."
account_status=$(warp-cli account 2>&1 || echo "")
if echo "$account_status" | grep -qi "missing\|not registered\|register"; then
    echo "   📝 WARP chưa được register, đang register..."
    warp-cli register 2>&1 | tee -a "$LOG_FILE" || true
    sleep 3
    log "✅ WARP đã được register"
else
    echo "   ✅ WARP đã được register"
fi

# Bước 4: Set proxy mode
echo ""
echo "4️⃣  Cấu hình proxy mode..."
warp-cli set-mode proxy 2>&1 | tee -a "$LOG_FILE" || true
sleep 2
warp-cli set-proxy-port 8111 2>&1 | tee -a "$LOG_FILE" || true
sleep 2
log "✅ Đã set proxy mode"

# Bước 5: Connect
echo ""
echo "5️⃣  Kết nối WARP..."
warp-cli connect 2>&1 | tee -a "$LOG_FILE" || true
sleep 5

# Bước 6: Kiểm tra
echo ""
echo "6️⃣  Kiểm tra kết nối..."
status_output=$(warp-cli status 2>&1 || echo "")
if echo "$status_output" | grep -qi "status.*connected"; then
    echo "   ✅ WARP đã connected!"
    log "✅ WARP đã connected"
else
    echo "   ⚠️  WARP chưa connected"
    log "⚠️  WARP chưa connected"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 WARP Status:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
warp-cli status 2>&1 | head -10
echo ""
log "✅ Ensure WARP daemon hoàn tất"








