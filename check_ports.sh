#!/usr/bin/env bash
# check_ports.sh
# Kiểm tra và hiển thị process đang sử dụng ports 18181 và 18182

set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Checking Ports 18181 and 18182"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_port() {
    local port=$1
    echo ""
    echo "Port $port:"
    echo "─────────────────────────────────────"
    
    # Try lsof (macOS/Linux)
    if command -v lsof &> /dev/null; then
        result=$(lsof -i :$port 2>/dev/null || echo "")
        if [ -n "$result" ]; then
            echo "$result"
            
            # Get PID
            pid=$(echo "$result" | tail -n 1 | awk '{print $2}')
            if [ -n "$pid" ] && [ "$pid" != "PID" ]; then
                echo ""
                echo "Process details:"
                ps -p $pid -o pid,ppid,user,command 2>/dev/null || echo "Cannot get process details"
            fi
        else
            echo "✅ Port $port is FREE"
        fi
    # Try netstat (Linux)
    elif command -v netstat &> /dev/null; then
        result=$(netstat -tlnp 2>/dev/null | grep ":$port " || echo "")
        if [ -n "$result" ]; then
            echo "$result"
        else
            echo "✅ Port $port is FREE"
        fi
    # Try ss (Linux)
    elif command -v ss &> /dev/null; then
        result=$(ss -tlnp 2>/dev/null | grep ":$port " || echo "")
        if [ -n "$result" ]; then
            echo "$result"
        else
            echo "✅ Port $port is FREE"
        fi
    else
        echo "⚠️  No port checking tool available (lsof/netstat/ss)"
    fi
}

check_port 18181
check_port 18182

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💡 To kill a process:"
echo "   kill -9 <PID>"
echo ""
echo "💡 To kill all processes on a port:"
echo "   lsof -ti :18181 | xargs kill -9"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

