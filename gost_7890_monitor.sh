#!/usr/bin/env bash
# gost_7890_monitor.sh
# Auto-restart Gost 7890 nếu không hoạt động

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="./logs"
LOG_FILE="$LOG_DIR/gost_7890_monitor.log"
PID_FILE="$LOG_DIR/gost_7890_monitor.pid"
GOST_PID_FILE="$LOG_DIR/gost_7890.pid"
CHECK_INTERVAL=30  # Kiểm tra mỗi 30 giây
GOST_PORT=7890

mkdir -p "$LOG_DIR"

timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(timestamp)] $*" | tee -a "$LOG_FILE"; }

check_gost_process() {
    # Kiểm tra Gost process có đang chạy không
    # Dùng pgrep để tìm process (hoạt động với cả root process)
    local pid=$(pgrep -f "gost.*7890" | head -1 || echo "")
    
    if [ -n "$pid" ]; then
        # Kiểm tra process có thực sự là gost và đang chạy không
        if ps -p "$pid" >/dev/null 2>&1; then
            return 0  # Process đang chạy
        fi
    fi
    
    # Fallback: kiểm tra port nếu không tìm thấy process
    if check_gost_port; then
        return 0  # Port đang listen, có thể process đang chạy
    fi
    
    return 1  # Không tìm thấy process
}

check_gost_port() {
    # Kiểm tra port 7890 có đang listen không
    if lsof -i :$GOST_PORT >/dev/null 2>&1; then
        return 0  # Port đang được sử dụng
    else
        return 1  # Port không được sử dụng
    fi
}

check_gost_functionality() {
    # Kiểm tra Gost có hoạt động không bằng cách test proxy
    # Port 7890 (WARP) cần timeout dài hơn vì forward qua WARP có thể chậm hơn
    if curl -s --connect-timeout 10 --max-time 15 -x "socks5h://127.0.0.1:$GOST_PORT" https://api.ipify.org >/dev/null 2>&1; then
        return 0  # Working
    else
        return 1  # Not working
    fi
}

restart_gost() {
    log "🔄 Restarting Gost 7890..."
    
    # Dừng Gost cũ nếu có
    if [ -f "$GOST_PID_FILE" ]; then
        local pid=$(cat "$GOST_PID_FILE" 2>/dev/null || echo "")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            sleep 2
            # Force kill nếu cần
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$GOST_PID_FILE"
    fi
    
    # Kill process trên port 7890 nếu có
    lsof -ti :$GOST_PORT 2>/dev/null | xargs kill -9 2>/dev/null || true
    sleep 2
    
    # Khởi động lại Gost
    if [ -f "./manage_gost.sh" ]; then
        chmod +x manage_gost.sh
        ./manage_gost.sh start-port 7890 >> "$LOG_DIR/gost_7890_restart.log" 2>&1 || {
            log "❌ Failed to restart Gost 7890"
            return 1
        }
        
        # Đợi Gost khởi động
        sleep 3
        
        # Kiểm tra lại
        if check_gost_process && check_gost_port && check_gost_functionality; then
            log "✅ Gost 7890 restarted successfully"
            return 0
        else
            log "⚠️  Gost restart may have failed, will retry after cooldown"
            return 1
        fi
    else
        log "❌ manage_gost.sh not found"
        return 1
    fi
}

monitor_loop() {
    log "🛡️  Gost 7890 monitor started (check interval: ${CHECK_INTERVAL}s)"
    
    local consecutive_failures=0
    local max_failures=3  # Sau 3 lần kiểm tra thất bại mới restart
    local last_restart_time=0
    local restart_cooldown=120  # Cooldown 2 phút sau mỗi lần restart
    
    while true; do
        local current_time=$(date +%s)
        local time_since_restart=$((current_time - last_restart_time))
        
        # Kiểm tra process trước
        if ! check_gost_process; then
            # Process không chạy
            if [ $time_since_restart -lt $restart_cooldown ]; then
                local remaining=$((restart_cooldown - time_since_restart))
                log "⏳ Gost process not running (cooldown ${remaining}s), waiting..."
                consecutive_failures=0
            else
                consecutive_failures=$((consecutive_failures + 1))
                
                if [ $consecutive_failures -ge $max_failures ]; then
                    log "⚠️  Gost process not running (failures: $consecutive_failures)"
                    restart_gost
                    last_restart_time=$(date +%s)
                    consecutive_failures=0
                else
                    log "⚠️  Gost process not running ($consecutive_failures/$max_failures), waiting..."
                fi
            fi
        elif ! check_gost_port; then
            # Process chạy nhưng port không listen
            if [ $time_since_restart -lt $restart_cooldown ]; then
                local remaining=$((restart_cooldown - time_since_restart))
                log "⏳ Gost process running but port not listening (cooldown ${remaining}s), waiting..."
                consecutive_failures=0
            else
                consecutive_failures=$((consecutive_failures + 1))
                
                if [ $consecutive_failures -ge $max_failures ]; then
                    log "⚠️  Gost port not listening (failures: $consecutive_failures)"
                    restart_gost
                    last_restart_time=$(date +%s)
                    consecutive_failures=0
                else
                    log "⚠️  Gost port not listening ($consecutive_failures/$max_failures), waiting..."
                fi
            fi
        elif ! check_gost_functionality; then
            # Process và port đều OK nhưng proxy không hoạt động
            if [ $time_since_restart -lt $restart_cooldown ]; then
                local remaining=$((restart_cooldown - time_since_restart))
                log "⏳ Gost not functional (cooldown ${remaining}s), waiting..."
                consecutive_failures=0
            else
                consecutive_failures=$((consecutive_failures + 1))
                
                if [ $consecutive_failures -ge $max_failures ]; then
                    log "⚠️  Gost not functional (failures: $consecutive_failures)"
                    restart_gost
                    last_restart_time=$(date +%s)
                    consecutive_failures=0
                else
                    log "⚠️  Gost not functional ($consecutive_failures/$max_failures), waiting..."
                fi
            fi
        else
            # Tất cả đều OK
            if [ $consecutive_failures -gt 0 ]; then
                log "✅ Gost is working again"
                consecutive_failures=0
            fi
        fi
        
        sleep "$CHECK_INTERVAL"
    done
}

stop_monitor() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE" 2>/dev/null || echo "")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            log "🛑 Stopping Gost 7890 monitor (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            sleep 1
            
            # Force kill nếu cần
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
            
            rm -f "$PID_FILE"
            log "✅ Gost 7890 monitor stopped"
        else
            rm -f "$PID_FILE"
        fi
    else
        echo "⚠️  Gost 7890 monitor is not running"
    fi
}

case "${1:-}" in
    start)
        if [ -f "$PID_FILE" ]; then
            pid=$(cat "$PID_FILE" 2>/dev/null || echo "")
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                echo "⚠️  Gost 7890 monitor đã đang chạy (PID: $pid)"
                exit 1
            else
                rm -f "$PID_FILE"
            fi
        fi
        
        log "🚀 Starting Gost 7890 monitor..."
        monitor_loop &
        monitor_pid=$!
        echo "$monitor_pid" > "$PID_FILE"
        log "✅ Gost 7890 monitor started (PID: $monitor_pid)"
        # Đợi để systemd đọc được PID file (cần thiết cho Type=forking)
        sleep 2
        # Verify PID file exists and process is running
        if [ -f "$PID_FILE" ] && kill -0 "$monitor_pid" 2>/dev/null; then
            exit 0
        else
            log "❌ Failed to start monitor process"
            exit 1
        fi
        ;;
    stop)
        stop_monitor
        ;;
    status)
        if [ -f "$PID_FILE" ]; then
            pid=$(cat "$PID_FILE" 2>/dev/null || echo "")
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                echo "✅ Gost 7890 monitor đang chạy (PID: $pid)"
                
                if check_gost_process && check_gost_port && check_gost_functionality; then
                    echo "   ✅ Gost 7890: Running và hoạt động"
                else
                    echo "   ⚠️  Gost 7890: Có vấn đề"
                fi
            else
                echo "❌ Gost 7890 monitor không đang chạy"
                rm -f "$PID_FILE"
            fi
        else
            echo "❌ Gost 7890 monitor không đang chạy"
        fi
        ;;
    check)
        if check_gost_process && check_gost_port && check_gost_functionality; then
            echo "✅ Gost 7890 đang hoạt động tốt"
            exit 0
        else
            echo "⚠️  Gost 7890 không hoạt động, đang restart..."
            restart_gost
            exit $?
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|status|check}"
        echo ""
        echo "Commands:"
        echo "  start  - Khởi động Gost 7890 monitor (background)"
        echo "  stop   - Dừng Gost 7890 monitor"
        echo "  status - Kiểm tra trạng thái monitor"
        echo "  check  - Kiểm tra và restart Gost 7890 nếu cần (one-time)"
        exit 1
        ;;
esac

