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
./setup_haproxy.sh --sock-port 7891 --stats-port 8091 --gost-ports 18181 --daemon
./setup_haproxy.sh --sock-port 7892 --stats-port 8092 --gost-ports 18182 --daemon

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
echo "   • SOCKS5 Proxy 1: socks5://127.0.0.1:7891"
echo "   • SOCKS5 Proxy 2: socks5://127.0.0.1:7892"
echo ""
echo "📈 HAProxy Stats:"
echo "   • Instance 1: http://127.0.0.1:8091/haproxy?stats"
echo "   • Instance 2: http://127.0.0.1:8092/haproxy?stats"
echo "   • Auth: admin:admin123"
echo ""
echo "🌐 Web UI:"
echo "   • URL: http://127.0.0.1:5000"
echo ""
echo "🧪 Test Commands:"
echo "   • Test proxy 1: curl -x socks5h://127.0.0.1:7891 https://api.ipify.org"
echo "   • Test proxy 2: curl -x socks5h://127.0.0.1:7892 https://api.ipify.org"
