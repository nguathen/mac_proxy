#!/usr/bin/env bash
# install_autostart_all.sh
# Cài đặt auto start cho hệ thống proxy trên Linux

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Cài đặt Auto Start cho Mac Proxy System"
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

# Cài đặt systemd service chính
echo "🚀 Cài đặt systemd service chính..."
if [ -f "$SCRIPT_DIR/install_systemd_main.sh" ]; then
    chmod +x "$SCRIPT_DIR/install_systemd_main.sh"
    "$SCRIPT_DIR/install_systemd_main.sh"
else
    echo "❌ install_systemd_main.sh not found"
    exit 1
fi

# Cài đặt Gost Monitor systemd service
echo ""
echo "🛡️  Cài đặt Gost Monitor systemd service..."
if [ -f "$SCRIPT_DIR/install_gostmonitor_systemd.sh" ]; then
    chmod +x "$SCRIPT_DIR/install_gostmonitor_systemd.sh"
    "$SCRIPT_DIR/install_gostmonitor_systemd.sh" || echo "⚠️  Gost Monitor có thể đã được cài đặt"
fi

# Cài đặt Gost 7890 Monitor systemd service
echo ""
echo "🛡️  Cài đặt Gost 7890 Monitor systemd service..."
if [ -f "$SCRIPT_DIR/install_gost7890monitor_systemd.sh" ]; then
    chmod +x "$SCRIPT_DIR/install_gost7890monitor_systemd.sh"
    "$SCRIPT_DIR/install_gost7890monitor_systemd.sh" || echo "⚠️  Gost 7890 Monitor có thể đã được cài đặt"
fi

# Cài đặt Auto Credential Updater systemd service
echo ""
echo "🔄 Cài đặt Auto Credential Updater systemd service..."
if [ -f "$SCRIPT_DIR/install_auto_updater_systemd.sh" ]; then
    chmod +x "$SCRIPT_DIR/install_auto_updater_systemd.sh"
    "$SCRIPT_DIR/install_auto_updater_systemd.sh" || echo "⚠️  Auto Credential Updater có thể đã được cài đặt"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Cài đặt auto start hoàn tất!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Hệ thống sẽ tự động khởi động khi system boot (sau khi network sẵn sàng)"
echo ""
echo "💡 Để gỡ cài đặt: sudo ./uninstall_autostart_all.sh"
echo ""
