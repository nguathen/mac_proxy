#!/usr/bin/env bash
# stop_app.sh
# Dừng tất cả services được khởi động bởi MacProxy.app

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="$SCRIPT_DIR/logs/app_stop.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] $*" | tee -a "$LOG_FILE"
}

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "🛑 Stopping Mac Proxy App"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Dừng Auto Credential Updater
log "🛑 Stopping Auto Credential Updater..."
if [ -f "$SCRIPT_DIR/start_auto_updater.sh" ]; then
    chmod +x "$SCRIPT_DIR/start_auto_updater.sh"
    "$SCRIPT_DIR/start_auto_updater.sh" stop >> "$LOG_FILE" 2>&1 || true
    log "✅ Auto Credential Updater stopped"
else
    log "⚠️  Auto Credential Updater script not found"
fi

# Dừng WebUI
log "🛑 Stopping Web UI..."
PID_FILE="$SCRIPT_DIR/logs/webui.pid"
if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE" 2>/dev/null || echo "")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null && log "✅ Stopped Web UI (PID: $pid)"
        rm -f "$PID_FILE"
    else
        log "⚠️  Web UI not running (stale PID)"
        rm -f "$PID_FILE"
    fi
else
    log "⚠️  Web UI not running"
fi

# Cleanup any remaining process on port 5000
lsof -ti :5000 2>/dev/null | xargs kill -9 2>/dev/null || true
log "✅ Cleaned up port 5000"

# Dừng HAProxy Monitor
log "🛑 Stopping HAProxy Monitor..."
if [ -f "$SCRIPT_DIR/services/haproxy_7890/haproxy_monitor.sh" ]; then
    cd "$SCRIPT_DIR/services/haproxy_7890"
    chmod +x haproxy_monitor.sh
    ./haproxy_monitor.sh stop >> "$SCRIPT_DIR/logs/haproxy_monitor_stop.log" 2>&1 || true
    cd "$SCRIPT_DIR"
    log "✅ HAProxy Monitor stopped"
else
    log "⚠️  HAProxy Monitor script not found"
fi

# Dừng WARP Monitor
log "🛑 Stopping WARP Monitor..."
if [ -f "$SCRIPT_DIR/services/haproxy_7890/warp_monitor.sh" ]; then
    cd "$SCRIPT_DIR/services/haproxy_7890"
    chmod +x warp_monitor.sh
    ./warp_monitor.sh stop >> "$SCRIPT_DIR/logs/warp_monitor_stop.log" 2>&1 || true
    cd "$SCRIPT_DIR"
    log "✅ WARP Monitor stopped"
else
    log "⚠️  WARP Monitor script not found"
fi

# Dừng HAProxy 7890
log "🛑 Stopping HAProxy 7890..."
if [ -f "$SCRIPT_DIR/services/haproxy_7890/stop_haproxy_7890.sh" ]; then
    cd "$SCRIPT_DIR/services/haproxy_7890"
    chmod +x stop_haproxy_7890.sh
    ./stop_haproxy_7890.sh >> "$SCRIPT_DIR/logs/haproxy_7890_stop.log" 2>&1 || true
    cd "$SCRIPT_DIR"
    log "✅ HAProxy 7890 stopped"
else
    log "⚠️  HAProxy 7890 stop script not found"
fi

# Dừng Gost Monitor
log "🛑 Stopping Gost Monitor..."
if [ -f "$SCRIPT_DIR/gost_monitor.sh" ]; then
    chmod +x "$SCRIPT_DIR/gost_monitor.sh"
    "$SCRIPT_DIR/gost_monitor.sh" stop >> "$SCRIPT_DIR/logs/gost_monitor.log" 2>&1 || true
    log "✅ Gost Monitor stopped"
else
    log "⚠️  Gost Monitor script not found"
fi

# Dừng Gost Services
log "🛑 Stopping Gost Services..."
if [ -f "$SCRIPT_DIR/manage_gost.sh" ]; then
    chmod +x "$SCRIPT_DIR/manage_gost.sh"
    "$SCRIPT_DIR/manage_gost.sh" stop >> "$LOG_FILE" 2>&1 || true
    log "✅ Gost Services stopped"
else
    log "⚠️  Gost management script not found"
fi

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "✅ App stopped successfully"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

