#!/usr/bin/env bash
# update_code.sh
# Stop hệ thống, update code từ GitHub, và restart lại

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄 Updating Mac Proxy System"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Kiểm tra xem có phải git repository không
if [ ! -d ".git" ]; then
    echo "❌ Không phải git repository"
    echo "   Vui lòng clone từ GitHub trước:"
    echo "   git clone https://github.com/nguathen/mac_proxy.git"
    exit 1
fi

# Step 1: Stop hệ thống
echo "📌 Step 1: Stopping system..."
if [ -f "stop_all.sh" ]; then
    chmod +x stop_all.sh
    ./stop_all.sh
elif [ -f "launch_linux.sh" ]; then
    chmod +x launch_linux.sh
    ./launch_linux.sh stop
else
    echo "⚠️  Không tìm thấy script stop, thử stop thủ công..."
    # Stop các services thủ công
    pkill -f "gost.*socks5" 2>/dev/null || true
    pkill -f "python.*app.py" 2>/dev/null || true
    pkill -f "auto_credential_updater" 2>/dev/null || true
    pkill -f "warp_monitor" 2>/dev/null || true
    pkill -f "gost_monitor" 2>/dev/null || true
    sleep 2
fi

echo ""
echo "✅ System stopped"
echo ""

# Step 2: Backup config files (optional)
echo "📌 Step 2: Backing up config files..."
BACKUP_DIR="./backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
if [ -d "config" ]; then
    cp -r config "$BACKUP_DIR/" 2>/dev/null || true
    echo "   ✅ Config files backed up to $BACKUP_DIR"
fi
if [ -d "proton_data" ]; then
    cp -r proton_data "$BACKUP_DIR/" 2>/dev/null || true
    echo "   ✅ Proton data backed up"
fi
echo ""

# Step 3: Pull code mới từ GitHub
echo "📌 Step 3: Pulling latest code from GitHub..."
echo "   Repository: https://github.com/nguathen/mac_proxy.git"
echo ""

# Lưu branch hiện tại
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")

# Stash local changes nếu có
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    echo "⚠️  Có thay đổi local, đang stash..."
    git stash push -m "Auto stash before update $(date +%Y%m%d_%H%M%S)" || true
fi

# Pull code mới
if git pull origin "$CURRENT_BRANCH"; then
    echo "✅ Code updated successfully"
else
    echo "❌ Failed to pull code"
    echo "   Vui lòng kiểm tra kết nối mạng và thử lại"
    exit 1
fi

echo ""

# Step 4: Make scripts executable
echo "📌 Step 4: Making scripts executable..."
find . -name "*.sh" -type f -exec chmod +x {} \; 2>/dev/null || true
echo "✅ Scripts are executable"
echo ""

# Step 5: Update Python dependencies (optional)
echo "📌 Step 5: Updating Python dependencies..."
if [ -f "webui/requirements.txt" ]; then
    if command -v pip3 &> /dev/null; then
        pip3 install --user -r webui/requirements.txt --quiet || true
        echo "✅ Python dependencies updated"
    else
        echo "⚠️  pip3 not found, skipping Python dependencies"
    fi
else
    echo "⚠️  requirements.txt not found, skipping"
fi
echo ""

# Step 6: Restore config files nếu cần
if [ -d "$BACKUP_DIR/config" ]; then
    echo "📌 Step 6: Restoring config files..."
    # Chỉ restore nếu file không tồn tại hoặc user muốn
    read -p "   Restore config files từ backup? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp -r "$BACKUP_DIR/config"/* config/ 2>/dev/null || true
        echo "   ✅ Config files restored"
    else
        echo "   ⏭️  Skipping config restore"
    fi
    echo ""
fi

# Step 7: Restart hệ thống
echo "📌 Step 7: Restarting system..."
read -p "   Bạn có muốn restart hệ thống ngay bây giờ? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    if [ -f "start_all.sh" ]; then
        chmod +x start_all.sh
        ./start_all.sh
    elif [ -f "launch_linux.sh" ]; then
        chmod +x launch_linux.sh
        ./launch_linux.sh start
    else
        echo "⚠️  Không tìm thấy script start"
        echo "   Vui lòng start thủ công:"
        echo "   ./start_all.sh"
        echo "   hoặc"
        echo "   ./launch_linux.sh start"
    fi
else
    echo "⏭️  Skipping restart"
    echo "   Để start hệ thống sau:"
    echo "   ./start_all.sh"
    echo "   hoặc"
    echo "   ./launch_linux.sh start"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Update completed!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Backup location: $BACKUP_DIR"
echo "🌐 Web UI: http://127.0.0.1:5000"
echo ""

