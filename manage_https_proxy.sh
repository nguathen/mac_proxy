#!/usr/bin/env bash
# manage_https_proxy.sh
# Quản lý HTTPS proxy instances sử dụng 3proxy

set -euo pipefail

PROXY_BIN="./3proxy"
CFG_DIR="./https_config"
LOG_DIR="./logs"
PID_DIR="./logs"

# Ports cho HTTPS proxy
HTTPS_PORT_1=8181
HTTPS_PORT_2=8182

mkdir -p "$CFG_DIR" "$LOG_DIR"

timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(timestamp)] $*"; }

check_3proxy() {
    if [ ! -f "$PROXY_BIN" ]; then
        log "❌ 3proxy chưa được cài đặt"
        log "   File không tồn tại: $PROXY_BIN"
        exit 1
    fi
}

check_and_kill_port() {
    local port=$1
    local service_name=$2
    
    log "🔍 Checking port $port..."
    
    local pids=""
    
    if command -v lsof &> /dev/null; then
        pids=$(lsof -ti :$port 2>/dev/null || echo "")
    fi
    
    if [ -n "$pids" ]; then
        for pid in $pids; do
            if [ -n "$pid" ] && [ "$pid" != "0" ]; then
                local proc_name=$(ps -p $pid -o comm= 2>/dev/null || echo "unknown")
                log "⚠️  Found process on port $port: $proc_name (PID: $pid)"
                
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

create_3proxy_config() {
    local port=$1
    local config_file="${CFG_DIR}/3proxy_${port}.cfg"
    local log_file="${LOG_DIR}/https_proxy_${port}.log"
    
    cat > "$config_file" <<EOF
# 3proxy configuration for HTTPS proxy on port $port
daemon
maxconn 1024
nscache 65536
timeouts 1 5 30 60 180 1800 15 60
log "$log_file" D
logformat "- +_L%t.%. %N.%p %E %U %C:%c %R:%r %O %I %h %T"
auth none
allow *

# HTTP/HTTPS Proxy
proxy -p${port} -a -n -i0.0.0.0 -e0.0.0.0
flush
EOF
    
    log "✅ Created config: $config_file"
}

start_https_proxy() {
    log "🚀 Starting HTTPS proxy instances..."
    
    check_3proxy
    
    # Start HTTPS proxy 1
    check_and_kill_port $HTTPS_PORT_1 "HTTPS Proxy 1"
    
    create_3proxy_config $HTTPS_PORT_1
    
    if [ -f "$PID_DIR/https_proxy_${HTTPS_PORT_1}.pid" ] && kill -0 $(cat "$PID_DIR/https_proxy_${HTTPS_PORT_1}.pid") 2>/dev/null; then
        log "⚠️  HTTPS Proxy 1 already running"
    else
        nohup "$PROXY_BIN" "${CFG_DIR}/3proxy_${HTTPS_PORT_1}.cfg" > "$LOG_DIR/https_proxy_${HTTPS_PORT_1}_stdout.log" 2>&1 &
        echo $! > "$PID_DIR/https_proxy_${HTTPS_PORT_1}.pid"
        log "✅ HTTPS Proxy 1 started (PID: $!, port $HTTPS_PORT_1)"
    fi
    
    # Start HTTPS proxy 2
    check_and_kill_port $HTTPS_PORT_2 "HTTPS Proxy 2"
    
    create_3proxy_config $HTTPS_PORT_2
    
    if [ -f "$PID_DIR/https_proxy_${HTTPS_PORT_2}.pid" ] && kill -0 $(cat "$PID_DIR/https_proxy_${HTTPS_PORT_2}.pid") 2>/dev/null; then
        log "⚠️  HTTPS Proxy 2 already running"
    else
        nohup "$PROXY_BIN" "${CFG_DIR}/3proxy_${HTTPS_PORT_2}.cfg" > "$LOG_DIR/https_proxy_${HTTPS_PORT_2}_stdout.log" 2>&1 &
        echo $! > "$PID_DIR/https_proxy_${HTTPS_PORT_2}.pid"
        log "✅ HTTPS Proxy 2 started (PID: $!, port $HTTPS_PORT_2)"
    fi
    
    sleep 2
    status_https_proxy
}

stop_https_proxy() {
    log "🛑 Stopping HTTPS proxy instances..."
    
    # Stop HTTPS proxy 1
    if [ -f "$PID_DIR/https_proxy_${HTTPS_PORT_1}.pid" ]; then
        pid=$(cat "$PID_DIR/https_proxy_${HTTPS_PORT_1}.pid")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null && log "✅ Stopped HTTPS proxy 1 (PID: $pid)"
            rm -f "$PID_DIR/https_proxy_${HTTPS_PORT_1}.pid"
        else
            log "⚠️  HTTPS proxy 1 not running (stale PID)"
            rm -f "$PID_DIR/https_proxy_${HTTPS_PORT_1}.pid"
        fi
    fi
    
    # Stop HTTPS proxy 2
    if [ -f "$PID_DIR/https_proxy_${HTTPS_PORT_2}.pid" ]; then
        pid=$(cat "$PID_DIR/https_proxy_${HTTPS_PORT_2}.pid")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null && log "✅ Stopped HTTPS proxy 2 (PID: $pid)"
            rm -f "$PID_DIR/https_proxy_${HTTPS_PORT_2}.pid"
        else
            log "⚠️  HTTPS proxy 2 not running (stale PID)"
            rm -f "$PID_DIR/https_proxy_${HTTPS_PORT_2}.pid"
        fi
    fi
    
    # Cleanup any remaining processes
    log "🧹 Cleaning up any remaining processes on ports $HTTPS_PORT_1 and $HTTPS_PORT_2..."
    
    if command -v lsof &> /dev/null; then
        lsof -ti :$HTTPS_PORT_1 2>/dev/null | xargs kill -9 2>/dev/null || true
        lsof -ti :$HTTPS_PORT_2 2>/dev/null | xargs kill -9 2>/dev/null || true
    fi
    
    pkill -9 -f "3proxy.*3proxy_818" 2>/dev/null || true
    
    log "✅ Cleanup complete"
}

restart_https_proxy() {
    log "♻️  Restarting HTTPS proxy instances..."
    stop_https_proxy
    sleep 2
    start_https_proxy
}

status_https_proxy() {
    log "📊 HTTPS Proxy Status:"
    
    # Check HTTPS proxy 1
    if [ -f "$PID_DIR/https_proxy_${HTTPS_PORT_1}.pid" ]; then
        pid=$(cat "$PID_DIR/https_proxy_${HTTPS_PORT_1}.pid")
        if kill -0 "$pid" 2>/dev/null; then
            log "  ✅ HTTPS Proxy 1 (port $HTTPS_PORT_1): Running (PID: $pid)"
            # Test connection
            if timeout 5 bash -c "curl -s --max-time 3 -x http://127.0.0.1:$HTTPS_PORT_1 https://api.ipify.org" &>/dev/null; then
                log "     🌐 Connection: OK"
            else
                log "     ⚠️  Connection: Failed"
            fi
        else
            log "  ❌ HTTPS Proxy 1: Not running"
        fi
    else
        log "  ❌ HTTPS Proxy 1: Not running"
    fi
    
    # Check HTTPS proxy 2
    if [ -f "$PID_DIR/https_proxy_${HTTPS_PORT_2}.pid" ]; then
        pid=$(cat "$PID_DIR/https_proxy_${HTTPS_PORT_2}.pid")
        if kill -0 "$pid" 2>/dev/null; then
            log "  ✅ HTTPS Proxy 2 (port $HTTPS_PORT_2): Running (PID: $pid)"
            # Test connection
            if timeout 5 bash -c "curl -s --max-time 3 -x http://127.0.0.1:$HTTPS_PORT_2 https://api.ipify.org" &>/dev/null; then
                log "     🌐 Connection: OK"
            else
                log "     ⚠️  Connection: Failed"
            fi
        else
            log "  ❌ HTTPS Proxy 2: Not running"
        fi
    else
        log "  ❌ HTTPS Proxy 2: Not running"
    fi
}

case "${1:-}" in
    start)
        start_https_proxy
        ;;
    stop)
        stop_https_proxy
        ;;
    restart)
        restart_https_proxy
        ;;
    status)
        status_https_proxy
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac

