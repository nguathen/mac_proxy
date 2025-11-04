#!/usr/bin/env bash
# haproxy_7890.sh
# Helper script để quản lý HAProxy 7890 service

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$SCRIPT_DIR/services/haproxy_7890"

if [ ! -d "$SERVICE_DIR" ]; then
    echo "❌ Không tìm thấy service directory: $SERVICE_DIR"
    exit 1
fi

case "${1:-}" in
    start)
        cd "$SERVICE_DIR"
        ./start_haproxy_7890.sh
        ;;
    stop)
        cd "$SERVICE_DIR"
        ./stop_haproxy_7890.sh
        ;;
    install)
        cd "$SERVICE_DIR"
        ./install_haproxy7890_autostart.sh
        ;;
    uninstall)
        cd "$SERVICE_DIR"
        ./uninstall_haproxy7890_autostart.sh
        ;;
    status)
        PID_FILE="$SERVICE_DIR/logs/haproxy_7890.pid"
        if [ -f "$PID_FILE" ]; then
            pid=$(cat "$PID_FILE" 2>/dev/null || echo "")
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                echo "✅ HAProxy 7890 đang chạy (PID: $pid)"
                echo "   • SOCKS5: socks5://0.0.0.0:7890"
            else
                echo "❌ HAProxy 7890 không đang chạy"
            fi
        else
            echo "❌ HAProxy 7890 không đang chạy"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|install|uninstall|status}"
        echo ""
        echo "Commands:"
        echo "  start      - Khởi động HAProxy 7890"
        echo "  stop       - Dừng HAProxy 7890"
        echo "  install    - Cài đặt autostart (chạy khi Mac khởi động)"
        echo "  uninstall  - Gỡ autostart"
        echo "  status     - Kiểm tra trạng thái"
        exit 1
        ;;
esac

