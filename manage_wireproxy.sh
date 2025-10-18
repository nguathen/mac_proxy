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

start_wireproxy() {
    log "🚀 Starting wireproxy instances..."
    
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
    
    # Cleanup any remaining wireproxy processes
    pkill -f "wireproxy.*wg1818" 2>/dev/null || true
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

