#!/usr/bin/env bash
# install_warp_manual.sh
# Script cài đặt Cloudflare WARP (chạy với sudo)

set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔐 Cloudflare WARP Installation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Detect OS and architecture
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    OS_VERSION=$VERSION_ID
else
    echo "❌ Cannot detect OS"
    exit 1
fi

ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
    WARP_ARCH="amd64"
elif [ "$ARCH" = "aarch64" ]; then
    WARP_ARCH="arm64"
else
    echo "❌ Unsupported architecture: $ARCH"
    exit 1
fi

echo "📌 OS: $OS $OS_VERSION"
echo "📌 Architecture: $ARCH ($WARP_ARCH)"
echo ""

if [ "$OS" = "ubuntu" ] || [ "$OS" = "debian" ]; then
    echo "📥 Adding Cloudflare GPG key..."
    curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
    
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
    
    echo "📥 Adding Cloudflare repository..."
    echo "deb [arch=${WARP_ARCH} signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ ${CODENAME} main" | sudo tee /etc/apt/sources.list.d/cloudflare-client.list
    
    echo "📥 Updating package list..."
    sudo apt-get update -qq
    
    echo "📥 Installing cloudflare-warp..."
    sudo apt-get install -y cloudflare-warp
    
    echo ""
    echo "✅ WARP installed successfully!"
    echo ""
    echo "📝 Next steps:"
    echo "   1. Register WARP: warp-cli registration new"
    echo "   2. Enable proxy mode: warp-cli proxy enable"
    echo "   3. Set proxy port: warp-cli proxy port 8111"
    echo "   4. Connect: warp-cli connect"
    echo "   5. Test: curl -x socks5h://127.0.0.1:8111 https://api.ipify.org"
    echo ""
else
    echo "❌ Unsupported OS: $OS"
    echo "   Please install WARP manually from: https://1.1.1.1/"
    exit 1
fi

