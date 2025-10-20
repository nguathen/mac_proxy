#!/usr/bin/env bash
# manage_wireproxy.sh
# Quản lý wireproxy instances (auto-detect)

set -euo pipefail

WIREPROXY_BIN="./wireproxy"
LOG_DIR="./logs"
PID_DIR="./logs"

mkdir -p "$LOG_DIR"

timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(timestamp)] $*"; }

# Auto-detect wireproxy config files
get_wireproxy_configs() {
    # Find all wg*.conf files and extract port numbers
    local configs=()
    for conf in wg*.conf; do
        if [ -f "$conf" ]; then
            # Extract port from BindAddress line
            local port=$(grep -E "^BindAddress" "$conf" | grep -oE '[0-9]+$' || echo "")
            if [ -n "$port" ]; then
                configs+=("$conf:$port")
            fi
        fi
    done
    echo "${configs[@]}"
}

check_and_kill_port() {
    local port=$1
    local service_name=$2
    
    log "🔍 Checking port $port..."
    
    # Tìm process đang sử dụng port (macOS/Linux compatible)
    local pids=""
    
    # Try lsof first (macOS/Linux)
    if command -v lsof &> /dev/null; then
        pids=$(lsof -ti :$port 2>/dev/null || echo "")
    fi
    
    # Try netstat if lsof not available (Linux)
    if [ -z "$pids" ] && command -v netstat &> /dev/null; then
        pids=$(netstat -tlnp 2>/dev/null | grep ":$port " | awk '{print $7}' | cut -d'/' -f1 || echo "")
    fi
    
    # Try ss if available (Linux)
    if [ -z "$pids" ] && command -v ss &> /dev/null; then
        pids=$(ss -tlnp 2>/dev/null | grep ":$port " | grep -oP 'pid=\K[0-9]+' || echo "")
    fi
    
    if [ -n "$pids" ]; then
        for pid in $pids; do
            if [ -n "$pid" ] && [ "$pid" != "0" ]; then
                # Get process name
                local proc_name=$(ps -p $pid -o comm= 2>/dev/null || echo "unknown")
                log "⚠️  Found process on port $port: $proc_name (PID: $pid)"
                
                # Kill the process
                if kill -9 $pid 2>/dev/null; then
                    log "✅ Killed process $pid on port $port"
                else
                    log "❌ Failed to kill process $pid (may need sudo)"
                fi
            fi
        done
        sleep 1
    else
        log "✅ Port $port is free"
    fi
}

start_wireproxy() {
    log "🚀 Starting wireproxy instances..."
    
    local configs=($(get_wireproxy_configs))
    
    if [ ${#configs[@]} -eq 0 ]; then
        log "❌ No wireproxy config files found (wg*.conf)"
        return 1
    fi
    
    local instance=1
    for config_info in "${configs[@]}"; do
        IFS=':' read -r conf_file port <<< "$config_info"
        
        # Check and kill any process using this port
        check_and_kill_port "$port" "Wireproxy $instance"
        
        # Start wireproxy instance
        local pid_file="$PID_DIR/wireproxy${instance}.pid"
        
        if [ -f "$pid_file" ] && kill -0 $(cat "$pid_file") 2>/dev/null; then
            log "⚠️  Wireproxy $instance already running"
        else
            nohup "$WIREPROXY_BIN" -c "$conf_file" > "$LOG_DIR/wireproxy${instance}.log" 2>&1 &
            local pid=$!
            echo $pid > "$pid_file"
            log "✅ Wireproxy $instance started (PID: $pid, port $port, config: $conf_file)"
        fi
        
        ((instance++))
    done
    
    sleep 2
    status_wireproxy
}

stop_wireproxy() {
    log "🛑 Stopping wireproxy instances..."
    
    # Find all wireproxy PID files
    local configs=($(get_wireproxy_configs))
    local instance=1
    local stopped_any=false
    
    # Stop all wireproxy instances
    for pid_file in "$PID_DIR"/wireproxy*.pid; do
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null && log "✅ Stopped wireproxy $instance (PID: $pid)"
                stopped_any=true
            else
                log "⚠️  Wireproxy $instance not running (stale PID)"
            fi
            rm -f "$pid_file"
            ((instance++))
        fi
    done
    
    if [ "$stopped_any" = false ] && [ ! -f "$PID_DIR"/wireproxy*.pid ]; then
        log "⚠️  No wireproxy instances running"
    fi
    
    # Cleanup any remaining wireproxy processes on detected ports
    if [ ${#configs[@]} -gt 0 ]; then
        log "🧹 Cleaning up any remaining processes on ports..."
        
        for config_info in "${configs[@]}"; do
            IFS=':' read -r conf_file port <<< "$config_info"
            
            if command -v lsof &> /dev/null; then
                lsof -ti ":$port" 2>/dev/null | xargs kill -9 2>/dev/null || true
            fi
        done
    fi
    
    # Also try to kill by process name pattern
    pkill -9 -f "wireproxy.*wg" 2>/dev/null || true
    
    log "✅ Cleanup complete"
}

restart_wireproxy() {
    log "♻️  Restarting wireproxy instances..."
    stop_wireproxy
    sleep 2
    start_wireproxy
}

status_wireproxy() {
    log "📊 Wireproxy Status:"
    
    local configs=($(get_wireproxy_configs))
    
    if [ ${#configs[@]} -eq 0 ]; then
        log "  ❌ No wireproxy config files found"
        return 1
    fi
    
    local instance=1
    local any_running=false
    
    for config_info in "${configs[@]}"; do
        IFS=':' read -r conf_file port <<< "$config_info"
        local pid_file="$PID_DIR/wireproxy${instance}.pid"
        
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                log "  ✅ Wireproxy $instance (port $port): Running (PID: $pid)"
                any_running=true
                
                # Test connection
                if timeout 15 bash -c "curl -s --max-time 10 -x socks5h://127.0.0.1:$port https://api.ipify.org" &>/dev/null; then
                    log "     🌐 Connection: OK"
                else
                    log "     ⚠️  Connection: Failed (may need more time to establish)"
                fi
            else
                log "  ❌ Wireproxy $instance (port $port): Not running"
            fi
        else
            log "  ❌ Wireproxy $instance (port $port): Not running"
        fi
        
        ((instance++))
    done
    
    if [ "$any_running" = false ]; then
        log "  ⚠️  No wireproxy instances are running"
    fi
}

case "${1:-}" in
    start)
        start_wireproxy
        ;;
    stop)
        stop_wireproxy
        ;;
    restart)
        restart_wireproxy
        ;;
    status)
        status_wireproxy
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac

