#!/usr/bin/env bash
# uninstall_haproxy7890_systemd.sh
# Gỡ cài đặt systemd service cho HAProxy 7890

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVICE_NAME="haproxy-7890.service"
SYSTEMD_DIR="/etc/systemd/system"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗑️  Gỡ cài đặt HAProxy 7890 Systemd Service"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Kiểm tra quyền root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Script này cần quyền root. Vui lòng chạy với sudo."
    exit 1
fi

# Stop service
if systemctl is-active --quiet haproxy-7890.service 2>/dev/null; then
    echo "🛑 Dừng service..."
    systemctl stop haproxy-7890.service || true
fi

# Disable service
if systemctl is-enabled --quiet haproxy-7890.service 2>/dev/null; then
    echo "🔄 Disable service..."
    systemctl disable haproxy-7890.service || true
fi

# Remove service file
if [ -f "$SYSTEMD_DIR/$SERVICE_NAME" ]; then
    echo "🗑️  Xóa service file..."
    rm -f "$SYSTEMD_DIR/$SERVICE_NAME"
fi

# Reload systemd
echo "🔄 Reload systemd daemon..."
systemctl daemon-reload

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ HAProxy 7890 systemd service đã được gỡ cài đặt"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

