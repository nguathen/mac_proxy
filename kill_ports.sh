#!/usr/bin/env bash
# kill_ports.sh
# Kill tất cả process đang sử dụng ports 18181 và 18182

set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💀 Killing all processes on ports 18181 and 18182"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

kill_port() {
    local port=$1
    echo ""
    echo "Checking port $port..."
    
    if command -v lsof &> /dev/null; then
        pids=$(lsof -ti :$port 2>/dev/null || echo "")
        
        if [ -n "$pids" ]; then
            for pid in $pids; do
                proc_name=$(ps -p $pid -o comm= 2>/dev/null || echo "unknown")
                echo "  Found: $proc_name (PID: $pid)"
                
                if kill -9 $pid 2>/dev/null; then
                    echo "  ✅ Killed PID $pid"
                else
                    echo "  ❌ Failed to kill PID $pid (may need sudo)"
                fi
            done
        else
            echo "  ✅ Port $port is already free"
        fi
    elif command -v fuser &> /dev/null; then
        # Linux alternative using fuser
        if fuser $port/tcp 2>/dev/null; then
            fuser -k -9 $port/tcp 2>/dev/null && echo "  ✅ Killed processes on port $port"
        else
            echo "  ✅ Port $port is already free"
        fi
    else
        echo "  ⚠️  No tool available to kill port (lsof/fuser)"
    fi
}

kill_port 18181
kill_port 18182

# Also kill by process name pattern
echo ""
echo "Killing wireproxy processes by name pattern..."
if pkill -9 -f "wireproxy.*wg1818" 2>/dev/null; then
    echo "✅ Killed wireproxy processes"
else
    echo "✅ No wireproxy processes found"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Done! Ports should be free now"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

