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
                
                # Kiểm tra WARP monitor
                if [ -f "$SERVICE_DIR/warp_monitor.sh" ]; then
                    cd "$SERVICE_DIR"
                    ./warp_monitor.sh status 2>/dev/null || echo "   • WARP monitor: Không chạy"
                fi
            else
                echo "❌ HAProxy 7890 không đang chạy"
            fi
        else
            echo "❌ HAProxy 7890 không đang chạy"
        fi
        ;;
    warp-status)
        cd "$SERVICE_DIR"
        if [ -f "warp_monitor.sh" ]; then
            ./warp_monitor.sh status
        else
            echo "❌ WARP monitor script không tìm thấy"
        fi
        ;;
    warp-check)
        cd "$SERVICE_DIR"
        if [ -f "warp_monitor.sh" ]; then
            ./warp_monitor.sh check
        else
            echo "❌ WARP monitor script không tìm thấy"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|install|uninstall|status|warp-status|warp-check}"
        echo ""
        echo "Commands:"
        echo "  start       - Khởi động HAProxy 7890"
        echo "  stop        - Dừng HAProxy 7890"
        echo "  install     - Cài đặt autostart (chạy khi Mac khởi động)"
        echo "  uninstall   - Gỡ autostart"
        echo "  status      - Kiểm tra trạng thái"
        echo "  warp-status - Kiểm tra trạng thái WARP monitor"
        echo "  warp-check  - Kiểm tra và reconnect WARP nếu cần"
        exit 1
        ;;
esac

