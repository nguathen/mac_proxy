#!/usr/bin/env bash
# status_all.sh
# Kiểm tra trạng thái tất cả services

set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Gost Proxy System Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Kiểm tra Auto Credential Updater
echo ""
echo "🔄 Auto Credential Updater:"
if [ -f "start_auto_updater.sh" ]; then
    chmod +x start_auto_updater.sh
    ./start_auto_updater.sh status
else
    echo "  ❌ Auto updater script not found"
fi

# Kiểm tra Gost instances
echo ""
echo "🔐 Gost Instances:"
for config_file in config/gost_*.config; do
    if [ -f "$config_file" ]; then
        port=$(basename "$config_file" .config | sed 's/gost_//')
        pid_file="logs/gost_${port}.pid"
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                echo "  ✅ Instance on port $port: Running (PID $pid)"
            else
                echo "  ❌ Instance on port $port: Dead (stale PID file)"
            fi
        else
            echo "  ❌ Instance on port $port: Not running"
        fi
    fi
done

# Kiểm tra listening ports
echo ""
echo "🔌 Listening Ports:"
for config_file in config/gost_*.config; do
    if [ -f "$config_file" ]; then
        port=$(basename "$config_file" .config | sed 's/gost_//')
        if lsof -i :$port > /dev/null 2>&1 || nc -z 127.0.0.1 $port 2>/dev/null; then
            echo "  ✅ Gost port $port: Listening"
        else
            echo "  ❌ Gost port $port: Not listening"
        fi
    fi
done

# Kiểm tra Cloudflare WARP
echo ""
echo "☁️  Cloudflare WARP (Fallback):"
if nc -z 127.0.0.1 8111 2>/dev/null; then
    ip=$(curl -s --max-time 5 -x socks5h://127.0.0.1:8111 https://ipinfo.io/ip 2>/dev/null || echo "N/A")
    if [ "$ip" != "N/A" ]; then
        echo "  ✅ WARP proxy (port 8111): Online (IP: $ip)"
    else
        echo "  ⚠️  WARP proxy (port 8111): Port open but not responding"
    fi
else
    echo "  ❌ WARP proxy (port 8111): Offline"
fi

# Test Gost endpoints
echo ""
echo "🧪 Gost Endpoint Tests:"
for config_file in config/gost_*.config; do
    if [ -f "$config_file" ]; then
        port=$(basename "$config_file" .config | sed 's/gost_//')
        if nc -z 127.0.0.1 $port 2>/dev/null; then
            ip=$(curl -s --max-time 8 -x socks5h://127.0.0.1:${port} https://ipinfo.io/ip 2>/dev/null || echo "N/A")
            if [ "$ip" != "N/A" ]; then
                echo "  ✅ Gost port $port: Working (IP: $ip)"
            else
                echo "  ⚠️  Gost port $port: Port open but proxy not working"
            fi
        else
            echo "  ❌ Gost port $port: Not accessible"
        fi
    fi
done

# Recent logs
echo ""
echo "📝 Recent Gost Monitor Logs:"
if [ -f "logs/gost_monitor.log" ]; then
    echo ""
    echo "  Gost Monitor (last 5 lines):"
    tail -n 5 "logs/gost_monitor.log" | sed 's/^/    /'
fi

if [ -f "logs/gost_7890_monitor.log" ]; then
    echo ""
    echo "  Gost 7890 Monitor (last 5 lines):"
    tail -n 5 "logs/gost_7890_monitor.log" | sed 's/^/    /'
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Web UI: http://127.0.0.1:5000"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
