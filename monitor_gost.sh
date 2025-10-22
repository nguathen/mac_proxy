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

# Gost ports được quản lý động dựa trên config files

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
    
    # Initialize counters for all configured ports
    for config_file in "$LOG_DIR"/gost_*.config; do
        if [ -f "$config_file" ]; then
            local port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
            fail_counts["$port"]=0
        fi
    done
    
    while true; do
        for config_file in "$LOG_DIR"/gost_*.config; do
            if [ -f "$config_file" ]; then
                local port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
                # Test connection
                if test_connection "$port"; then
                    # Success - reset counter
                    if [ "${fail_counts[$port]}" -gt 0 ]; then
                        log "✅ Gost port $port recovered"
                    fi
                    fail_counts["$port"]=0
                else
                    # Failed - increment counter
                    ((fail_counts["$port"]++))
                    local count=${fail_counts[$port]}
                    
                    log "⚠️  Gost port $port failed ($count/$FAIL_THRESHOLD)"
                    
                    # Check if threshold reached
                    if [ "$count" -ge "$FAIL_THRESHOLD" ]; then
                        log "🔄 Restarting gost port $port - threshold reached"
                        
                        # Restart specific service
                        local pid_file="$LOG_DIR/gost_${port}.pid"
                    
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
                        
                        # Start using manage_gost.sh
                        ./manage_gost.sh restart-port "$port"
                        
                        log "✅ Gost port $port restarted"
                        
                        # Reset counter
                        fail_counts["$port"]=0
                    fi
                fi
            fi
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
