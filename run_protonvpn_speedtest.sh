#!/usr/bin/env bash
# Script chạy speedtest giữa ProtonVPN HTTPS trực tiếp và Gost SOCKS5

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse arguments
if [ $# -lt 3 ]; then
    echo "Usage: $0 <server_host> <server_port> <gost_port>"
    echo "Example: $0 node-jp-33.protonvpn.net 4461 7891"
    echo ""
    echo "To get a server:"
    echo "  curl http://localhost:5000/api/protonvpn/best?country=JP | jq -r '.server.domain'"
    exit 1
fi

SERVER_HOST=$1
SERVER_PORT=$2
GOST_PORT=$3

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 ProtonVPN vs Gost Speed Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Kiểm tra Gost port
echo "🔍 Checking Gost $GOST_PORT..."
if ! nc -z 127.0.0.1 $GOST_PORT 2>/dev/null; then
    echo "⚠️  Gost $GOST_PORT is not running, starting it..."
    ./manage_gost.sh start $GOST_PORT
    sleep 5
fi
echo "✅ Gost $GOST_PORT is running"
echo ""

# Chạy test
echo "🧪 Running speed test..."
echo "   Server: $SERVER_HOST:$SERVER_PORT"
echo "   Gost Port: $GOST_PORT"
echo ""
python3 test_protonvpn_gost_speed.py "$SERVER_HOST" "$SERVER_PORT" "$GOST_PORT"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Test completed!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

