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

# Update system packages
update_system() {
    log_info "Updating system packages..."
    
    if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
        ${SUDO_CMD} apt-get update -qq
        ${SUDO_CMD} apt-get upgrade -y -qq
        log_success "System packages updated"
    elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ] || [ "$OS" = "fedora" ]; then
        if [ "$OS" = "fedora" ]; then
            ${SUDO_CMD} dnf update -y -q
        else
            ${SUDO_CMD} yum update -y -q
        fi
        log_success "System packages updated"
    else
        log_warning "System update not supported for $OS, skipping..."
    fi
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
    
    # Get latest version from GitHub releases
    log_info "Checking latest Gost version..."
    GOST_VERSION=$(curl -s --connect-timeout 5 --max-time 10 https://api.github.com/repos/ginuerzh/gost/releases/latest 2>/dev/null | jq -r '.tag_name' 2>/dev/null | sed 's/v//' || echo "")
    
    if [ -z "$GOST_VERSION" ] || [ "$GOST_VERSION" = "null" ] || [ "$GOST_VERSION" = "" ]; then
        # Try to get a known working version
        GOST_VERSION="3.0.0-rc8"
        log_warning "Using fallback Gost version: $GOST_VERSION"
    fi
    
    log_info "Downloading Gost v${GOST_VERSION} (${GOST_ARCH})..."
    
    # Try multiple URL formats (correct format is gost_VERSION_linux_ARCH.tar.gz)
    GOST_URLS=(
        "https://github.com/ginuerzh/gost/releases/download/v${GOST_VERSION}/gost_${GOST_VERSION}_linux_${GOST_ARCH}.tar.gz"
        "https://github.com/ginuerzh/gost/releases/download/v${GOST_VERSION}/gost-linux-${GOST_ARCH}-${GOST_VERSION}.gz"
        "https://github.com/ginuerzh/gost/releases/download/v${GOST_VERSION}/gost_${GOST_VERSION}_linux_${GOST_ARCH}.gz"
    )
    
    # Download and install
    cd /tmp
    DOWNLOAD_SUCCESS=false
    
    for GOST_URL in "${GOST_URLS[@]}"; do
        log_info "Trying URL: $GOST_URL"
        if command -v wget &> /dev/null; then
            if wget -q --timeout=10 --spider "$GOST_URL" 2>/dev/null; then
                if wget -q --timeout=30 "$GOST_URL" -O gost.gz; then
                    if [ -f gost.gz ] && [ -s gost.gz ]; then
                        DOWNLOAD_SUCCESS=true
                        log_info "Successfully downloaded from: $GOST_URL"
                        break
                    fi
                fi
            fi
        else
            HTTP_RESPONSE=$(curl -fsSL --connect-timeout 5 --max-time 10 --head "$GOST_URL" 2>/dev/null | head -n 1 || echo "")
            if echo "$HTTP_RESPONSE" | grep -q "200 OK"; then
                if curl -fsSL --connect-timeout 10 --max-time 60 "$GOST_URL" -o gost.gz; then
                    if [ -f gost.gz ] && [ -s gost.gz ]; then
                        DOWNLOAD_SUCCESS=true
                        log_info "Successfully downloaded from: $GOST_URL"
                        break
                    fi
                fi
            fi
        fi
    done
    
    # If all URLs failed, try downloading latest release asset directly from GitHub API
    if [ "$DOWNLOAD_SUCCESS" = false ]; then
        log_warning "Standard URLs failed, trying to find release asset from GitHub API..."
        # Try to find the correct asset name pattern
        ASSET_PATTERNS=(
            "gost_${GOST_VERSION}_linux_${GOST_ARCH}.tar.gz"
            "gost-linux-${GOST_ARCH}-${GOST_VERSION}.gz"
            "gost_${GOST_VERSION}_linux_${GOST_ARCH}.gz"
        )
        
        for PATTERN in "${ASSET_PATTERNS[@]}"; do
            ASSET_URL=$(curl -s --connect-timeout 5 --max-time 10 "https://api.github.com/repos/ginuerzh/gost/releases/latest" 2>/dev/null | \
                jq -r ".assets[] | select(.name == \"${PATTERN}\") | .browser_download_url" 2>/dev/null | head -n 1)
            
            if [ -n "$ASSET_URL" ] && [ "$ASSET_URL" != "null" ]; then
                log_info "Found asset URL: $ASSET_URL"
                if command -v wget &> /dev/null; then
                    if wget -q --timeout=30 "$ASSET_URL" -O gost.gz && [ -f gost.gz ] && [ -s gost.gz ]; then
                        DOWNLOAD_SUCCESS=true
                        break
                    fi
                else
                    if curl -fsSL --connect-timeout 10 --max-time 60 "$ASSET_URL" -o gost.gz && [ -f gost.gz ] && [ -s gost.gz ]; then
                        DOWNLOAD_SUCCESS=true
                        break
                    fi
                fi
            fi
        done
        
        # If still failed, try to find any linux asset matching architecture
        if [ "$DOWNLOAD_SUCCESS" = false ]; then
            ASSET_URL=$(curl -s --connect-timeout 5 --max-time 10 "https://api.github.com/repos/ginuerzh/gost/releases/latest" 2>/dev/null | \
                jq -r ".assets[] | select(.name | contains(\"linux\") and contains(\"${GOST_ARCH}\")) | .browser_download_url" 2>/dev/null | head -n 1)
            
            if [ -n "$ASSET_URL" ] && [ "$ASSET_URL" != "null" ]; then
                log_info "Found matching asset URL: $ASSET_URL"
                if command -v wget &> /dev/null; then
                    wget -q --timeout=30 "$ASSET_URL" -O gost.gz && [ -f gost.gz ] && [ -s gost.gz ] && DOWNLOAD_SUCCESS=true
                else
                    curl -fsSL --connect-timeout 10 --max-time 60 "$ASSET_URL" -o gost.gz && [ -f gost.gz ] && [ -s gost.gz ] && DOWNLOAD_SUCCESS=true
                fi
            fi
        fi
    fi
    
    if [ "$DOWNLOAD_SUCCESS" = false ] || [ ! -f gost.gz ]; then
        log_error "Failed to download Gost from GitHub releases"
        log_info "Trying alternative installation method..."
        
        # Alternative: Install from Go (if available) or use package manager
        if command -v go &> /dev/null; then
            log_info "Installing Gost using Go..."
            go install github.com/ginuerzh/gost/cmd/gost@latest
            if command -v gost &> /dev/null || [ -f "$HOME/go/bin/gost" ]; then
                if [ -f "$HOME/go/bin/gost" ]; then
                    sudo cp "$HOME/go/bin/gost" /usr/local/bin/gost
                    sudo chmod +x /usr/local/bin/gost
                fi
                log_success "Gost installed via Go"
                return
            fi
        fi
        
        log_error "Please install Gost manually:"
        log_info "  Option 1: Download from https://github.com/ginuerzh/gost/releases"
        log_info "  Option 2: Install Go and run: go install github.com/ginuerzh/gost/cmd/gost@latest"
        exit 1
    fi
    
    # Extract based on file type
    log_info "Extracting Gost binary..."
    FILE_TYPE=$(file gost.gz 2>/dev/null || echo "")
    log_info "File type: $FILE_TYPE"
    
    if echo "$FILE_TYPE" | grep -qi "gzip.*compressed"; then
        log_info "Detected gzip compressed file"
        # Gunzip will create file with name without .gz extension
        gunzip -f gost.gz
        # After gunzip, file might be named gost-linux-amd64-2.12.0 or just gost
        if [ -f "gost-linux-${GOST_ARCH}-${GOST_VERSION}" ]; then
            mv "gost-linux-${GOST_ARCH}-${GOST_VERSION}" gost
            log_info "Renamed gost-linux-${GOST_ARCH}-${GOST_VERSION} to gost"
        elif [ -f "gost-linux-${GOST_ARCH}" ]; then
            mv "gost-linux-${GOST_ARCH}" gost
            log_info "Renamed gost-linux-${GOST_ARCH} to gost"
        elif [ ! -f gost ]; then
            log_error "Failed to gunzip file or find extracted binary"
            log_info "Files in /tmp after gunzip:"
            ls -la /tmp/gost* 2>/dev/null || true
            exit 1
        fi
    elif echo "$FILE_TYPE" | grep -qi "tar archive\|POSIX tar"; then
        log_info "Detected tar archive"
        # Extract tar.gz file
        tar -xzf gost.gz
        # Find gost binary in extracted files (usually in a subdirectory like gost_2.12.0_linux_amd64/)
        if [ -f "gost" ]; then
            log_info "Found gost binary in root"
        elif [ -d "gost_${GOST_VERSION}_linux_${GOST_ARCH}" ] && [ -f "gost_${GOST_VERSION}_linux_${GOST_ARCH}/gost" ]; then
            mv "gost_${GOST_VERSION}_linux_${GOST_ARCH}/gost" gost
            log_info "Found gost in subdirectory gost_${GOST_VERSION}_linux_${GOST_ARCH}/"
        elif [ -f "gost-linux-${GOST_ARCH}-${GOST_VERSION}" ]; then
            mv "gost-linux-${GOST_ARCH}-${GOST_VERSION}" gost
            log_info "Found gost-linux-${GOST_ARCH}-${GOST_VERSION}"
        else
            # Search for gost binary in current directory and subdirectories
            FOUND_GOST=$(find . -maxdepth 3 -name "gost" -type f ! -name "*.gz" ! -name "*.tar" 2>/dev/null | head -n 1)
            if [ -n "$FOUND_GOST" ] && [ "$FOUND_GOST" != "./gost" ]; then
                mv "$FOUND_GOST" gost
                log_info "Found gost at: $FOUND_GOST"
            else
                # Try to find any executable file that's not a script
                FOUND_BIN=$(find . -maxdepth 3 -type f -executable ! -name "*.sh" ! -name "*.py" ! -name "*.gz" ! -name "*.tar" 2>/dev/null | head -n 1)
                if [ -n "$FOUND_BIN" ] && [ "$FOUND_BIN" != "./gost" ]; then
                    mv "$FOUND_BIN" gost
                    log_info "Found binary at: $FOUND_BIN"
                fi
            fi
        fi
    elif echo "$FILE_TYPE" | grep -qi "executable\|ELF"; then
        log_info "File appears to be executable already"
        mv gost.gz gost
    else
        log_info "Unknown file type, trying to extract..."
        # Try gunzip first
        if gunzip -f gost.gz 2>/dev/null; then
            log_info "Successfully extracted with gunzip"
        elif tar -xzf gost.gz 2>/dev/null; then
            log_info "Successfully extracted with tar"
            # Find the binary
            FOUND_GOST=$(find . -maxdepth 3 -name "gost" -type f 2>/dev/null | head -n 1)
            if [ -n "$FOUND_GOST" ] && [ "$FOUND_GOST" != "./gost" ]; then
                mv "$FOUND_GOST" gost
            fi
        else
            # Last resort: try to use as-is
            log_warning "Could not extract, trying to use file as-is"
            mv gost.gz gost
        fi
    fi
    
    # Verify we have the binary
    if [ ! -f gost ]; then
        log_error "Failed to extract Gost binary"
        log_info "File type was: $FILE_TYPE"
        log_info "Contents of /tmp:"
        ls -la /tmp/gost* 2>/dev/null || true
        exit 1
    fi
    
    # Make sure it's executable
    chmod +x gost
    
    # Verify it's actually a binary
    BINARY_TYPE=$(file gost 2>/dev/null || echo "")
    log_info "Extracted binary type: $BINARY_TYPE"
    if ! echo "$BINARY_TYPE" | grep -qi "executable\|ELF"; then
        log_warning "File may not be a valid binary, but continuing..."
    fi
    ${SUDO_CMD} mv gost /usr/local/bin/gost
    
    # Verify installation
    if gost -V &> /dev/null; then
        log_success "Gost installed: $(gost -V)"
    else
        log_success "Gost installed to /usr/local/bin/gost"
    fi
}

# Install Cloudflare WARP
install_warp() {
    log_info "Installing Cloudflare WARP..."
    
    if command -v warp-cli &> /dev/null; then
        log_warning "WARP CLI already installed: $(command -v warp-cli)"
        log_info "Checking WARP configuration..."
        
        # Check if already configured (try different syntax for Linux)
        WARP_STATUS=$(warp-cli status 2>/dev/null || echo "")
        WARP_SETTINGS=$(warp-cli settings 2>/dev/null || echo "")
        
        if echo "$WARP_STATUS" | grep -qi "connected" && \
           (echo "$WARP_SETTINGS" | grep -qi "proxy\|mode.*proxy" || \
            echo "$WARP_SETTINGS" | grep -qi "8111\|port.*8111"); then
            log_success "WARP already configured"
            return
        fi
    else
        log_info "Installing Cloudflare WARP CLI..."
        
        if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
            # Install WARP from Cloudflare repository (recommended method)
            log_info "Adding Cloudflare WARP repository..."
            
            ARCH=$(uname -m)
            if [ "$ARCH" = "x86_64" ]; then
                WARP_ARCH="amd64"
            elif [ "$ARCH" = "aarch64" ]; then
                WARP_ARCH="arm64"
            else
                log_error "Unsupported architecture for WARP: $ARCH"
                return
            fi
            
            # Install GPG key
            curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg 2>/dev/null || {
                log_warning "Failed to add GPG key, trying alternative method..."
                curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo apt-key add - 2>/dev/null || true
            }
            
            # Detect Ubuntu/Debian codename
            if command -v lsb_release &> /dev/null; then
                CODENAME=$(lsb_release -cs)
            elif [ -f /etc/os-release ]; then
                CODENAME=$(grep VERSION_CODENAME /etc/os-release | cut -d= -f2)
                if [ -z "$CODENAME" ]; then
                    # Fallback for older systems
                    CODENAME=$(grep VERSION_ID /etc/os-release | cut -d= -f2 | tr -d '"' | cut -d. -f1)
                    case "$CODENAME" in
                        20) CODENAME="focal" ;;
                        22) CODENAME="jammy" ;;
                        24) CODENAME="noble" ;;
                        *) CODENAME="jammy" ;; # Default fallback
                    esac
                fi
            else
                CODENAME="jammy" # Default fallback
            fi
            
            # Add repository
            echo "deb [arch=${WARP_ARCH} signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ ${CODENAME} main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list > /dev/null
            
            # Update and install
            sudo apt-get update -qq
            sudo apt-get install -y cloudflare-warp
            
        elif [ "$OS" = "centos" ] || [ "$OS" = "rhel" ] || [ "$OS" = "fedora" ]; then
            log_info "Installing WARP from Cloudflare repository..."
            
            ARCH=$(uname -m)
            if [ "$ARCH" = "x86_64" ]; then
                WARP_ARCH="x86_64"
            elif [ "$ARCH" = "aarch64" ]; then
                WARP_ARCH="aarch64"
            else
                log_error "Unsupported architecture for WARP: $ARCH"
                return
            fi
            
            if [ "$OS" = "fedora" ]; then
                sudo dnf install -y 'https://pkg.cloudflareclient.com/packages/fedora/cloudflare-warp-2024.12.0-1.${WARP_ARCH}.rpm' || \
                (curl https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg && \
                 echo -e "[cloudflare-client]\nname=Cloudflare Client\nbaseurl=https://pkg.cloudflareclient.com/packages/fedora\nenabled=1\ngpgcheck=1\ngpgkey=file:///usr/share/keyrings/cloudflare-warp-archive-keyring.gpg" | sudo tee /etc/yum.repos.d/cloudflare-warp.repo && \
                 sudo dnf install -y cloudflare-warp)
            else
                sudo yum install -y 'https://pkg.cloudflareclient.com/packages/el8/cloudflare-warp-2024.12.0-1.${WARP_ARCH}.rpm' || \
                (curl https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg && \
                 echo -e "[cloudflare-client]\nname=Cloudflare Client\nbaseurl=https://pkg.cloudflareclient.com/packages/el8\nenabled=1\ngpgcheck=1\ngpgkey=file:///usr/share/keyrings/cloudflare-warp-archive-keyring.gpg" | sudo tee /etc/yum.repos.d/cloudflare-warp.repo && \
                 sudo yum install -y cloudflare-warp)
            fi
        else
            log_warning "WARP installation not supported for $OS. Please install manually from https://1.1.1.1/"
            return
        fi
        
        # Verify installation
        if ! command -v warp-cli &> /dev/null; then
            log_error "Failed to install WARP CLI"
            log_info "Please install manually from: https://1.1.1.1/"
            return
        fi
        
        log_success "WARP CLI installed"
    fi
    
    # Configure WARP
    log_info "Configuring Cloudflare WARP..."
    
    # Wait for WARP daemon to be ready (may take a few seconds after installation)
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
        # Try different registration commands
        if warp-cli registration new 2>&1 | grep -qi "success\|ok\|registered"; then
            log_info "WARP registered using 'registration new'"
        elif warp-cli register 2>&1 | grep -qi "success\|ok\|registered"; then
            log_info "WARP registered using 'register'"
        else
            log_warning "WARP registration may have failed, but continuing..."
        fi
        sleep 2
    else
        log_info "WARP already registered"
    fi
    
    # Set proxy mode (Linux WARP CLI uses 'proxy' subcommand)
    log_info "Setting WARP to proxy mode..."
    
    # Check if proxy subcommand exists
    if warp-cli proxy --help 2>/dev/null | grep -q "proxy"; then
        # Linux WARP CLI syntax: warp-cli proxy enable
        PROXY_STATUS=$(warp-cli proxy status 2>/dev/null || echo "")
        if echo "$PROXY_STATUS" | grep -qi "enabled\|on\|active"; then
            log_info "WARP proxy already enabled"
        else
            log_info "Enabling WARP proxy mode..."
            warp-cli proxy enable 2>&1 | grep -v "Success" || true
            sleep 2
        fi
        
        # Set proxy port to 8111 (correct syntax: warp-cli proxy port 8111)
        log_info "Setting WARP proxy port to 8111..."
        CURRENT_PORT=$(warp-cli proxy status 2>/dev/null | grep -i "port" | awk '{print $NF}' || echo "")
        
        if echo "$CURRENT_PORT" | grep -q "8111"; then
            log_info "WARP proxy port already set to 8111"
        else
            # Use correct syntax: warp-cli proxy port 8111
            log_info "Running: warp-cli proxy port 8111"
            warp-cli proxy port 8111 2>&1 | grep -v "Success" || true
            sleep 2
            
            # Verify port was set
            VERIFY_PORT=$(warp-cli proxy status 2>/dev/null | grep -i "port" | awk '{print $NF}' || echo "")
            if echo "$VERIFY_PORT" | grep -q "8111"; then
                log_success "WARP proxy port set to 8111"
            else
                log_warning "Could not verify proxy port, but command executed"
                log_info "You can verify with: warp-cli proxy status"
            fi
        fi
    else
        # Fallback: Try macOS syntax or config file
        log_warning "WARP proxy subcommand not available, trying alternative methods..."
        
        # Try macOS syntax (may work on some Linux versions)
        if warp-cli set-mode proxy 2>&1 | grep -qi "success\|ok"; then
            log_info "Set proxy mode using set-mode"
        else
            log_warning "Could not set proxy mode automatically"
            log_info "WARP proxy mode configuration skipped"
            log_info "You can configure it manually later if needed"
        fi
        
        # Try to set port
        if warp-cli set-proxy-port 8111 2>&1 | grep -qi "success\|ok"; then
            log_info "Set proxy port using set-proxy-port"
        else
            log_warning "Could not set proxy port automatically"
            log_info "Proxy port configuration skipped"
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
    if warp-cli status 2>/dev/null | grep -qi "connected"; then
        # Test proxy port
        if nc -z 127.0.0.1 8111 2>/dev/null; then
            log_success "WARP configured and connected (proxy mode, port 8111)"
        else
            log_warning "WARP connected but proxy port 8111 not ready yet"
        fi
    else
        log_warning "WARP may not be connected yet. It will be checked when services start."
        log_info "You can manually connect with: warp-cli connect"
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

# Create test Gost configuration
create_test_gost_config() {
    log_info "Creating test Gost configuration..."
    
    INSTALL_DIR="$HOME/mac_proxy"
    CONFIG_DIR="$INSTALL_DIR/config"
    
    # Create config directory if it doesn't exist
    mkdir -p "$CONFIG_DIR"
    
    # Create a simple test config for Gost on port 7891
    # Using a simple HTTP proxy for testing (you can change this later)
    TEST_CONFIG_FILE="$CONFIG_DIR/gost_7891.config"
    
    if [ ! -f "$TEST_CONFIG_FILE" ]; then
        log_info "Creating test Gost config on port 7891..."
        
        # Create a simple test config using a public proxy or direct connection
        # For testing, we'll use a simple SOCKS5 listener that forwards to WARP
        cat > "$TEST_CONFIG_FILE" <<EOF
{
    "port": "7891",
    "provider": "test",
    "country": "test",
    "proxy_url": "socks5://127.0.0.1:8111",
    "proxy_host": "127.0.0.1",
    "proxy_port": "8111",
    "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
        log_success "Test Gost config created: $TEST_CONFIG_FILE"
        log_info "This config forwards to WARP proxy (127.0.0.1:8111) for testing"
        log_info "You can modify this config later or create new ones via Web UI"
    else
        log_info "Gost config already exists: $TEST_CONFIG_FILE"
    fi
    
    # Also create a test script to start Gost manually
    TEST_SCRIPT="$INSTALL_DIR/test_gost.sh"
    if [ ! -f "$TEST_SCRIPT" ]; then
        log_info "Creating test script: $TEST_SCRIPT"
        cat > "$TEST_SCRIPT" <<'TEST_EOF'
#!/usr/bin/env bash
# test_gost.sh
# Script để test Gost configuration

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 Testing Gost Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if Gost is installed
if ! command -v gost &> /dev/null; then
    echo "❌ Gost is not installed"
    echo "   Run: cd $SCRIPT_DIR && ./install_linux.sh"
    exit 1
fi

echo "✅ Gost found: $(command -v gost)"
echo ""

# Check if config exists
if [ ! -f "config/gost_7891.config" ]; then
    echo "❌ Config file not found: config/gost_7891.config"
    exit 1
fi

echo "✅ Config file found: config/gost_7891.config"
echo ""

# Read config
PROXY_URL=$(cat config/gost_7891.config | jq -r '.proxy_url // ""' 2>/dev/null || echo "")
PORT=$(cat config/gost_7891.config | jq -r '.port // "7891"' 2>/dev/null || echo "7891")

if [ -z "$PROXY_URL" ] || [ "$PROXY_URL" = "null" ]; then
    echo "❌ Invalid config: proxy_url is empty"
    exit 1
fi

echo "📋 Config details:"
echo "   Port: $PORT"
echo "   Proxy URL: $PROXY_URL"
echo ""

# Check if port is already in use
if command -v lsof &> /dev/null; then
    if lsof -i :$PORT >/dev/null 2>&1; then
        echo "⚠️  Port $PORT is already in use"
        lsof -i :$PORT
        echo ""
        read -p "Do you want to kill the process and restart? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            lsof -ti :$PORT | xargs kill -9 2>/dev/null || true
            sleep 1
        else
            exit 1
        fi
    fi
fi

# Start Gost
echo "🚀 Starting Gost on port $PORT..."
echo "   Command: gost -L socks5://:$PORT -F $PROXY_URL"
echo ""

mkdir -p logs
nohup gost -L socks5://:$PORT -F "$PROXY_URL" > logs/gost_${PORT}_test.log 2>&1 &
GOST_PID=$!

sleep 2

# Check if Gost started successfully
if kill -0 "$GOST_PID" 2>/dev/null; then
    echo "✅ Gost started successfully (PID: $GOST_PID)"
    echo ""
    echo "🧪 Testing proxy connection..."
    
    # Test the proxy
    if curl -s --connect-timeout 5 --max-time 10 -x "socks5h://127.0.0.1:$PORT" https://api.ipify.org >/dev/null 2>&1; then
        IP=$(curl -s --connect-timeout 5 --max-time 10 -x "socks5h://127.0.0.1:$PORT" https://api.ipify.org 2>/dev/null || echo "N/A")
        echo "✅ Proxy is working!"
        echo "   Your IP through proxy: $IP"
        echo ""
        echo "📊 Proxy endpoint: socks5://127.0.0.1:$PORT"
        echo "📝 Logs: logs/gost_${PORT}_test.log"
        echo ""
        echo "🛑 To stop Gost: kill $GOST_PID"
    else
        echo "⚠️  Proxy started but connection test failed"
        echo "   Check logs: logs/gost_${PORT}_test.log"
        echo "   PID: $GOST_PID"
    fi
else
    echo "❌ Failed to start Gost"
    echo "   Check logs: logs/gost_${PORT}_test.log"
    exit 1
fi
TEST_EOF
        chmod +x "$TEST_SCRIPT"
        log_success "Test script created: $TEST_SCRIPT"
    else
        log_info "Test script already exists: $TEST_SCRIPT"
    fi
    
    log_info "To test Gost, run: cd $INSTALL_DIR && ./test_gost.sh"
}

# Main installation
main() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🚀 Mac Proxy - Linux Installation Script"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Detect if running as root and set SUDO_CMD accordingly
    # Don't block execution, just adjust behavior
    IS_ROOT=false
    USER_ID=$(id -u 2>/dev/null || echo "0")
    
    if [ "$USER_ID" -eq 0 ]; then
        IS_ROOT=true
        log_warning "⚠️  Running as root user detected"
        log_info "Continuing installation as root (sudo not needed)..."
        log_info ""
        SUDO_CMD=""
    else
        # Check sudo access for non-root users
        if ! sudo -n true 2>/dev/null; then
            log_info "This script requires sudo access. You may be prompted for your password."
            if ! sudo -v 2>/dev/null; then
                log_error "Cannot obtain sudo access. Please ensure you have sudo privileges."
                exit 1
            fi
        fi
        SUDO_CMD="sudo"
    fi
    
    detect_os
    update_system
    install_dependencies
    install_gost
    install_warp
    clone_repo
    install_python_deps
    make_executable
    create_launch_script
    create_test_gost_config
    
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
    echo "🧪 To test Gost:"
    echo "   cd $HOME/mac_proxy"
    echo "   ./test_gost.sh"
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
        
        # Wait a bit and check HAProxy 7890 status
        sleep 3
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "📊 Checking service status..."
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        # Check HAProxy 7890
        HAPROXY_PID_FILE="$HOME/mac_proxy/services/haproxy_7890/logs/haproxy_7890.pid"
        if [ -f "$HAPROXY_PID_FILE" ]; then
            HAPROXY_PID=$(cat "$HAPROXY_PID_FILE" 2>/dev/null || echo "")
            if [ -n "$HAPROXY_PID" ] && kill -0 "$HAPROXY_PID" 2>/dev/null; then
                echo "✅ HAProxy 7890: Running (PID: $HAPROXY_PID)"
                echo "   Proxy: socks5://0.0.0.0:7890"
            else
                echo "❌ HAProxy 7890: Not running"
                echo "   Try: cd $HOME/mac_proxy && ./launch_linux.sh start"
            fi
        else
            echo "❌ HAProxy 7890: Not started"
            echo "   Try: cd $HOME/mac_proxy && ./launch_linux.sh start"
        fi
        
        # Check WARP
        if nc -z 127.0.0.1 8111 2>/dev/null; then
            echo "✅ WARP Proxy: Running on port 8111"
        else
            echo "⚠️  WARP Proxy: Port 8111 not accessible"
        fi
        
        echo ""
        echo "📝 To check full status: cd $HOME/mac_proxy && ./launch_linux.sh status"
    else
        echo ""
        echo "💡 To start the system later:"
        echo "   cd $HOME/mac_proxy"
        echo "   ./launch_linux.sh start"
    fi
}

# Run main function
main "$@"

