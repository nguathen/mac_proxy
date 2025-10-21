#!/usr/bin/env bash
# test_gost_config.sh
# Test script để demo hệ thống cấu hình gost

set -euo pipefail

echo "🧪 Testing Gost Configuration System"
echo "=================================="

# Test 1: Cấu hình instance 1 với ProtonVPN
echo ""
echo "1️⃣ Configuring instance 1 with ProtonVPN..."
./manage_gost.sh config 1 protonvpn "node-uk-29.protonvpn.net"

# Test 2: Cấu hình instance 2 với NordVPN
echo ""
echo "2️⃣ Configuring instance 2 with NordVPN..."
./manage_gost.sh config 2 nordvpn "us"

# Test 3: Hiển thị tất cả cấu hình
echo ""
echo "3️⃣ Showing all configurations..."
./manage_gost.sh show-config

# Test 4: Hiển thị cấu hình instance 1
echo ""
echo "4️⃣ Showing configuration for instance 1..."
./manage_gost.sh show-config 1

# Test 5: Khởi động gost instances
echo ""
echo "5️⃣ Starting gost instances..."
./manage_gost.sh start

# Test 6: Kiểm tra trạng thái
echo ""
echo "6️⃣ Checking status..."
./manage_gost.sh status

echo ""
echo "✅ Test completed!"
echo ""
echo "📝 Config files created:"
ls -la logs/gost*.config 2>/dev/null || echo "No config files found"
