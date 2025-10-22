#!/usr/bin/env bash
# start_gost_system.sh
# Khởi động hệ thống gost hoàn chỉnh

set -euo pipefail

echo "🚀 Starting Gost System"
echo "======================"

# Dừng các service cũ
echo "1️⃣ Stopping old services..."
./stop_all.sh

# Khởi động gost instances
echo ""
echo "2️⃣ Starting gost instances..."
./simple_gost.sh

# Khởi động HAProxy instances
echo ""
echo "3️⃣ Starting HAProxy instances..."
# Dynamic discovery: Start HAProxy services based on gost config files
for config_file in ./logs/gost_*.config; do
    if [ -f "$config_file" ]; then
        gost_port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
        haproxy_port=$((gost_port - 10000))
        stats_port=$((haproxy_port + 200))
        
        echo "🚀 Starting HAProxy $haproxy_port for gost $gost_port..."
        ./setup_haproxy.sh --sock-port $haproxy_port --stats-port $stats_port --gost-ports $gost_port --daemon
    fi
done

# Khởi động Web UI
echo ""
echo "4️⃣ Starting Web UI..."
./start_webui_daemon.sh

# Kiểm tra trạng thái
echo ""
echo "5️⃣ Checking system status..."
sleep 3
./status_all.sh

echo ""
echo "✅ Gost System Started Successfully!"
echo ""
echo "📊 Proxy Endpoints:"
for config_file in ./logs/gost_*.config; do
    if [ -f "$config_file" ]; then
        gost_port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
        haproxy_port=$((gost_port - 10000))
        echo "   • SOCKS5 Proxy $haproxy_port: socks5://127.0.0.1:$haproxy_port"
    fi
done
echo ""
echo "📈 HAProxy Stats:"
for config_file in ./logs/gost_*.config; do
    if [ -f "$config_file" ]; then
        gost_port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
        haproxy_port=$((gost_port - 10000))
        stats_port=$((haproxy_port + 200))
        echo "   • HAProxy $haproxy_port: http://127.0.0.1:$stats_port/haproxy?stats"
    fi
done
echo "   • Auth: admin:admin123"
echo ""
echo "🌐 Web UI:"
echo "   • URL: http://127.0.0.1:5000"
echo ""
echo "🧪 Test Commands:"
for config_file in ./logs/gost_*.config; do
    if [ -f "$config_file" ]; then
        gost_port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
        haproxy_port=$((gost_port - 10000))
        echo "   • Test proxy $haproxy_port: curl -x socks5h://127.0.0.1:$haproxy_port https://api.ipify.org"
    fi
done
