#!/usr/bin/env bash
# install_linux.sh
# Script tự động cài đặt hệ thống proxy trên Linux VPS
# Sử dụng: curl -fsSL https://raw.githubusercontent.com/nguathen/mac_proxy/main/install_linux.sh | bash
# Hoặc: wget -qO- https://raw.githubusercontent.com/nguathen/mac_proxy/main/install_linux.sh | bash

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
    else
        log_error "Cannot detect OS. Please install manually."
        exit 1
    fi
    
    log_info "Detected OS: $OS $OS_VERSION"
}

# Install dependencies based on OS
install_dependencies() {
    log_info "Installing system dependencies..."
    
    if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
        sudo apt-get update -qq
        sudo apt-get install -y \
            curl \
            wget \
            git \
            python3 \
            python3-pip \
            jq \
            netcat-openbsd \
            haproxy \
            build-essential \
            ca-certificates
        
    elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ] || [ "$OS" = "fedora" ]; then
        if [ "$OS" = "fedora" ]; then
            sudo dnf install -y \
                curl \
                wget \
                git \
                python3 \
                python3-pip \
                jq \
                nc \
                haproxy \
                gcc \
                make \
                ca-certificates
        else
            sudo yum install -y epel-release
            sudo yum install -y \
                curl \
                wget \
                git \
                python3 \
                python3-pip \
                jq \
                nc \
                haproxy \
                gcc \
                make \
                ca-certificates
        fi
    else
        log_error "Unsupported OS: $OS"
        exit 1
    fi
    
    log_success "System dependencies installed"
}

# Install Gost binary
install_gost() {
    log_info "Installing Gost..."
    
    if command -v gost &> /dev/null; then
        log_warning "Gost already installed: $(command -v gost)"
        return
    fi
    
    # Detect architecture
    ARCH=$(uname -m)
    case $ARCH in
        x86_64)
            GOST_ARCH="amd64"
            ;;
        aarch64|arm64)
            GOST_ARCH="arm64"
            ;;
        *)
            log_error "Unsupported architecture: $ARCH"
            exit 1
            ;;
    esac
    
    # Get latest version
    GOST_VERSION=$(curl -s --connect-timeout 5 --max-time 10 https://api.github.com/repos/ginuerzh/gost/releases/latest 2>/dev/null | jq -r '.tag_name' 2>/dev/null | sed 's/v//' || echo "")
    
    if [ -z "$GOST_VERSION" ] || [ "$GOST_VERSION" = "null" ] || [ "$GOST_VERSION" = "" ]; then
        GOST_VERSION="3.0.0-rc8"  # Fallback version
        log_warning "Using fallback Gost version: $GOST_VERSION"
    fi
    
    log_info "Downloading Gost v${GOST_VERSION} (${GOST_ARCH})..."
    
    GOST_URL="https://github.com/ginuerzh/gost/releases/download/v${GOST_VERSION}/gost-linux-${GOST_ARCH}-${GOST_VERSION}.gz"
    
    # Download and install
    cd /tmp
    if command -v wget &> /dev/null; then
        wget -q --timeout=10 "$GOST_URL" -O gost.gz || curl -fsSL --connect-timeout 10 --max-time 30 "$GOST_URL" -o gost.gz
    else
        curl -fsSL --connect-timeout 10 --max-time 30 "$GOST_URL" -o gost.gz
    fi
    
    if [ ! -f gost.gz ]; then
        log_error "Failed to download Gost from $GOST_URL"
        log_error "Please check your internet connection and try again"
        exit 1
    fi
    
    gunzip -f gost.gz
    chmod +x gost
    sudo mv gost /usr/local/bin/gost
    
    # Verify installation
    if gost -V &> /dev/null; then
        log_success "Gost installed: $(gost -V)"
    else
        log_success "Gost installed to /usr/local/bin/gost"
    fi
}

# Clone repository
clone_repo() {
    log_info "Cloning repository..."
    
    REPO_URL="https://github.com/nguathen/mac_proxy.git"
    INSTALL_DIR="$HOME/mac_proxy"
    
    if [ -d "$INSTALL_DIR" ]; then
        log_warning "Directory $INSTALL_DIR already exists"
        read -p "Do you want to remove it and reinstall? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$INSTALL_DIR"
        else
            log_info "Using existing installation at $INSTALL_DIR"
            cd "$INSTALL_DIR"
            git pull || log_warning "Failed to pull latest changes"
            return
        fi
    fi
    
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    
    log_success "Repository cloned to $INSTALL_DIR"
}

# Install Python dependencies
install_python_deps() {
    log_info "Installing Python dependencies..."
    
    if [ -f "webui/requirements.txt" ]; then
        pip3 install --user -r webui/requirements.txt
        log_success "Python dependencies installed"
    else
        log_warning "requirements.txt not found, skipping Python dependencies"
    fi
}

# Make scripts executable
make_executable() {
    log_info "Making scripts executable..."
    
    find . -name "*.sh" -type f -exec chmod +x {} \;
    
    log_success "Scripts are now executable"
}

# Create systemd service (optional)
create_systemd_service() {
    log_info "Creating systemd service..."
    
    SERVICE_FILE="/etc/systemd/system/mac-proxy.service"
    INSTALL_DIR="$HOME/mac_proxy"
    
    if [ -f "$SERVICE_FILE" ]; then
        log_warning "Systemd service already exists"
        return
    fi
    
    sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Mac Proxy System
After=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/launch_linux.sh start
ExecStop=$INSTALL_DIR/launch_linux.sh stop
User=$USER
Group=$USER

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    
    log_success "Systemd service created"
    log_info "To enable auto-start: sudo systemctl enable mac-proxy"
    log_info "To start service: sudo systemctl start mac-proxy"
}

# Create launch script for Linux (similar to MacProxy.app)
create_launch_script() {
    log_info "Creating Linux launch script..."
    
    cat > launch_linux.sh <<'LAUNCH_EOF'
#!/usr/bin/env bash
# launch_linux.sh
# Script launcher để chạy hệ thống proxy trên Linux (tương tự MacProxy.app)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="$SCRIPT_DIR/logs/app_launcher.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] $*" | tee -a "$LOG_FILE"
}

case "${1:-start}" in
    start)
        log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log "🚀 Starting Mac Proxy System"
        log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        # Khởi động HAProxy 7890
        log "🚀 Starting HAProxy 7890..."
        if [ -f "$SCRIPT_DIR/services/haproxy_7890/start_haproxy_7890.sh" ]; then
            cd "$SCRIPT_DIR/services/haproxy_7890"
            chmod +x start_haproxy_7890.sh
            ./start_haproxy_7890.sh >> "$SCRIPT_DIR/logs/haproxy_7890_launch.log" 2>&1 || true
            cd "$SCRIPT_DIR"
            log "✅ HAProxy 7890 started"
        else
            log "⚠️  HAProxy 7890 script not found"
        fi
        
        # Đợi một chút để HAProxy khởi động
        sleep 2
        
        # Khởi động WebUI
        log "🌐 Starting Web UI..."
        if [ -f "$SCRIPT_DIR/start_webui_daemon.sh" ]; then
            chmod +x "$SCRIPT_DIR/start_webui_daemon.sh"
            "$SCRIPT_DIR/start_webui_daemon.sh" >> "$LOG_FILE" 2>&1
            log "✅ Web UI started"
        else
            log "❌ Web UI script not found"
        fi
        
        # Đợi một chút để WebUI khởi động
        sleep 3
        
        # Khởi động Auto Credential Updater
        log "🔄 Starting Auto Credential Updater..."
        if [ -f "$SCRIPT_DIR/start_auto_updater.sh" ]; then
            chmod +x "$SCRIPT_DIR/start_auto_updater.sh"
            "$SCRIPT_DIR/start_auto_updater.sh" start >> "$LOG_FILE" 2>&1 || true
            log "✅ Auto Credential Updater started"
        else
            log "⚠️  Auto Credential Updater script not found"
        fi
        
        # Khởi động HAProxy monitor
        log "🛡️  Starting HAProxy Monitor..."
        if [ -f "$SCRIPT_DIR/services/haproxy_7890/haproxy_monitor.sh" ]; then
            cd "$SCRIPT_DIR/services/haproxy_7890"
            chmod +x haproxy_monitor.sh
            ./haproxy_monitor.sh start >> "$SCRIPT_DIR/logs/haproxy_monitor_launchd.log" 2>&1 || true
            cd "$SCRIPT_DIR"
            log "✅ HAProxy Monitor started"
        else
            log "⚠️  HAProxy Monitor script not found"
        fi
        
        # Khởi động WARP monitor
        log "🛡️  Starting WARP Monitor..."
        if [ -f "$SCRIPT_DIR/services/haproxy_7890/warp_monitor.sh" ]; then
            cd "$SCRIPT_DIR/services/haproxy_7890"
            chmod +x warp_monitor.sh
            ./warp_monitor.sh start >> "$SCRIPT_DIR/logs/warp_monitor_launchd.log" 2>&1 || true
            cd "$SCRIPT_DIR"
            log "✅ WARP Monitor started"
        else
            log "⚠️  WARP Monitor script not found"
        fi
        
        # Khởi động Gost services
        log "🔐 Starting Gost Services..."
        if [ -f "$SCRIPT_DIR/manage_gost.sh" ]; then
            chmod +x "$SCRIPT_DIR/manage_gost.sh"
            "$SCRIPT_DIR/manage_gost.sh" start >> "$LOG_FILE" 2>&1 || true
            log "✅ Gost Services started"
        else
            log "⚠️  Gost management script not found"
        fi
        
        # Đợi một chút để Gost khởi động
        sleep 2
        
        # Khởi động Gost Monitor
        log "🛡️  Starting Gost Monitor..."
        if [ -f "$SCRIPT_DIR/gost_monitor.sh" ]; then
            chmod +x "$SCRIPT_DIR/gost_monitor.sh"
            "$SCRIPT_DIR/gost_monitor.sh" start >> "$SCRIPT_DIR/logs/gost_monitor.log" 2>&1 || true
            log "✅ Gost Monitor started"
        else
            log "⚠️  Gost Monitor script not found"
        fi
        
        log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log "✅ App started successfully"
        log "📊 Web UI: http://127.0.0.1:5000"
        log "📊 Web UI (external): http://$(hostname -I | awk '{print $1}'):5000"
        log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ;;
    
    stop)
        log "🛑 Stopping Mac Proxy System..."
        
        # Stop Gost Monitor
        if [ -f "$SCRIPT_DIR/gost_monitor.sh" ]; then
            "$SCRIPT_DIR/gost_monitor.sh" stop || true
        fi
        
        # Stop Gost Services
        if [ -f "$SCRIPT_DIR/manage_gost.sh" ]; then
            "$SCRIPT_DIR/manage_gost.sh" stop || true
        fi
        
        # Stop WARP Monitor
        if [ -f "$SCRIPT_DIR/services/haproxy_7890/warp_monitor.sh" ]; then
            cd "$SCRIPT_DIR/services/haproxy_7890"
            ./warp_monitor.sh stop || true
            cd "$SCRIPT_DIR"
        fi
        
        # Stop HAProxy Monitor
        if [ -f "$SCRIPT_DIR/services/haproxy_7890/haproxy_monitor.sh" ]; then
            cd "$SCRIPT_DIR/services/haproxy_7890"
            ./haproxy_monitor.sh stop || true
            cd "$SCRIPT_DIR"
        fi
        
        # Stop Auto Credential Updater
        if [ -f "$SCRIPT_DIR/start_auto_updater.sh" ]; then
            "$SCRIPT_DIR/start_auto_updater.sh" stop || true
        fi
        
        # Stop WebUI
        if [ -f "$SCRIPT_DIR/start_webui_daemon.sh" ]; then
            PID_FILE="$SCRIPT_DIR/logs/webui.pid"
            if [ -f "$PID_FILE" ]; then
                PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
                if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
                    kill "$PID" 2>/dev/null || true
                fi
                rm -f "$PID_FILE"
            fi
        fi
        
        # Stop HAProxy 7890
        if [ -f "$SCRIPT_DIR/services/haproxy_7890/stop_haproxy_7890.sh" ]; then
            cd "$SCRIPT_DIR/services/haproxy_7890"
            ./stop_haproxy_7890.sh || true
            cd "$SCRIPT_DIR"
        fi
        
        log "✅ All services stopped"
        ;;
    
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    
    status)
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "📊 Mac Proxy System Status"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        # Check WebUI
        PID_FILE="$SCRIPT_DIR/logs/webui.pid"
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
            if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
                echo "✅ Web UI: Running (PID: $PID)"
            else
                echo "❌ Web UI: Not running"
            fi
        else
            echo "❌ Web UI: Not running"
        fi
        
        # Check Gost
        if [ -f "$SCRIPT_DIR/manage_gost.sh" ]; then
            "$SCRIPT_DIR/manage_gost.sh" status || true
        fi
        
        # Check HAProxy 7890
        PID_FILE="$SCRIPT_DIR/services/haproxy_7890/logs/haproxy_7890.pid"
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
            if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
                echo "✅ HAProxy 7890: Running (PID: $PID)"
            else
                echo "❌ HAProxy 7890: Not running"
            fi
        else
            echo "❌ HAProxy 7890: Not running"
        fi
        
        echo ""
        echo "🌐 Web UI: http://127.0.0.1:5000"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ;;
    
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
LAUNCH_EOF
    
    chmod +x launch_linux.sh
    log_success "Linux launch script created"
}

# Main installation
main() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🚀 Mac Proxy - Linux Installation Script"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Check if running as root
    if [ "$EUID" -eq 0 ]; then
        log_error "Please do not run this script as root. It will use sudo when needed."
        exit 1
    fi
    
    # Check sudo access
    if ! sudo -n true 2>/dev/null; then
        log_info "This script requires sudo access. You may be prompted for your password."
    fi
    
    detect_os
    install_dependencies
    install_gost
    clone_repo
    install_python_deps
    make_executable
    create_launch_script
    
    # Ask if user wants to create systemd service
    read -p "Do you want to create systemd service for auto-start? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        create_systemd_service
    fi
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ Installation completed successfully!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📁 Installation directory: $HOME/mac_proxy"
    echo ""
    echo "🚀 To start the system:"
    echo "   cd $HOME/mac_proxy"
    echo "   ./launch_linux.sh start"
    echo ""
    echo "🛑 To stop the system:"
    echo "   cd $HOME/mac_proxy"
    echo "   ./launch_linux.sh stop"
    echo ""
    echo "📊 To check status:"
    echo "   cd $HOME/mac_proxy"
    echo "   ./launch_linux.sh status"
    echo ""
    echo "🌐 Web UI will be available at:"
    echo "   http://127.0.0.1:5000"
    if command -v hostname &> /dev/null; then
        EXTERNAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "")
        if [ -n "$EXTERNAL_IP" ]; then
            echo "   http://${EXTERNAL_IP}:5000"
        fi
    fi
    echo ""
    echo "💡 Optional: Enable auto-start on boot"
    echo "   sudo systemctl enable mac-proxy"
    echo "   sudo systemctl start mac-proxy"
    echo ""
    
    # Ask if user wants to start now
    read -p "Do you want to start the system now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd "$HOME/mac_proxy"
        ./launch_linux.sh start
    fi
}

# Run main function
main "$@"

