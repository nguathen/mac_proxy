#!/usr/bin/env bash
# gost_monitor.sh
# Auto-restart gost nếu connection fail

# Không dùng set -e trong script này vì monitor loop cần tiếp tục chạy ngay cả khi có lỗi
# Chỉ dùng set -u để bắt undefined variables, không dùng pipefail để tránh exit
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="./logs"
LOG_FILE="$LOG_DIR/gost_monitor.log"
PID_FILE="$LOG_DIR/gost_monitor.pid"
CHECK_INTERVAL=10  # Kiểm tra mỗi 10 giây để phát hiện lỗi nhanh hơn
CONFIG_DIR="./config"
MANAGE_GOST_SCRIPT="./manage_gost.sh"

mkdir -p "$LOG_DIR"

timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(timestamp)] $*" | tee -a "$LOG_FILE"; }

# Kiểm tra gost có đang chạy không
check_gost_process() {
    local port=$1
    local pid_file="$LOG_DIR/gost_${port}.pid"
    
    if [ ! -f "$pid_file" ]; then
        return 1  # PID file không tồn tại
    fi
    
    local pid=$(cat "$pid_file" 2>/dev/null || echo "")
    if [ -z "$pid" ]; then
        return 1  # PID file rỗng
    fi
    
    if kill -0 "$pid" 2>/dev/null; then
        return 0  # Process đang chạy
    else
        return 1  # Process không chạy
    fi
}

# Kiểm tra gost proxy có hoạt động không
check_gost_proxy() {
    local port=$1
    
    # Port 7890 (WARP) cần timeout dài hơn vì forward qua WARP có thể chậm hơn
    if [ "$port" = "7890" ]; then
        # Timeout dài hơn cho WARP: connect-timeout 10s, max-time 15s
        if curl -s --connect-timeout 10 --max-time 15 -x socks5h://127.0.0.1:$port https://ipinfo.io/ip >/dev/null 2>&1; then
            return 0  # Working
        else
            return 1  # Not working
        fi
    else
        # Kiểm tra proxy có hoạt động không (với timeout tối ưu cho ProtonVPN)
        # Tăng timeout lên để phù hợp với ProtonVPN (có thể chậm hơn do distance)
        # Dùng curl với timeout options: connect-timeout 15s, max-time 20s (tăng từ 8s/12s)
        if curl -s --connect-timeout 15 --max-time 20 -x socks5h://127.0.0.1:$port https://ipinfo.io/ip >/dev/null 2>&1; then
            return 0  # Working
        else
            return 1  # Not working
        fi
    fi
}

# Restart gost service
restart_gost_port() {
    local port=$1
    log "🔄 Restarting gost on port $port..."
    
    if [ ! -f "$MANAGE_GOST_SCRIPT" ]; then
        log "❌ manage_gost.sh not found!"
        return 1
    fi
    
    # Sử dụng manage_gost.sh để restart với error handling
    local result=""
    local exit_code=1
    
    result=$(bash "$MANAGE_GOST_SCRIPT" restart-port "$port" 2>&1)
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        # Đợi một chút để gost khởi động
        sleep 3
        
        # Kiểm tra lại
        local process_ok=false
        local proxy_ok=false
        
        if check_gost_process "$port"; then
            process_ok=true
        fi
        
        if check_gost_proxy "$port"; then
            proxy_ok=true
        fi
        
        if [ "$process_ok" = true ] && [ "$proxy_ok" = true ]; then
            log "✅ Gost on port $port restarted successfully"
            return 0
        else
            log "⚠️  Gost on port $port restarted but may not be working yet"
            return 1
        fi
    else
        log "❌ Failed to restart gost on port $port: $result"
        return 1
    fi
}

# Lấy danh sách các gost ports từ config files
get_gost_ports() {
    local ports=""
    
    for config_file in "$CONFIG_DIR"/gost_*.config; do
        if [ -f "$config_file" ]; then
            local port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
            if [ -n "$port" ]; then
                # Loại bỏ port 7890 vì có monitor riêng (gost_7890_monitor.sh)
                if [ "$port" != "7890" ]; then
                    ports="$ports $port"
                fi
            fi
        fi
    done
    
    echo "$ports" | xargs  # Trim whitespace
}

monitor_loop() {
    log "🛡️  Gost monitor started (check interval: ${CHECK_INTERVAL}s)"
    
    local reconnect_cooldown=120  # Cooldown 2 phút sau mỗi lần restart (tăng từ 1 phút để tránh restart quá nhanh)
    local max_failures=3  # Sau 3 lần kiểm tra thất bại mới restart (tăng từ 2 để tránh restart quá nhanh)
    
    # Initialize failure counters for each port
    local ports=$(get_gost_ports)
    if [ -z "$ports" ]; then
        log "⚠️  No gost configs found, monitor will check periodically"
    fi
    
    # Trap để log khi exit hoặc bị kill
    trap 'log "⚠️  Monitor loop exiting (PID: $$, signal: EXIT)"' EXIT
    trap 'log "⚠️  Monitor loop killed (PID: $$, signal: SIGTERM)"; exit 0' TERM
    trap 'log "⚠️  Monitor loop interrupted (PID: $$, signal: SIGINT)"; exit 0' INT
    
    while true; do
        # Monitor loop không bao giờ dùng set -e để tránh exit
        
        local current_time=$(date +%s)
        
        # Lấy danh sách ports hiện tại (có thể thay đổi)
        local current_ports=$(get_gost_ports 2>/dev/null || echo "")
        
        # Nếu không có ports, đợi và tiếp tục
        if [ -z "$current_ports" ]; then
            sleep "$CHECK_INTERVAL"
            continue
        fi
        
        for port in $current_ports; do
            # Skip nếu port rỗng
            if [ -z "$port" ]; then
                continue
            fi
            # Double check: không bao giờ monitor port 7890 (có monitor riêng)
            if [ "$port" = "7890" ]; then
                continue
            fi
            # Sử dụng file để lưu trữ failure count và last restart time
            local failure_file="$LOG_DIR/gost_${port}_failures.txt"
            local restart_file="$LOG_DIR/gost_${port}_restart_time.txt"
            
            # Đọc failure count và restart time từ file
            local failures=0
            local last_restart=0
            
            if [ -f "$failure_file" ]; then
                failures=$(cat "$failure_file" 2>/dev/null || echo "0")
                failures=$((failures + 0))  # Ensure it's a number
            fi
            
            if [ -f "$restart_file" ]; then
                last_restart=$(cat "$restart_file" 2>/dev/null || echo "0")
                last_restart=$((last_restart + 0))  # Ensure it's a number
            fi
            
            local time_since_restart=$((current_time - last_restart))
            
            # Kiểm tra process
            if ! check_gost_process "$port"; then
                # Process không chạy
                if [ $time_since_restart -lt $reconnect_cooldown ]; then
                    local remaining=$((reconnect_cooldown - time_since_restart))
                    log "⏳ Gost on port $port not running (cooldown ${remaining}s), waiting..."
                    echo "0" > "$failure_file"
                else
                    failures=$((failures + 1))
                    echo "$failures" > "$failure_file"
                    
                    if [ $failures -ge $max_failures ]; then
                        log "⚠️  Gost on port $port not running (failures: $failures)"
                        restart_gost_port "$port"
                        echo "$(date +%s)" > "$restart_file"
                        echo "0" > "$failure_file"
                    else
                        log "⚠️  Gost on port $port not running ($failures/$max_failures), waiting..."
                    fi
                fi
            else
                # Process đang chạy, kiểm tra proxy
                if check_gost_proxy "$port"; then
                    if [ $failures -gt 0 ]; then
                        log "✅ Gost on port $port is working again"
                    fi
                    echo "0" > "$failure_file"
                else
                    # Process chạy nhưng proxy không hoạt động
                    if [ $time_since_restart -lt $reconnect_cooldown ]; then
                        local remaining=$((reconnect_cooldown - time_since_restart))
                        log "⏳ Gost on port $port proxy failed (cooldown ${remaining}s), waiting..."
                        echo "0" > "$failure_file"
                    else
                        failures=$((failures + 1))
                        echo "$failures" > "$failure_file"
                        
                        if [ $failures -ge $max_failures ]; then
                            log "⚠️  Gost on port $port proxy not working (failures: $failures)"
                            restart_gost_port "$port"
                            echo "$(date +%s)" > "$restart_file"
                            echo "0" > "$failure_file"
                        else
                            log "⚠️  Gost on port $port proxy check failed ($failures/$max_failures), waiting..."
                        fi
                    fi
                fi
            fi
        done
        
        # KHÔNG bật lại set -e vì monitor loop phải chạy liên tục
        
        sleep "$CHECK_INTERVAL"
    done
}

stop_monitor() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE" 2>/dev/null || echo "")
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            log "🛑 Stopping gost monitor (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            sleep 1
            
            # Force kill nếu cần
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
            
            rm -f "$PID_FILE"
            log "✅ Gost monitor stopped"
        else
            rm -f "$PID_FILE"
        fi
    else
        echo "⚠️  Gost monitor is not running"
    fi
}

case "${1:-}" in
    start)
        if [ -f "$PID_FILE" ]; then
            pid=$(cat "$PID_FILE" 2>/dev/null || echo "")
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                echo "⚠️  Gost monitor đã đang chạy (PID: $pid)"
                exit 1
            else
                rm -f "$PID_FILE"
            fi
        fi
        
        log "🚀 Starting gost monitor..."
        monitor_loop &
        monitor_pid=$!
        echo "$monitor_pid" > "$PID_FILE"
        log "✅ Gost monitor started (PID: $monitor_pid)"
        ;;
    stop)
        stop_monitor
        ;;
    status)
        if [ -f "$PID_FILE" ]; then
            pid=$(cat "$PID_FILE" 2>/dev/null || echo "")
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                echo "✅ Gost monitor đang chạy (PID: $pid)"
                
                ports=$(get_gost_ports)
                all_ok=true
                for port in $ports; do
                    if check_gost_process "$port" && check_gost_proxy "$port"; then
                        echo "   ✅ Port $port: Running và hoạt động"
                    else
                        echo "   ⚠️  Port $port: Có vấn đề"
                        all_ok=false
                    fi
                done
                
                if [ "$all_ok" = true ]; then
                    echo "   ✅ Tất cả gost services đang hoạt động tốt"
                fi
            else
                echo "❌ Gost monitor không đang chạy"
                rm -f "$PID_FILE"
            fi
        else
            echo "❌ Gost monitor không đang chạy"
        fi
        ;;
    check)
        # One-time check và restart nếu cần
        ports=$(get_gost_ports)
        restarted_any=false
        
        for port in $ports; do
            if ! check_gost_process "$port" || ! check_gost_proxy "$port"; then
                echo "⚠️  Gost on port $port không hoạt động, đang restart..."
                restart_gost_port "$port"
                restarted_any=true
            fi
        done
        
        if [ "$restarted_any" = false ]; then
            echo "✅ Tất cả gost services đang hoạt động tốt"
            exit 0
        else
            exit 1
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|status|check}"
        echo ""
        echo "Commands:"
        echo "  start  - Khởi động gost monitor (background)"
        echo "  stop   - Dừng gost monitor"
        echo "  status - Kiểm tra trạng thái monitor"
        echo "  check  - Kiểm tra và restart gost nếu cần (one-time)"
        exit 1
        ;;
esac

