#!/bin/bash

# Script kiểm tra trạng thái hệ thống proxy

echo "=== Trạng thái hệ thống Proxy ==="

# Kiểm tra HAProxy
echo ""
echo "📊 HAProxy:"
if pgrep -f "haproxy.*haproxy1.cfg" > /dev/null; then
    echo "  ✓ HAProxy 1 (cổng 7891): Đang chạy"
else
    echo "  ✗ HAProxy 1 (cổng 7891): Không chạy"
fi

if pgrep -f "haproxy.*haproxy2.cfg" > /dev/null; then
    echo "  ✓ HAProxy 2 (cổng 7892): Đang chạy"
else
    echo "  ✗ HAProxy 2 (cổng 7892): Không chạy"
fi

# Kiểm tra các cổng
echo ""
echo "🔌 Kiểm tra cổng:"
for port in 7891 7892 8111 18181 18182; do
    if lsof -i :$port > /dev/null 2>&1; then
        echo "  ✓ Cổng $port: Đang lắng nghe"
    else
        echo "  ✗ Cổng $port: Không hoạt động"
    fi
done

# Kiểm tra Cloudflare WARP
echo ""
echo "☁️  Cloudflare WARP:"
if command -v warp-cli &> /dev/null; then
    WARP_STATUS=$(warp-cli status 2>&1 || echo "Error")
    if echo "$WARP_STATUS" | grep -q "Connected"; then
        echo "  ✓ Đã kết nối"
    else
        echo "  ✗ Chưa kết nối"
    fi
else
    echo "  ⚠️  CLI chưa cài đặt"
fi

# Kiểm tra WireGuard
echo ""
echo "🔐 WireGuard:"
if command -v wg &> /dev/null; then
    WG_INTERFACES=$(sudo wg show interfaces 2>/dev/null || echo "")
    if [ -z "$WG_INTERFACES" ]; then
        echo "  ⚠️  Không có interface nào đang chạy"
    else
        echo "  ✓ Interfaces: $WG_INTERFACES"
    fi
else
    echo "  ⚠️  WireGuard chưa cài đặt"
fi

echo ""
echo "==========================="

