#!/usr/bin/env bash
# warp_monitor.sh
# Auto-reconnect WARP nếu không hoạt động

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="./logs"
LOG_FILE="$LOG_DIR/warp_monitor.log"
PID_FILE="$LOG_DIR/warp_monitor.pid"
CHECK_INTERVAL=30  # Kiểm tra mỗi 30 giây
WARP_PORT=8111

mkdir -p "$LOG_DIR"

timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(timestamp)] $*" | tee -a "$LOG_FILE"; }

check_warp_status() {
    # Kiểm tra WARP CLI status
    if ! command -v warp-cli &> /dev/null; then
        return 1
    fi
    
    local status_output=$(warp-cli status 2>/dev/null || echo "")
    if echo "$status_output" | grep -qi "status.*connected"; then
        return 0  # Connected
    elif echo "$status_output" | grep -qi "status.*connecting"; then
        return 2  # Connecting (đang kết nối, cần đợi)
    else
        return 1  # Disconnected hoặc lỗi
    fi
}

check_warp_proxy() {
    # WARP trên macOS chỉ hoạt động qua SOCKS5 protocol, không accept raw TCP
    # Chỉ kiểm tra proxy functionality thực tế bằng curl
    
    # Kiểm tra proxy có hoạt động không (với timeout ngắn)
    if curl -s --connect-timeout 3 --max-time 6 -x "socks5h://127.0.0.1:$WARP_PORT" https://api.ipify.org >/dev/null 2>&1; then
        return 0  # Working
    else
        return 1  # Not working
    fi
}

reconnect_warp() {
    log "🔄 Reconnecting WARP..."
    
    # Đảm bảo proxy mode được set
    warp-cli set-mode proxy 2>/dev/null || true
    warp-cli set-proxy-port "$WARP_PORT" 2>/dev/null || true
    sleep 1
    
    # Disconnect
    warp-cli disconnect 2>/dev/null || true
    sleep 3
    
    # Connect
    warp-cli connect 2>/dev/null || true
    
    # Đợi WARP kết nối (có thể mất 5-10 giây)
    local wait_count=0
    local max_wait=10
    while [ $wait_count -lt $max_wait ]; do
        sleep 1
        if warp-cli status 2>/dev/null | grep -qi "status.*connected"; then
            break
        fi
        wait_count=$((wait_count + 1))
    done
    
    # Đợi thêm để proxy port sẵn sàng
    sleep 5
    
    # Kiểm tra lại
    if check_warp_proxy; then
        log "✅ WARP reconnected successfully"
        return 0
    else
        log "⚠️  WARP reconnect may have failed, will retry after cooldown"
        return 1
    fi
}

monitor_loop() {
    log "🛡️  WARP monitor started (check interval: ${CHECK_INTERVAL}s)"
    
    local consecutive_failures=0
    local max_failures=3  # Sau 3 lần kiểm tra thất bại mới reconnect
    local last_reconnect_time=0
    local reconnect_cooldown=120  # Cooldown 2 phút sau mỗi lần reconnect
    
    while true; do
        local current_time=$(date +%s)
        local time_since_reconnect=$((current_time - last_reconnect_time))
        
        # Kiểm tra WARP status trước
        check_warp_status
        local status_result=$?
        
        if [ $status_result -eq 2 ]; then
            # WARP đang connecting, đợi thêm
            log "⏳ WARP đang connecting, đợi thêm..."
            consecutive_failures=0  # Reset counter khi đang connecting
        elif [ $status_result -eq 0 ]; then
            # WARP đã connected, kiểm tra proxy
            if check_warp_proxy; then
                if [ $consecutive_failures -gt 0 ]; then
                    log "✅ WARP is working again"
                    consecutive_failures=0
                fi
            else
                # Connected nhưng proxy không hoạt động
                if [ $time_since_reconnect -lt $reconnect_cooldown ]; then
                    local remaining=$((reconnect_cooldown - time_since_reconnect))
                    log "⏳ WARP connected but proxy failed (cooldown ${remaining}s), waiting..."
                    consecutive_failures=0
                else
                    consecutive_failures=$((consecutive_failures + 1))
                    
                    if [ $consecutive_failures -ge $max_failures ]; then
                        log "⚠️  WARP connected but proxy not working (failures: $consecutive_failures)"
                        reconnect_warp
                        last_reconnect_time=$(date +%s)
                        consecutive_failures=0
                    else
                        log "⚠️  WARP proxy check failed ($consecutive_failures/$max_failures), waiting..."
                    fi
                fi
            fi
        else
            # WARP disconnected
            if [ $time_since_reconnect -lt $reconnect_cooldown ]; then
                local remaining=$((reconnect_cooldown - time_since_reconnect))
                log "⏳ WARP disconnected (cooldown ${remaining}s), waiting..."
                consecutive_failures=0
            else
                consecutive_failures=$((consecutive_failures + 1))
                
                if [ $consecutive_failures -ge $max_failures ]; then
                    log "⚠️  WARP disconnected (failures: $consecutive_failures)"
                    reconnect_warp
                    last_reconnect_time=$(date +%s)
                    consecutive_failures=0
                else
                    log "⚠️  WARP disconnected ($consecutive_failures/$max_failures), waiting..."
                fi
            fi
        fi
        
        sleep "$CHECK_INTERVAL"
    done
}

stop_monitor() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE" 2>/dev/null || echo "")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            log "🛑 Stopping WARP monitor (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            sleep 1
            
            # Force kill nếu cần
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
            
            rm -f "$PID_FILE"
            log "✅ WARP monitor stopped"
        else
            rm -f "$PID_FILE"
        fi
    else
        echo "⚠️  WARP monitor is not running"
    fi
}

case "${1:-}" in
    start)
        if [ -f "$PID_FILE" ]; then
            pid=$(cat "$PID_FILE" 2>/dev/null || echo "")
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                echo "⚠️  WARP monitor đã đang chạy (PID: $pid)"
                exit 1
            else
                rm -f "$PID_FILE"
            fi
        fi
        
        log "🚀 Starting WARP monitor..."
        monitor_loop &
        monitor_pid=$!
        echo "$monitor_pid" > "$PID_FILE"
        log "✅ WARP monitor started (PID: $monitor_pid)"
        ;;
    stop)
        stop_monitor
        ;;
    status)
        if [ -f "$PID_FILE" ]; then
            pid=$(cat "$PID_FILE" 2>/dev/null || echo "")
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                echo "✅ WARP monitor đang chạy (PID: $pid)"
                
                if check_warp_status && check_warp_proxy; then
                    echo "   ✅ WARP: Connected và hoạt động"
                else
                    echo "   ⚠️  WARP: Có vấn đề"
                fi
            else
                echo "❌ WARP monitor không đang chạy"
                rm -f "$PID_FILE"
            fi
        else
            echo "❌ WARP monitor không đang chạy"
        fi
        ;;
    check)
        if check_warp_status && check_warp_proxy; then
            echo "✅ WARP đang hoạt động tốt"
            exit 0
        else
            echo "⚠️  WARP không hoạt động, đang reconnect..."
            reconnect_warp
            exit $?
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|status|check}"
        echo ""
        echo "Commands:"
        echo "  start  - Khởi động WARP monitor (background)"
        echo "  stop   - Dừng WARP monitor"
        echo "  status - Kiểm tra trạng thái monitor"
        echo "  check  - Kiểm tra và reconnect WARP nếu cần (one-time)"
        exit 1
        ;;
esac

