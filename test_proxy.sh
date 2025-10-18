#!/usr/bin/env bash
# test_proxy.sh
# Test HAProxy endpoints với nhiều request

set -euo pipefail

TEST_URL="${1:-https://api.ipify.org}"
TEST_COUNT="${2:-5}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 Testing HAProxy Proxies"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test URL: $TEST_URL"
echo "Test Count: $TEST_COUNT per proxy"
echo ""

test_proxy() {
    local port=$1
    local name=$2
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Testing $name (port $port)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    local success=0
    local failed=0
    local total_time=0
    
    for i in $(seq 1 $TEST_COUNT); do
        echo -n "Request $i/$TEST_COUNT: "
        
        start=$(date +%s%3N 2>/dev/null || echo $(($(date +%s) * 1000)))
        result=$(curl -s --max-time 10 -x socks5h://127.0.0.1:${port} "$TEST_URL" 2>/dev/null || echo "FAILED")
        end=$(date +%s%3N 2>/dev/null || echo $(($(date +%s) * 1000)))
        
        latency=$((end - start))
        
        if [ "$result" != "FAILED" ] && [ -n "$result" ]; then
            echo "✅ Success - IP: $result - Latency: ${latency}ms"
            success=$((success + 1))
            total_time=$((total_time + latency))
        else
            echo "❌ Failed"
            failed=$((failed + 1))
        fi
        
        sleep 0.5
    done
    
    echo ""
    echo "📊 Summary for $name:"
    echo "   Success: $success/$TEST_COUNT"
    echo "   Failed: $failed/$TEST_COUNT"
    
    if [ $success -gt 0 ]; then
        avg_time=$((total_time / success))
        echo "   Average Latency: ${avg_time}ms"
    fi
    
    echo ""
}

# Test HAProxy 1
test_proxy 7891 "HAProxy Instance 1"

# Test HAProxy 2
test_proxy 7892 "HAProxy Instance 2"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Testing Complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

