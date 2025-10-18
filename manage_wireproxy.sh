#!/usr/bin/env bash
# manage_wireproxy.sh
# Quản lý wireproxy instances

set -euo pipefail

WIREPROXY_BIN="./wireproxy"
WG1_CONF="wg18181.conf"
WG2_CONF="wg18182.conf"
LOG_DIR="./logs"
PID_DIR="./logs"

mkdir -p "$LOG_DIR"

timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(timestamp)] $*"; }

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
    
    # Check and kill any process using port 18181
    check_and_kill_port 18181 "Wireproxy 1"
    
    # Check and kill any process using port 18182
    check_and_kill_port 18182 "Wireproxy 2"
    
    # Start wireproxy 1 (port 18181)
    if [ -f "$WG1_CONF" ]; then
        if [ -f "$PID_DIR/wireproxy1.pid" ] && kill -0 $(cat "$PID_DIR/wireproxy1.pid") 2>/dev/null; then
            log "⚠️  Wireproxy 1 already running"
        else
            nohup "$WIREPROXY_BIN" -c "$WG1_CONF" > "$LOG_DIR/wireproxy1.log" 2>&1 &
            echo $! > "$PID_DIR/wireproxy1.pid"
            log "✅ Wireproxy 1 started (PID: $!, port 18181)"
        fi
    else
        log "❌ Config file $WG1_CONF not found"
    fi
    
    # Start wireproxy 2 (port 18182)
    if [ -f "$WG2_CONF" ]; then
        if [ -f "$PID_DIR/wireproxy2.pid" ] && kill -0 $(cat "$PID_DIR/wireproxy2.pid") 2>/dev/null; then
            log "⚠️  Wireproxy 2 already running"
        else
            nohup "$WIREPROXY_BIN" -c "$WG2_CONF" > "$LOG_DIR/wireproxy2.log" 2>&1 &
            echo $! > "$PID_DIR/wireproxy2.pid"
            log "✅ Wireproxy 2 started (PID: $!, port 18182)"
        fi
    else
        log "❌ Config file $WG2_CONF not found"
    fi
    
    sleep 2
    status_wireproxy
}

stop_wireproxy() {
    log "🛑 Stopping wireproxy instances..."
    
    # Stop wireproxy 1
    if [ -f "$PID_DIR/wireproxy1.pid" ]; then
        pid=$(cat "$PID_DIR/wireproxy1.pid")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null && log "✅ Stopped wireproxy 1 (PID: $pid)"
            rm -f "$PID_DIR/wireproxy1.pid"
        else
            log "⚠️  Wireproxy 1 not running (stale PID)"
            rm -f "$PID_DIR/wireproxy1.pid"
        fi
    fi
    
    # Stop wireproxy 2
    if [ -f "$PID_DIR/wireproxy2.pid" ]; then
        pid=$(cat "$PID_DIR/wireproxy2.pid")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null && log "✅ Stopped wireproxy 2 (PID: $pid)"
            rm -f "$PID_DIR/wireproxy2.pid"
        else
            log "⚠️  Wireproxy 2 not running (stale PID)"
            rm -f "$PID_DIR/wireproxy2.pid"
        fi
    fi
    
    # Cleanup any remaining wireproxy processes on our ports
    log "🧹 Cleaning up any remaining processes on ports 18181 and 18182..."
    
    # Kill any process on port 18181
    if command -v lsof &> /dev/null; then
        lsof -ti :18181 2>/dev/null | xargs -r kill -9 2>/dev/null || true
        lsof -ti :18182 2>/dev/null | xargs -r kill -9 2>/dev/null || true
    fi
    
    # Also try to kill by process name pattern
    pkill -9 -f "wireproxy.*wg1818" 2>/dev/null || true
    
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
    
    # Check wireproxy 1
    if [ -f "$PID_DIR/wireproxy1.pid" ]; then
        pid=$(cat "$PID_DIR/wireproxy1.pid")
        if kill -0 "$pid" 2>/dev/null; then
            log "  ✅ Wireproxy 1 (port 18181): Running (PID: $pid)"
            # Test connection
            if timeout 5 bash -c "curl -s --max-time 3 -x socks5h://127.0.0.1:18181 https://api.ipify.org" &>/dev/null; then
                log "     🌐 Connection: OK"
            else
                log "     ⚠️  Connection: Failed"
            fi
        else
            log "  ❌ Wireproxy 1: Not running"
        fi
    else
        log "  ❌ Wireproxy 1: Not running"
    fi
    
    # Check wireproxy 2
    if [ -f "$PID_DIR/wireproxy2.pid" ]; then
        pid=$(cat "$PID_DIR/wireproxy2.pid")
        if kill -0 "$pid" 2>/dev/null; then
            log "  ✅ Wireproxy 2 (port 18182): Running (PID: $pid)"
            # Test connection
            if timeout 5 bash -c "curl -s --max-time 3 -x socks5h://127.0.0.1:18182 https://api.ipify.org" &>/dev/null; then
                log "     🌐 Connection: OK"
            else
                log "     ⚠️  Connection: Failed"
            fi
        else
            log "  ❌ Wireproxy 2: Not running"
        fi
    else
        log "  ❌ Wireproxy 2: Not running"
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

