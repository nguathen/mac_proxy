#!/usr/bin/env bash
# launch_app.sh
# Script launcher để chạy WebUI và WARP monitor

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="$SCRIPT_DIR/logs/app_launcher.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] $*" | tee -a "$LOG_FILE"
}

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "🚀 Starting Mac Proxy App"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Khởi động HAProxy 7890
log "🚀 Starting HAProxy 7890..."
if [ -f "$SCRIPT_DIR/services/haproxy_7890/start_haproxy_7890.sh" ]; then
    cd "$SCRIPT_DIR/services/haproxy_7890"
    chmod +x start_haproxy_7890.sh
    ./start_haproxy_7890.sh >> "$SCRIPT_DIR/logs/haproxy_7890_launch.log" 2>&1 || true
    cd "$SCRIPT_DIR"
    log "✅ HAProxy 7890 started"
else
    log "⚠️  HAProxy 7890 script not found"
fi

# Đợi một chút để HAProxy khởi động
sleep 2

# Khởi động WebUI
log "🌐 Starting Web UI..."
if [ -f "$SCRIPT_DIR/start_webui_daemon.sh" ]; then
    chmod +x "$SCRIPT_DIR/start_webui_daemon.sh"
    "$SCRIPT_DIR/start_webui_daemon.sh" >> "$LOG_FILE" 2>&1
    log "✅ Web UI started"
else
    log "❌ Web UI script not found"
fi

# Đợi một chút để WebUI khởi động
sleep 3

# Khởi động Auto Credential Updater (tự động clear sau 5 phút)
log "🔄 Starting Auto Credential Updater..."
if [ -f "$SCRIPT_DIR/start_auto_updater.sh" ]; then
    chmod +x "$SCRIPT_DIR/start_auto_updater.sh"
    "$SCRIPT_DIR/start_auto_updater.sh" start >> "$LOG_FILE" 2>&1 || true
    log "✅ Auto Credential Updater started"
else
    log "⚠️  Auto Credential Updater script not found"
fi

# Khởi động HAProxy monitor (tự động restart nếu lỗi)
log "🛡️  Starting HAProxy Monitor..."
if [ -f "$SCRIPT_DIR/services/haproxy_7890/haproxy_monitor.sh" ]; then
    cd "$SCRIPT_DIR/services/haproxy_7890"
    chmod +x haproxy_monitor.sh
    ./haproxy_monitor.sh start >> "$SCRIPT_DIR/logs/haproxy_monitor_launchd.log" 2>&1 || true
    cd "$SCRIPT_DIR"
    log "✅ HAProxy Monitor started"
else
    log "⚠️  HAProxy Monitor script not found"
fi

# Khởi động WARP monitor
log "🛡️  Starting WARP Monitor..."
if [ -f "$SCRIPT_DIR/services/haproxy_7890/warp_monitor.sh" ]; then
    cd "$SCRIPT_DIR/services/haproxy_7890"
    chmod +x warp_monitor.sh
    ./warp_monitor.sh start >> "$SCRIPT_DIR/logs/warp_monitor_launchd.log" 2>&1 || true
    cd "$SCRIPT_DIR"
    log "✅ WARP Monitor started"
else
    log "⚠️  WARP Monitor script not found"
fi

log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "✅ App started successfully"
log "📊 Web UI: http://127.0.0.1:5000"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Hiển thị thông báo thành công
osascript -e 'display notification "Web UI: http://127.0.0.1:5000" with title "Mac Proxy" subtitle "App đã khởi động thành công"' 2>/dev/null || true

# Mở trình duyệt
sleep 2
open "http://127.0.0.1:5000" 2>/dev/null || true

