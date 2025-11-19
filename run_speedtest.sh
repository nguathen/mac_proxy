#!/usr/bin/env bash
# Script chạy speedtest giữa WARP và Gost 7890

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 WARP vs Gost 7890 Speed Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Kiểm tra WARP
echo "🔍 Checking WARP (port 8111)..."
if ! nc -z 127.0.0.1 8111 2>/dev/null; then
    echo "❌ WARP proxy (port 8111) is not running"
    echo "   Please start WARP: warp-cli connect"
    exit 1
fi
echo "✅ WARP proxy is running"
echo ""

# Kiểm tra Gost 7890
echo "🔍 Checking Gost 7890..."
if ! nc -z 127.0.0.1 7890 2>/dev/null; then
    echo "⚠️  Gost 7890 is not running, starting it..."
    ./manage_gost.sh start 7890
    sleep 3
fi
echo "✅ Gost 7890 is running"
echo ""

# Chạy test
echo "🧪 Running speed test..."
echo ""
python3 test_warp_gost_speed.py

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Test completed!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

