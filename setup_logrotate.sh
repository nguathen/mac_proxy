#!/usr/bin/env bash
# setup_logrotate.sh
# Setup logrotate cho Gost services

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOGROTATE_CONF="gost_logrotate.conf"
LOGROTATE_DEST="/etc/logrotate.d/gost"

# Kiểm tra quyền root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root (use sudo)"
    exit 1
fi

# Kiểm tra logrotate có tồn tại không
if ! command -v logrotate &> /dev/null; then
    echo "❌ logrotate is not installed"
    echo "   Install with: apt-get install logrotate (Ubuntu/Debian)"
    exit 1
fi

# Kiểm tra config file có tồn tại không
if [ ! -f "$SCRIPT_DIR/$LOGROTATE_CONF" ]; then
    echo "❌ Logrotate config file not found: $SCRIPT_DIR/$LOGROTATE_CONF"
    exit 1
fi

# Cập nhật đường dẫn trong config file
echo "📝 Updating paths in logrotate config..."
sed -i "s|/project_proxy/mac_proxy|$SCRIPT_DIR|g" "$SCRIPT_DIR/$LOGROTATE_CONF"

# Copy config vào /etc/logrotate.d/
echo "📋 Installing logrotate config..."
cp "$SCRIPT_DIR/$LOGROTATE_CONF" "$LOGROTATE_DEST"

# Set permissions
chmod 644 "$LOGROTATE_DEST"
chown root:root "$LOGROTATE_DEST"

# Test logrotate config
echo "🧪 Testing logrotate config..."
if logrotate -d "$LOGROTATE_DEST" > /dev/null 2>&1; then
    echo "✅ Logrotate config is valid"
else
    echo "⚠️  Warning: Logrotate config test failed, but continuing..."
fi

echo ""
echo "✅ Logrotate setup complete!"
echo ""
echo "Logrotate sẽ tự động rotate logs:"
echo "  - Daily rotation"
echo "  - Max size: 50MB per file"
echo "  - Keep: 7 rotated files (5 for port 7890)"
echo "  - Auto compress old logs"
echo ""
echo "Test manually với:"
echo "  sudo logrotate -d $LOGROTATE_DEST  # Dry run"
echo "  sudo logrotate -f $LOGROTATE_DEST  # Force rotate now"
echo ""
echo "Logs location: $SCRIPT_DIR/logs/"

