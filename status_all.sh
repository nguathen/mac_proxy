#!/usr/bin/env bash
# status_all.sh
# Kiểm tra trạng thái tất cả services

set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 HAProxy Multi-Instance System Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Kiểm tra HAProxy processes
echo ""
echo "🔧 HAProxy Instances:"
for port in 7891 7892; do
    if [ -f "logs/haproxy_${port}.pid" ]; then
        pid=$(cat "logs/haproxy_${port}.pid")
        if kill -0 "$pid" 2>/dev/null; then
            echo "  ✅ Instance on port $port: Running (PID $pid)"
        else
            echo "  ❌ Instance on port $port: Dead (stale PID file)"
        fi
    else
        echo "  ❌ Instance on port $port: Not running"
    fi
done

# Kiểm tra health monitors
echo ""
echo "🩺 Health Monitors:"
for port in 7891 7892; do
    if [ -f "logs/health_${port}.pid" ]; then
        pid=$(cat "logs/health_${port}.pid")
        if kill -0 "$pid" 2>/dev/null; then
            echo "  ✅ Monitor for port $port: Running (PID $pid)"
        else
            echo "  ❌ Monitor for port $port: Dead (stale PID file)"
        fi
    else
        echo "  ❌ Monitor for port $port: Not running"
    fi
done

# Kiểm tra listening ports
echo ""
echo "🔌 Listening Ports:"
for port in 7891 7892 8091 8092; do
    if lsof -i :$port > /dev/null 2>&1 || nc -z 127.0.0.1 $port 2>/dev/null; then
        echo "  ✅ Port $port: Listening"
    else
        echo "  ❌ Port $port: Not listening"
    fi
done

# Kiểm tra wiresock backends
echo ""
echo "🔐 Wiresock Backends:"
for port in 18181 18182; do
    if nc -z 127.0.0.1 $port 2>/dev/null; then
        # Test với curl
        ip=$(curl -s --max-time 5 -x socks5h://127.0.0.1:${port} https://api.ipify.org 2>/dev/null || echo "N/A")
        if [ "$ip" != "N/A" ]; then
            echo "  ✅ Wiresock port $port: Online (IP: $ip)"
        else
            echo "  ⚠️  Wiresock port $port: Port open but not responding"
        fi
    else
        echo "  ❌ Wiresock port $port: Offline"
    fi
done


# Kiểm tra Cloudflare WARP
echo ""
echo "☁️  Cloudflare WARP (Fallback):"
if nc -z 127.0.0.1 8111 2>/dev/null; then
    ip=$(curl -s --max-time 5 -x socks5h://127.0.0.1:8111 https://api.ipify.org 2>/dev/null || echo "N/A")
    if [ "$ip" != "N/A" ]; then
        echo "  ✅ WARP proxy (port 8111): Online (IP: $ip)"
    else
        echo "  ⚠️  WARP proxy (port 8111): Port open but not responding"
    fi
else
    echo "  ❌ WARP proxy (port 8111): Offline"
fi

# Test HAProxy endpoints
echo ""
echo "🧪 HAProxy Endpoint Tests:"
for port in 7891 7892; do
    if nc -z 127.0.0.1 $port 2>/dev/null; then
        ip=$(curl -s --max-time 8 -x socks5h://127.0.0.1:${port} https://api.ipify.org 2>/dev/null || echo "N/A")
        if [ "$ip" != "N/A" ]; then
            echo "  ✅ HAProxy port $port: Working (IP: $ip)"
        else
            echo "  ⚠️  HAProxy port $port: Port open but proxy not working"
        fi
    else
        echo "  ❌ HAProxy port $port: Not accessible"
    fi
done

# Recent logs
echo ""
echo "📝 Recent Health Monitor Logs:"
for port in 7891 7892; do
    if [ -f "logs/haproxy_health_${port}.log" ]; then
        echo ""
        echo "  Instance $port (last 3 lines):"
        tail -n 3 "logs/haproxy_health_${port}.log" | sed 's/^/    /'
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📈 Stats URLs:"
echo "   • Instance 1: http://127.0.0.1:8091/haproxy?stats"
echo "   • Instance 2: http://127.0.0.1:8092/haproxy?stats"
echo "   • Auth: admin:admin123"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

