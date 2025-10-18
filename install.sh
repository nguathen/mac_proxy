#!/bin/bash

# Script cài đặt hệ thống proxy trên macOS
# Yêu cầu: Homebrew đã được cài đặt

set -e

echo "=== Cài đặt hệ thống Proxy trên macOS ==="

# Kiểm tra Homebrew
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew chưa được cài đặt. Vui lòng cài đặt Homebrew trước:"
    echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 1
fi

echo "✓ Homebrew đã được cài đặt"

# Cài đặt HAProxy
echo ""
echo "📦 Cài đặt HAProxy..."
if ! command -v haproxy &> /dev/null; then
    brew install haproxy
    echo "✓ HAProxy đã được cài đặt"
else
    echo "✓ HAProxy đã tồn tại"
fi

# Cài đặt WireGuard
echo ""
echo "📦 Cài đặt WireGuard..."
if ! command -v wg &> /dev/null; then
    brew install wireguard-tools
    echo "✓ WireGuard đã được cài đặt"
else
    echo "✓ WireGuard đã tồn tại"
fi

# Cài đặt Cloudflare WARP
echo ""
echo "📦 Kiểm tra Cloudflare WARP..."
if ! command -v warp-cli &> /dev/null; then
    echo "⚠️  Cloudflare WARP chưa được cài đặt"
    echo "Vui lòng tải và cài đặt từ: https://1.1.1.1/"
    echo "Sau khi cài đặt, chạy: warp-cli register && warp-cli connect"
else
    echo "✓ Cloudflare WARP đã tồn tại"
fi

# Tạo thư mục logs
echo ""
echo "📁 Tạo thư mục logs..."
mkdir -p logs
echo "✓ Thư mục logs đã được tạo"

# Tạo thư mục cho WireGuard configs
echo ""
echo "📁 Tạo thư mục WireGuard configs..."
mkdir -p wireguard
echo "✓ Thư mục wireguard đã được tạo"

echo ""
echo "=== Cài đặt hoàn tất ==="
echo ""
echo "📝 Các bước tiếp theo:"
echo "1. Cấu hình WireGuard: Đặt file cấu hình vào thư mục wireguard/"
echo "2. Cấu hình Cloudflare WARP proxy trên cổng 8111"
echo "3. Chạy: ./start.sh để khởi động hệ thống"

