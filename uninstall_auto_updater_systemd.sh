#!/usr/bin/env bash
# uninstall_auto_updater_systemd.sh
# Gỡ cài đặt systemd service cho Auto Credential Updater

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SERVICE_NAME="auto-credential-updater.service"
SYSTEMD_DIR="/etc/systemd/system"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗑️  Gỡ cài đặt Auto Credential Updater Systemd Service"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Kiểm tra quyền root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Script này cần quyền root. Vui lòng chạy với sudo."
    exit 1
fi

# Stop service
if systemctl is-active --quiet auto-credential-updater.service 2>/dev/null; then
    echo "🛑 Dừng service..."
    systemctl stop auto-credential-updater.service || true
fi

# Disable service
if systemctl is-enabled --quiet auto-credential-updater.service 2>/dev/null; then
    echo "🔄 Disable service..."
    systemctl disable auto-credential-updater.service || true
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
echo "✅ Auto Credential Updater systemd service đã được gỡ cài đặt"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

