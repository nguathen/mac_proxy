#!/usr/bin/env bash
# Script chạy speedtest cho 52 server LK của ProtonVPN
# Test cả HTTPS và SOCKS5 proxy của gost

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 ProtonVPN LK Servers Speed Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Kiểm tra Python
if ! command -v python3 &> /dev/null; then
    echo "❌ python3 not found"
    exit 1
fi

# Kiểm tra gost
if [ ! -f "bin/gost" ] && ! command -v gost &> /dev/null; then
    echo "❌ gost not found"
    exit 1
fi

# Kiểm tra ProtonVPN credentials
if [ ! -f "protonvpn_credentials.json" ]; then
    echo "⚠️  Warning: protonvpn_credentials.json not found"
fi

echo "🔍 Starting speed test for LK servers..."
echo "   This will test both HTTP and SOCKS5 proxies of gost"
echo "   Testing up to 52 servers"
echo ""

# Chạy test
python3 test_lk_servers_speedtest.py

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Test completed!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

