#!/usr/bin/env bash
# monitor_gost.sh
# Monitor gost connection stability

set -euo pipefail

LOG_DIR="./logs"
MONITOR_LOG="$LOG_DIR/monitor.log"
CHECK_INTERVAL=30  # Check every 30 seconds
FAIL_THRESHOLD=3   # Restart after 3 consecutive failures

mkdir -p "$LOG_DIR"

timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(timestamp)] $*" | tee -a "$MONITOR_LOG"; }

# Cấu hình gost instances
declare -A GOST_INSTANCES=(
    ["1"]="18181"
    ["2"]="18182" 
    ["3"]="18183"
    ["4"]="18184"
    ["5"]="18185"
    ["6"]="18186"
    ["7"]="18187"
)

# Test connection for a port
test_connection() {
    local port=$1
    local timeout=10
    
    if curl -s --max-time "$timeout" -x "socks5h://127.0.0.1:$port" https://api.ipify.org &>/dev/null; then
        return 0  # Success
    else
        return 1  # Failed
    fi
}

# Monitor loop
monitor_loop() {
    log "🔍 Starting gost monitor (interval: ${CHECK_INTERVAL}s, threshold: ${FAIL_THRESHOLD})"
    
    # Initialize failure counters
    declare -A fail_counts
    
    local instance=1
    for port in "${GOST_INSTANCES[@]}"; do
        fail_counts["$instance"]=0
        ((instance++))
    done
    
    while true; do
        instance=1
        
        for port in "${GOST_INSTANCES[@]}"; do
            # Test connection
            if test_connection "$port"; then
                # Success - reset counter
                if [ "${fail_counts[$instance]}" -gt 0 ]; then
                    log "✅ Gost $instance (port $port) recovered"
                fi
                fail_counts["$instance"]=0
            else
                # Failed - increment counter
                ((fail_counts["$instance"]++))
                local count=${fail_counts[$instance]}
                
                log "⚠️  Gost $instance (port $port) failed ($count/$FAIL_THRESHOLD)"
                
                # Check if threshold reached
                if [ "$count" -ge "$FAIL_THRESHOLD" ]; then
                    log "🔄 Restarting gost $instance (port $port) - threshold reached"
                    
                    # Restart specific instance
                    local pid_file="$LOG_DIR/gost${instance}.pid"
                    
                    # Stop
                    if [ -f "$pid_file" ]; then
                        pid=$(cat "$pid_file" 2>/dev/null || echo "")
                        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                            kill "$pid" 2>/dev/null || true
                        fi
                        rm -f "$pid_file"
                    fi
                    
                    # Kill port
                    lsof -ti ":$port" 2>/dev/null | xargs kill -9 2>/dev/null || true
                    sleep 2
                    
                    # Start
                    local log_file="$LOG_DIR/gost${instance}.log"
                    local proxy_url="https://user:pass@az-01.protonvpn.net:4465"
                    nohup gost -L socks5://:$port -F "$proxy_url" > "$log_file" 2>&1 &
                    local new_pid=$!
                    echo "$new_pid" > "$pid_file"
                    
                    log "✅ Gost $instance restarted (PID: $new_pid)"
                    
                    # Reset counter
                    fail_counts["$instance"]=0
                    
                    # Wait for it to stabilize
                    sleep 10
                fi
            fi
            
            ((instance++))
        done
        
        sleep "$CHECK_INTERVAL"
    done
}

# Signal handling
trap 'log "🛑 Monitor stopped"; exit 0' SIGTERM SIGINT

# Main
case "${1:-}" in
    start)
        if [ -f "$LOG_DIR/monitor.pid" ]; then
            pid=$(cat "$LOG_DIR/monitor.pid" 2>/dev/null || echo "")
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                echo "Monitor already running (PID: $pid)"
                exit 1
            fi
        fi
        
        # Start in background
        nohup bash "$0" run >> "$MONITOR_LOG" 2>&1 &
        echo $! > "$LOG_DIR/monitor.pid"
        echo "Monitor started (PID: $!)"
        echo "Log: tail -f $MONITOR_LOG"
        ;;
    
    stop)
        if [ -f "$LOG_DIR/monitor.pid" ]; then
            pid=$(cat "$LOG_DIR/monitor.pid" 2>/dev/null || echo "")
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                kill "$pid"
                rm -f "$LOG_DIR/monitor.pid"
                echo "Monitor stopped (PID: $pid)"
            else
                echo "Monitor not running"
                rm -f "$LOG_DIR/monitor.pid"
            fi
        else
            echo "Monitor not running"
        fi
        ;;
    
    status)
        if [ -f "$LOG_DIR/monitor.pid" ]; then
            pid=$(cat "$LOG_DIR/monitor.pid" 2>/dev/null || echo "")
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                echo "✅ Monitor running (PID: $pid)"
                echo ""
                echo "Recent logs:"
                tail -20 "$MONITOR_LOG"
            else
                echo "❌ Monitor not running (stale PID)"
                rm -f "$LOG_DIR/monitor.pid"
            fi
        else
            echo "❌ Monitor not running"
        fi
        ;;
    
    run)
        # Internal: run monitoring loop
        monitor_loop
        ;;
    
    *)
        echo "Usage: $0 {start|stop|status}"
        echo ""
        echo "  start  - Start monitoring in background"
        echo "  stop   - Stop monitoring"
        echo "  status - Check monitor status and show recent logs"
        exit 1
        ;;
esac
