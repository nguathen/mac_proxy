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

