#!/usr/bin/env bash
# build_app.sh
# Script để build MacProxy.app

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔨 Building MacProxy.app"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Tạo cấu trúc thư mục .app
APP_DIR="$SCRIPT_DIR/MacProxy.app"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# Copy launcher script
if [ -f "$SCRIPT_DIR/MacProxy.app/Contents/MacOS/MacProxy" ]; then
    echo "✅ Launcher script đã tồn tại"
else
    echo "❌ Launcher script không tìm thấy"
    exit 1
fi

# Đảm bảo quyền thực thi
chmod +x "$APP_DIR/Contents/MacOS/MacProxy"
chmod +x "$SCRIPT_DIR/launch_app.sh"

# Kiểm tra Info.plist
if [ -f "$APP_DIR/Contents/Info.plist" ]; then
    echo "✅ Info.plist đã tồn tại"
else
    echo "❌ Info.plist không tìm thấy"
    exit 1
fi

echo ""
echo "✅ MacProxy.app đã được build thành công!"
echo ""
echo "📱 Cách sử dụng:"
echo "   1. Double-click vào MacProxy.app để khởi động"
echo "   2. App sẽ tự động:"
echo "      • Khởi động Web UI (http://127.0.0.1:5000)"
echo "      • Khởi động WARP Monitor"
echo "      • Mở trình duyệt tự động"
echo ""
echo "📂 Vị trí: $APP_DIR"
echo ""

