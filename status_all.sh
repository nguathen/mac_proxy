#!/usr/bin/env bash
# status_all.sh
# Kiểm tra trạng thái tất cả services

set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 HAProxy Multi-Instance System Status"
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

# Kiểm tra HAProxy processes
echo ""
echo "🔧 HAProxy Instances:"
for pid_file in logs/haproxy_*.pid; do
    if [ -f "$pid_file" ]; then
        port=$(basename "$pid_file" .pid | sed 's/haproxy_//')
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "  ✅ Instance on port $port: Running (PID $pid)"
        else
            echo "  ❌ Instance on port $port: Dead (stale PID file)"
        fi
    fi
done

# Kiểm tra health monitors
echo ""
echo "🩺 Health Monitors:"
for pid_file in logs/health_*.pid; do
    if [ -f "$pid_file" ]; then
        port=$(basename "$pid_file" .pid | sed 's/health_//')
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "  ✅ Monitor for port $port: Running (PID $pid)"
        else
            echo "  ❌ Monitor for port $port: Dead (stale PID file)"
        fi
    fi
done

# Kiểm tra listening ports
echo ""
echo "🔌 Listening Ports:"
# Kiểm tra HAProxy ports và stats ports
for pid_file in logs/haproxy_*.pid; do
    if [ -f "$pid_file" ]; then
        port=$(basename "$pid_file" .pid | sed 's/haproxy_//')
        stats_port=$((port + 200))
        
        # Kiểm tra HAProxy port
        if lsof -i :$port > /dev/null 2>&1 || nc -z 127.0.0.1 $port 2>/dev/null; then
            echo "  ✅ HAProxy port $port: Listening"
        else
            echo "  ❌ HAProxy port $port: Not listening"
        fi
        
        # Kiểm tra stats port
        if lsof -i :$stats_port > /dev/null 2>&1 || nc -z 127.0.0.1 $stats_port 2>/dev/null; then
            echo "  ✅ Stats port $stats_port: Listening"
        else
            echo "  ❌ Stats port $stats_port: Not listening"
        fi
    fi
done

# Kiểm tra gost backends
echo ""
echo "🔐 Gost Backends:"
for port in 18181 18182 18183 18184 18185 18186 18187; do
    if nc -z 127.0.0.1 $port 2>/dev/null; then
        # Test với curl
        ip=$(curl -s --max-time 5 -x socks5h://127.0.0.1:${port} https://api.ipify.org 2>/dev/null || echo "N/A")
        if [ "$ip" != "N/A" ]; then
            echo "  ✅ Gost port $port: Online (IP: $ip)"
        else
            echo "  ⚠️  Gost port $port: Port open but not responding"
        fi
    else
        echo "  ❌ Gost port $port: Offline"
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
for pid_file in logs/haproxy_*.pid; do
    if [ -f "$pid_file" ]; then
        port=$(basename "$pid_file" .pid | sed 's/haproxy_//')
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
    fi
done

# Recent logs
echo ""
echo "📝 Recent Health Monitor Logs:"
for log_file in logs/haproxy_health_*.log; do
    if [ -f "$log_file" ]; then
        port=$(basename "$log_file" .log | sed 's/haproxy_health_//')
        echo ""
        echo "  Instance $port (last 3 lines):"
        tail -n 3 "$log_file" | sed 's/^/    /'
    fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📈 Stats URLs:"
for pid_file in logs/haproxy_*.pid; do
    if [ -f "$pid_file" ]; then
        port=$(basename "$pid_file" .pid | sed 's/haproxy_//')
        stats_port=$((port + 200))
        echo "   • Instance $port: http://127.0.0.1:$stats_port/haproxy?stats"
    fi
done
echo "   • Auth: admin:admin123"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

