#!/bin/bash
# start_auto_updater.sh
# Script để chạy auto credential updater như daemon

BASE_DIR="$(dirname "$0")"
PID_FILE="$BASE_DIR/logs/auto_updater.pid"
LOG_FILE="$BASE_DIR/logs/auto_updater.log"

start_auto_updater() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo "⚠️  Auto updater already running (PID: $pid)"
            return 1
        else
            echo "🧹 Removing stale PID file"
            rm -f "$PID_FILE"
        fi
    fi
    
    echo "🚀 Starting auto credential updater..."
    cd "$BASE_DIR"
    nohup python3 auto_credential_updater.py start > "$LOG_FILE" 2>&1 &
    local pid=$!
    echo $pid > "$PID_FILE"
    echo "✅ Auto updater started (PID: $pid)"
    echo "📝 Log file: $LOG_FILE"
}

stop_auto_updater() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            echo "✅ Auto updater stopped (PID: $pid)"
        else
            echo "⚠️  Auto updater not running (stale PID)"
        fi
        rm -f "$PID_FILE"
    else
        echo "⚠️  Auto updater not running"
    fi
}

status_auto_updater() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo "✅ Auto updater running (PID: $pid)"
            echo "📝 Log file: $LOG_FILE"
            if [ -f "$LOG_FILE" ]; then
                echo "📋 Recent logs:"
                tail -10 "$LOG_FILE"
            fi
        else
            echo "⚠️  Auto updater not running (stale PID)"
            rm -f "$PID_FILE"
        fi
    else
        echo "⚠️  Auto updater not running"
    fi
}

case "${1:-}" in
    start)
        start_auto_updater
        ;;
    stop)
        stop_auto_updater
        ;;
    restart)
        stop_auto_updater
        sleep 2
        start_auto_updater
        ;;
    status)
        status_auto_updater
        ;;
    cleanup)
        echo "🧹 Manual cleanup unused services..."
        cd "$BASE_DIR"
        python3 auto_credential_updater.py cleanup
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|cleanup}"
        echo "  start   - Start auto credential updater daemon"
        echo "  stop    - Stop auto credential updater daemon"
        echo "  restart - Restart auto credential updater daemon"
        echo "  status  - Check auto credential updater status"
        echo "  cleanup - Manual cleanup unused services"
        exit 1
        ;;
esac
