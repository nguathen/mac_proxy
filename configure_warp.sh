#!/usr/bin/env bash
# configure_warp.sh
# Script cấu hình Cloudflare WARP sau khi cài đặt

set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚙️  Configuring Cloudflare WARP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if WARP is installed
if ! command -v warp-cli &> /dev/null; then
    echo "❌ WARP CLI chưa được cài đặt"
    echo "   Chạy: sudo ./install_warp_manual.sh"
    exit 1
fi

echo "✅ WARP CLI found: $(command -v warp-cli)"
echo ""

# Wait for WARP daemon to be ready
echo "⏳ Waiting for WARP daemon to be ready..."
WAIT_COUNT=0
MAX_WAIT=30
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if warp-cli status &>/dev/null; then
        break
    fi
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo "⚠️  WARP daemon may not be ready. Continuing anyway..."
fi

# Register if needed
echo "📋 Checking WARP registration..."
ACCOUNT_STATUS=$(warp-cli account 2>&1 || echo "")
if echo "$ACCOUNT_STATUS" | grep -qi "missing\|not registered\|register\|No account"; then
    echo "📝 Registering WARP..."
    if warp-cli registration new 2>&1 | grep -qi "success\|ok\|registered"; then
        echo "✅ WARP registered"
    elif warp-cli register 2>&1 | grep -qi "success\|ok\|registered"; then
        echo "✅ WARP registered"
    else
        echo "⚠️  WARP registration may have failed"
    fi
    sleep 2
else
    echo "✅ WARP already registered"
fi

# Set proxy mode
echo ""
echo "⚙️  Setting WARP to proxy mode..."

# Set proxy mode
echo "📝 Setting WARP to proxy mode..."
warp-cli mode proxy 2>&1 | grep -v "Success" || true
sleep 2
echo "✅ WARP mode set to proxy"

# Set proxy port to 8111
echo ""
echo "⚙️  Setting WARP proxy port to 8111..."
warp-cli proxy port 8111 2>&1 | grep -v "Success" || true
sleep 2
echo "✅ WARP proxy port set to 8111"

# Connect WARP
echo ""
echo "🔌 Connecting WARP..."
CURRENT_STATUS=$(warp-cli status 2>/dev/null | grep -i "status" | awk '{print $2}' || echo "")
if echo "$CURRENT_STATUS" | grep -qi "disconnected"; then
    warp-cli connect 2>&1 | grep -v "Success" || true
    sleep 3
    echo "✅ WARP connected"
else
    echo "✅ WARP already connected"
fi

# Verify connection
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Verifying WARP configuration..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

WARP_STATUS=$(warp-cli status 2>/dev/null || echo "")
echo "WARP Status:"
echo "$WARP_STATUS"
echo ""

PROXY_STATUS=$(warp-cli proxy status 2>/dev/null || echo "")
echo "Proxy Status:"
echo "$PROXY_STATUS"
echo ""

if echo "$WARP_STATUS" | grep -qi "connected"; then
    # Test proxy port
    if nc -z 127.0.0.1 8111 2>/dev/null; then
        echo "✅ WARP proxy port 8111 is listening"
        
        # Test proxy connection
        echo ""
        echo "🧪 Testing WARP proxy..."
        TEST_IP=$(curl -s --connect-timeout 5 --max-time 10 -x socks5h://127.0.0.1:8111 https://api.ipify.org 2>/dev/null || echo "")
        if [ -n "$TEST_IP" ]; then
            echo "✅ WARP proxy is working!"
            echo "   Your IP through WARP: $TEST_IP"
        else
            echo "⚠️  WARP proxy may not be working yet"
            echo "   Try again in a few seconds: curl -x socks5h://127.0.0.1:8111 https://api.ipify.org"
        fi
    else
        echo "⚠️  WARP proxy port 8111 is not listening yet"
        echo "   Wait a few seconds and try: curl -x socks5h://127.0.0.1:8111 https://api.ipify.org"
    fi
else
    echo "⚠️  WARP is not connected"
    echo "   Try: warp-cli connect"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ WARP Configuration Complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Useful commands:"
echo "   • Check status: warp-cli status"
echo "   • Check proxy: warp-cli proxy status"
echo "   • Connect: warp-cli connect"
echo "   • Disconnect: warp-cli disconnect"
echo "   • Test proxy: curl -x socks5h://127.0.0.1:8111 https://api.ipify.org"
echo ""

