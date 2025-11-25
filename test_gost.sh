#!/usr/bin/env bash
# test_gost.sh
# Script để test Gost configuration

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 Testing Gost Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if Gost is installed
if ! command -v gost &> /dev/null; then
    echo "❌ Gost is not installed"
    echo "   Run: cd $SCRIPT_DIR && ./install_linux.sh"
    exit 1
fi

echo "✅ Gost found: $(command -v gost)"
echo ""

# Check if config exists
if [ ! -f "config/gost_7891.config" ]; then
    echo "❌ Config file not found: config/gost_7891.config"
    echo ""
    echo "Creating test config..."
    mkdir -p config
    cat > config/gost_7891.config <<EOF
{
    "port": "7891",
    "provider": "test",
    "country": "test",
    "proxy_url": "socks5://127.0.0.1:8111",
    "proxy_host": "127.0.0.1",
    "proxy_port": "8111",
    "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
    echo "✅ Test config created"
    echo ""
fi

echo "✅ Config file found: config/gost_7891.config"
echo ""

# Read config
PROXY_URL=$(cat config/gost_7891.config | jq -r '.proxy_url // ""' 2>/dev/null || echo "")
PORT=$(cat config/gost_7891.config | jq -r '.port // "7891"' 2>/dev/null || echo "7891")

if [ -z "$PROXY_URL" ] || [ "$PROXY_URL" = "null" ]; then
    echo "❌ Invalid config: proxy_url is empty"
    exit 1
fi

echo "📋 Config details:"
echo "   Port: $PORT"
echo "   Proxy URL: $PROXY_URL"
echo ""

# Check if port is already in use
PORT_IN_USE=false
if command -v lsof &> /dev/null; then
    if lsof -i :$PORT >/dev/null 2>&1; then
        PORT_IN_USE=true
        echo "⚠️  Port $PORT is already in use:"
        lsof -i :$PORT
    fi
elif command -v ss &> /dev/null; then
    if ss -tlnp | grep -q ":$PORT "; then
        PORT_IN_USE=true
        echo "⚠️  Port $PORT is already in use:"
        ss -tlnp | grep ":$PORT "
    fi
elif command -v netstat &> /dev/null; then
    if netstat -tlnp 2>/dev/null | grep -q ":$PORT "; then
        PORT_IN_USE=true
        echo "⚠️  Port $PORT is already in use:"
        netstat -tlnp 2>/dev/null | grep ":$PORT "
    fi
fi

if [ "$PORT_IN_USE" = true ]; then
    echo ""
    read -p "Do you want to kill the process and restart? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if command -v lsof &> /dev/null; then
            lsof -ti :$PORT | xargs kill -9 2>/dev/null || true
        elif command -v ss &> /dev/null; then
            ss -tlnp | grep ":$PORT " | grep -oP 'pid=\K[0-9]+' | xargs kill -9 2>/dev/null || true
        elif command -v netstat &> /dev/null; then
            netstat -tlnp 2>/dev/null | grep ":$PORT " | awk '{print $7}' | cut -d'/' -f1 | xargs kill -9 2>/dev/null || true
        fi
        sleep 1
    else
        exit 1
    fi
fi

# Start Gost
echo "🚀 Starting Gost on port $PORT..."
echo "   Command: gost -L socks5://:$PORT -F $PROXY_URL"
echo ""

mkdir -p logs
nohup gost -L socks5://:$PORT -F "$PROXY_URL" > logs/gost_${PORT}_test.log 2>&1 &
GOST_PID=$!

sleep 2

# Check if Gost started successfully
if kill -0 "$GOST_PID" 2>/dev/null; then
    echo "✅ Gost started successfully (PID: $GOST_PID)"
    echo ""
    echo "🧪 Testing proxy connection..."
    
    # Test the proxy
    if curl -s --connect-timeout 5 --max-time 10 -x "socks5h://127.0.0.1:$PORT" https://ipinfo.io/ip >/dev/null 2>&1; then
        IP=$(curl -s --connect-timeout 5 --max-time 10 -x "socks5h://127.0.0.1:$PORT" https://ipinfo.io/ip 2>/dev/null || echo "N/A")
        echo "✅ Proxy is working!"
        echo "   Your IP through proxy: $IP"
        echo ""
        echo "📊 Proxy endpoint: socks5://127.0.0.1:$PORT"
        echo "📝 Logs: logs/gost_${PORT}_test.log"
        echo ""
        echo "🛑 To stop Gost: kill $GOST_PID"
        echo "   Or: pkill -f 'gost.*socks5.*:$PORT'"
    else
        echo "⚠️  Proxy started but connection test failed"
        echo "   Check logs: logs/gost_${PORT}_test.log"
        echo "   PID: $GOST_PID"
        echo ""
        echo "💡 Make sure WARP proxy is running on port 8111:"
        echo "   nc -z 127.0.0.1 8111"
    fi
else
    echo "❌ Failed to start Gost"
    echo "   Check logs: logs/gost_${PORT}_test.log"
    if [ -f "logs/gost_${PORT}_test.log" ]; then
        echo ""
        echo "Last 10 lines of log:"
        tail -10 "logs/gost_${PORT}_test.log"
    fi
    exit 1
fi

