#!/usr/bin/env bash
# start_webui.sh
# Khởi động Web UI để quản lý HAProxy và Wireproxy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Starting HAProxy & Wireproxy Web UI"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Kiểm tra Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3."
    exit 1
fi

echo "✅ Python 3 found"

# Kiểm tra và cài đặt Flask
if ! python3 -c "import flask" 2>/dev/null; then
    echo "📦 Installing Flask..."
    pip3 install -r webui/requirements.txt
fi

echo "✅ Flask installed"

# Cấp quyền thực thi cho các scripts
chmod +x manage_wireproxy.sh start_all.sh stop_all.sh status_all.sh 2>/dev/null || true

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Web UI is starting..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Access Web UI at:"
echo "   • Local:    http://127.0.0.1:5000"
echo "   • Network:  http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'YOUR_IP'):5000"
echo ""
echo "⚙️  Features:"
echo "   • View service status (Wireproxy & HAProxy)"
echo "   • Start/Stop/Restart services"
echo "   • Edit Wireproxy configurations"
echo "   • View logs"
echo "   • Test proxy connections"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Khởi động Flask app
cd webui
python3 app.py

