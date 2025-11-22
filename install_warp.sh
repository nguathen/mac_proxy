#!/usr/bin/env bash
# install_warp.sh
# Script cài đặt và cấu hình Cloudflare WARP

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔐 Cloudflare WARP Installation & Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if WARP is already installed
if command -v warp-cli &> /dev/null; then
    log_warning "WARP CLI already installed: $(command -v warp-cli)"
    log_info "Checking WARP configuration..."
    
    WARP_STATUS=$(warp-cli status 2>/dev/null || echo "")
    if echo "$WARP_STATUS" | grep -qi "connected"; then
        PROXY_STATUS=$(warp-cli proxy status 2>/dev/null || echo "")
        if echo "$PROXY_STATUS" | grep -qi "enabled\|on\|active" && echo "$PROXY_STATUS" | grep -q "8111"; then
            log_success "WARP already configured and connected"
            exit 0
        fi
    fi
else
    log_info "Installing Cloudflare WARP CLI..."
    
    # Detect OS
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        OS_VERSION=$VERSION_ID
    else
        log_error "Cannot detect OS"
        exit 1
    fi
    
    log_info "Detected OS: $OS $OS_VERSION"
    
    # Detect architecture
    ARCH=$(uname -m)
    if [ "$ARCH" = "x86_64" ]; then
        WARP_ARCH="amd64"
    elif [ "$ARCH" = "aarch64" ]; then
        WARP_ARCH="arm64"
    else
        log_error "Unsupported architecture: $ARCH"
        exit 1
    fi
    
    log_info "Architecture: $ARCH ($WARP_ARCH)"
    
    if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
        log_info "Installing WARP from Cloudflare repository..."
        
        # Install GPG key
        log_info "Adding Cloudflare GPG key..."
        curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg 2>/dev/null || {
            log_warning "Failed to add GPG key, trying alternative method..."
            curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo apt-key add - 2>/dev/null || {
                log_error "Failed to add GPG key"
                exit 1
            }
        }
        
        # Detect codename
        if command -v lsb_release &> /dev/null; then
            CODENAME=$(lsb_release -cs)
        elif [ -f /etc/os-release ]; then
            CODENAME=$(grep VERSION_CODENAME /etc/os-release | cut -d= -f2)
            if [ -z "$CODENAME" ]; then
                CODENAME=$(grep VERSION_ID /etc/os-release | cut -d= -f2 | tr -d '"' | cut -d. -f1)
                case "$CODENAME" in
                    20) CODENAME="focal" ;;
                    22) CODENAME="jammy" ;;
                    24) CODENAME="noble" ;;
                    *) CODENAME="jammy" ;;
                esac
            fi
        else
            CODENAME="jammy"
        fi
        
        log_info "Detected codename: $CODENAME"
        
        # Add repository
        log_info "Adding Cloudflare repository..."
        echo "deb [arch=${WARP_ARCH} signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ ${CODENAME} main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list > /dev/null
        
        # Update and install
        log_info "Updating package list..."
        sudo apt-get update -qq
        
        log_info "Installing cloudflare-warp..."
        sudo apt-get install -y cloudflare-warp
        
        log_success "WARP CLI installed"
    else
        log_error "Unsupported OS: $OS"
        log_info "Please install WARP manually from: https://1.1.1.1/"
        exit 1
    fi
fi

# Verify installation
if ! command -v warp-cli &> /dev/null; then
    log_error "WARP CLI installation failed"
    exit 1
fi

# Configure WARP
log_info "Configuring Cloudflare WARP..."

# Wait for WARP daemon to be ready
log_info "Waiting for WARP daemon to be ready..."
WAIT_COUNT=0
MAX_WAIT=30
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if warp-cli status &>/dev/null; then
        break
    fi
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    log_warning "WARP daemon may not be ready. Continuing anyway..."
fi

# Register if needed
log_info "Checking WARP registration..."
ACCOUNT_STATUS=$(warp-cli account 2>&1 || echo "")
if echo "$ACCOUNT_STATUS" | grep -qi "missing\|not registered\|register\|No account"; then
    log_info "Registering WARP..."
    if warp-cli registration new 2>&1 | grep -qi "success\|ok\|registered"; then
        log_success "WARP registered"
    elif warp-cli register 2>&1 | grep -qi "success\|ok\|registered"; then
        log_success "WARP registered"
    else
        log_warning "WARP registration may have failed, but continuing..."
    fi
    sleep 2
else
    log_info "WARP already registered"
fi

# Set proxy mode
log_info "Setting WARP to proxy mode..."

# Check if proxy subcommand exists
if warp-cli proxy --help 2>/dev/null | grep -q "proxy"; then
    # Linux WARP CLI syntax
    PROXY_STATUS=$(warp-cli proxy status 2>/dev/null || echo "")
    if echo "$PROXY_STATUS" | grep -qi "enabled\|on\|active"; then
        log_info "WARP proxy already enabled"
    else
        log_info "Enabling WARP proxy mode..."
        warp-cli proxy enable 2>&1 | grep -v "Success" || true
        sleep 2
    fi
    
    # Set proxy port to 8111
    log_info "Setting WARP proxy port to 8111..."
    CURRENT_PORT=$(warp-cli proxy status 2>/dev/null | grep -i "port" | awk '{print $NF}' || echo "")
    
    if echo "$CURRENT_PORT" | grep -q "8111"; then
        log_info "WARP proxy port already set to 8111"
    else
        log_info "Running: warp-cli proxy port 8111"
        warp-cli proxy port 8111 2>&1 | grep -v "Success" || true
        sleep 2
        
        # Verify port was set
        VERIFY_PORT=$(warp-cli proxy status 2>/dev/null | grep -i "port" | awk '{print $NF}' || echo "")
        if echo "$VERIFY_PORT" | grep -q "8111"; then
            log_success "WARP proxy port set to 8111"
        else
            log_warning "Could not verify proxy port"
            log_info "You can verify with: warp-cli proxy status"
        fi
    fi
else
    # Fallback: Try macOS syntax
    log_warning "WARP proxy subcommand not available, trying alternative methods..."
    
    if warp-cli set-mode proxy 2>&1 | grep -qi "success\|ok"; then
        log_success "Set proxy mode using set-mode"
    else
        log_warning "Could not set proxy mode automatically"
    fi
    
    if warp-cli set-proxy-port 8111 2>&1 | grep -qi "success\|ok"; then
        log_success "Set proxy port using set-proxy-port"
    else
        log_warning "Could not set proxy port automatically"
    fi
fi

# Connect WARP
log_info "Connecting WARP..."
CURRENT_STATUS=$(warp-cli status 2>/dev/null | grep -i "status" | awk '{print $2}' || echo "")
if echo "$CURRENT_STATUS" | grep -qi "disconnected"; then
    warp-cli connect 2>&1 | grep -v "Success" || true
    sleep 3
else
    log_info "WARP already connected"
fi

# Verify connection
echo ""
log_info "Verifying WARP configuration..."
WARP_STATUS=$(warp-cli status 2>/dev/null || echo "")
if echo "$WARP_STATUS" | grep -qi "connected"; then
    # Test proxy port
    if nc -z 127.0.0.1 8111 2>/dev/null; then
        log_success "WARP configured and connected (proxy mode, port 8111)"
        
        # Test proxy connection
        log_info "Testing WARP proxy..."
        TEST_IP=$(curl -s --connect-timeout 5 --max-time 10 -x socks5h://127.0.0.1:8111 https://api.ipify.org 2>/dev/null || echo "")
        if [ -n "$TEST_IP" ]; then
            log_success "WARP proxy is working! Your IP: $TEST_IP"
        else
            log_warning "WARP proxy may not be working yet"
        fi
    else
        log_warning "WARP connected but proxy port 8111 not ready yet"
        log_info "Wait a few seconds and try: curl -x socks5h://127.0.0.1:8111 https://api.ipify.org"
    fi
else
    log_warning "WARP may not be connected yet"
    log_info "You can manually connect with: warp-cli connect"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ WARP Installation & Configuration Complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 Useful commands:"
echo "   • Check status: warp-cli status"
echo "   • Check proxy: warp-cli proxy status"
echo "   • Connect: warp-cli connect"
echo "   • Disconnect: warp-cli disconnect"
echo "   • Test proxy: curl -x socks5h://127.0.0.1:8111 https://api.ipify.org"
echo ""

