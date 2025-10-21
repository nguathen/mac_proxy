#!/usr/bin/env bash
# demo_restart.sh
# Demo việc khôi phục cấu hình khi khởi động lại

set -euo pipefail

echo "🔄 Demo: Restart with Configuration Recovery"
echo "============================================="

# Bước 1: Cấu hình một số instances
echo ""
echo "1️⃣ Setting up configurations..."
./manage_gost.sh config 1 protonvpn "node-uk-29.protonvpn.net"
./manage_gost.sh config 2 nordvpn "us"
./manage_gost.sh config 3 protonvpn "node-de-15.protonvpn.net"

# Bước 2: Khởi động gost
echo ""
echo "2️⃣ Starting gost instances..."
./manage_gost.sh start

# Bước 3: Hiển thị cấu hình hiện tại
echo ""
echo "3️⃣ Current configurations:"
./manage_gost.sh show-config

# Bước 4: Dừng tất cả
echo ""
echo "4️⃣ Stopping all instances..."
./manage_gost.sh stop

# Bước 5: Khởi động lại (sẽ khôi phục cấu hình)
echo ""
echo "5️⃣ Restarting (should recover configurations)..."
./manage_gost.sh start

# Bước 6: Kiểm tra trạng thái
echo ""
echo "6️⃣ Final status:"
./manage_gost.sh status

echo ""
echo "✅ Demo completed!"
echo "   - Configurations were saved and restored"
echo "   - ProtonVPN credentials were updated before restart"
