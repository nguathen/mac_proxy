#!/usr/bin/env bash
# start_webui_daemon.sh
# Khởi động Web UI ở background mode

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

mkdir -p logs

PID_FILE="./logs/webui.pid"
LOG_FILE="./logs/webui.log"

# Kiểm tra nếu đã chạy
if [ -f "$PID_FILE" ]; then
    pid=$(cat "$PID_FILE")
    if kill -0 "$pid" 2>/dev/null; then
        echo "⚠️  Web UI already running (PID: $pid)"
        echo "   Access: http://127.0.0.1:5000"
        exit 0
    else
        rm -f "$PID_FILE"
    fi
fi

# Kiểm tra Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found"
    exit 1
fi

# Kiểm tra Flask
if ! python3 -c "import flask" 2>/dev/null; then
    echo "📦 Installing Flask..."
    pip3 install -r webui/requirements.txt
fi

# Kill process trên port 5000 nếu có
lsof -ti :5000 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

# Khởi động Web UI
echo "🌐 Starting Web UI in background..."
cd webui
nohup python3 app.py > "../$LOG_FILE" 2>&1 &
WEBUI_PID=$!
cd ..
echo "$WEBUI_PID" > "$PID_FILE"

# Đợi Web UI khởi động
sleep 2

# Kiểm tra
if kill -0 "$WEBUI_PID" 2>/dev/null; then
    echo "✅ Web UI started successfully (PID: $WEBUI_PID)"
    echo "   Access: http://127.0.0.1:5000"
    echo "   Logs: $LOG_FILE"
else
    echo "❌ Failed to start Web UI"
    rm -f "$PID_FILE"
    exit 1
fi

