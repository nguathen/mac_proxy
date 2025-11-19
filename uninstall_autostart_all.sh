#!/usr/bin/env bash
# uninstall_autostart_all.sh
# Gỡ cài đặt auto start cho hệ thống proxy trên Linux

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗑️  Gỡ cài đặt Auto Start cho Mac Proxy System"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Kiểm tra OS
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "❌ Script này chỉ hỗ trợ Linux"
    echo "   Detected OS: $OSTYPE"
    exit 1
fi

# Kiểm tra quyền root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Script này cần quyền root. Vui lòng chạy với sudo."
    exit 1
fi

# Stop và disable systemd service chính
echo "🛑 Dừng và disable systemd service chính..."
if systemctl is-active --quiet mac-proxy.service 2>/dev/null; then
    systemctl stop mac-proxy.service || true
fi
if systemctl is-enabled --quiet mac-proxy.service 2>/dev/null; then
    systemctl disable mac-proxy.service || true
fi

# Xóa service file
if [ -f "/etc/systemd/system/mac-proxy.service" ]; then
    rm -f /etc/systemd/system/mac-proxy.service
    echo "✅ Đã xóa mac-proxy.service"
fi

# Gỡ cài đặt các monitor services
echo ""
echo "🛡️  Gỡ cài đặt Gost Monitor services..."

if systemctl is-active --quiet gost-monitor.service 2>/dev/null; then
    systemctl stop gost-monitor.service || true
fi
if systemctl is-enabled --quiet gost-monitor.service 2>/dev/null; then
    systemctl disable gost-monitor.service || true
fi
if [ -f "/etc/systemd/system/gost-monitor.service" ]; then
    rm -f /etc/systemd/system/gost-monitor.service
    echo "✅ Đã xóa gost-monitor.service"
fi

if systemctl is-active --quiet gost-7890-monitor.service 2>/dev/null; then
    systemctl stop gost-7890-monitor.service || true
fi
if systemctl is-enabled --quiet gost-7890-monitor.service 2>/dev/null; then
    systemctl disable gost-7890-monitor.service || true
fi
if [ -f "/etc/systemd/system/gost-7890-monitor.service" ]; then
    rm -f /etc/systemd/system/gost-7890-monitor.service
    echo "✅ Đã xóa gost-7890-monitor.service"
fi

# Gỡ cài đặt Auto Credential Updater
echo ""
echo "🔄 Gỡ cài đặt Auto Credential Updater..."
if systemctl is-active --quiet auto-credential-updater.service 2>/dev/null; then
    systemctl stop auto-credential-updater.service || true
fi
if systemctl is-enabled --quiet auto-credential-updater.service 2>/dev/null; then
    systemctl disable auto-credential-updater.service || true
fi
if [ -f "/etc/systemd/system/auto-credential-updater.service" ]; then
    rm -f /etc/systemd/system/auto-credential-updater.service
    echo "✅ Đã xóa auto-credential-updater.service"
fi

# Reload systemd
echo ""
echo "🔄 Reload systemd daemon..."
systemctl daemon-reload

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Gỡ cài đặt auto start hoàn tất!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
