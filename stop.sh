#!/bin/bash

# Script dừng hệ thống proxy

echo "=== Dừng hệ thống Proxy ==="

echo ""
echo "🛑 Dừng HAProxy..."
pkill -f "haproxy.*haproxy1.cfg" || true
pkill -f "haproxy.*haproxy2.cfg" || true

sleep 1

# Kiểm tra xem còn tiến trình nào không
if pgrep -f "haproxy.*haproxy[12].cfg" > /dev/null; then
    echo "⚠️  Một số tiến trình HAProxy vẫn đang chạy"
    echo "Sử dụng: pkill -9 -f haproxy để buộc dừng"
else
    echo "✓ Tất cả tiến trình HAProxy đã dừng"
fi

echo ""
echo "=== Hệ thống đã dừng ==="

