#!/bin/bash

# Script khởi động hệ thống proxy

set -e

echo "=== Khởi động hệ thống Proxy ==="

# Kiểm tra các file cấu hình
if [ ! -f "haproxy1.cfg" ] || [ ! -f "haproxy2.cfg" ]; then
    echo "❌ Không tìm thấy file cấu hình HAProxy"
    exit 1
fi

# Tạo thư mục logs nếu chưa có
mkdir -p logs

# Kiểm tra Cloudflare WARP
echo ""
echo "🔍 Kiểm tra Cloudflare WARP..."
if command -v warp-cli &> /dev/null; then
    WARP_STATUS=$(warp-cli status 2>&1 || echo "disconnected")
    if echo "$WARP_STATUS" | grep -q "Connected"; then
        echo "✓ Cloudflare WARP đang chạy"
    else
        echo "⚠️  Cloudflare WARP chưa kết nối. Đang kết nối..."
        warp-cli connect || echo "⚠️  Không thể kết nối WARP tự động"
    fi
else
    echo "⚠️  Cloudflare WARP CLI chưa được cài đặt"
fi

# Kiểm tra WireGuard
echo ""
echo "🔍 Kiểm tra WireGuard..."
WG1_RUNNING=false
WG2_RUNNING=false

if [ -f "wireguard/wg1.conf" ]; then
    echo "✓ Tìm thấy cấu hình WireGuard 1"
    WG1_RUNNING=true
fi

if [ -f "wireguard/wg2.conf" ]; then
    echo "✓ Tìm thấy cấu hình WireGuard 2"
    WG2_RUNNING=true
fi

if [ "$WG1_RUNNING" = false ] && [ "$WG2_RUNNING" = false ]; then
    echo "⚠️  Không tìm thấy cấu hình WireGuard nào"
    echo "Vui lòng đặt file cấu hình vào wireguard/wg1.conf và wireguard/wg2.conf"
fi

# Dừng các tiến trình cũ nếu có
echo ""
echo "🛑 Dừng các tiến trình cũ..."
pkill -f "haproxy.*haproxy1.cfg" || true
pkill -f "haproxy.*haproxy2.cfg" || true
sleep 1

# Khởi động HAProxy 1
echo ""
echo "🚀 Khởi động HAProxy 1 (cổng 7891)..."
haproxy -f haproxy1.cfg -D
if [ $? -eq 0 ]; then
    echo "✓ HAProxy 1 đã khởi động thành công"
else
    echo "❌ Lỗi khởi động HAProxy 1"
    exit 1
fi

# Khởi động HAProxy 2
echo ""
echo "🚀 Khởi động HAProxy 2 (cổng 7892)..."
haproxy -f haproxy2.cfg -D
if [ $? -eq 0 ]; then
    echo "✓ HAProxy 2 đã khởi động thành công"
else
    echo "❌ Lỗi khởi động HAProxy 2"
    exit 1
fi

echo ""
echo "=== Hệ thống đã khởi động ==="
echo ""
echo "📊 Thông tin proxy:"
echo "  • HAProxy 1: socks5://127.0.0.1:7891"
echo "  • HAProxy 2: socks5://127.0.0.1:7892"
echo ""
echo "🔄 Cấu trúc fallback:"
echo "  • HAProxy 1: WireGuard 18181 → Cloudflare WARP 8111"
echo "  • HAProxy 2: WireGuard 18182 → Cloudflare WARP 8111"
echo ""
echo "📝 Lệnh hữu ích:"
echo "  • Kiểm tra trạng thái: ./status.sh"
echo "  • Dừng hệ thống: ./stop.sh"
echo "  • Xem logs: tail -f logs/*.log"

