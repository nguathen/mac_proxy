#!/usr/bin/env bash
# reinstall_gost.sh
# Reinstall Gost binary đúng cách

set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄 Reinstalling Gost Binary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

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
        echo "❌ Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

echo "📌 Architecture: $ARCH ($GOST_ARCH)"
echo ""

# Stop any running Gost processes
echo "📌 Stopping running Gost processes..."
pkill -9 gost 2>/dev/null || true
sleep 1
echo "✅ Gost processes stopped"
echo ""

# Remove old binary if exists
if [ -f "/usr/local/bin/gost" ]; then
    echo "📌 Removing old Gost binary..."
    sudo rm -f /usr/local/bin/gost
    echo "✅ Old binary removed"
    echo ""
fi

# Get latest version
echo "📌 Checking latest Gost version..."
GOST_VERSION=$(curl -s --connect-timeout 5 --max-time 10 https://api.github.com/repos/ginuerzh/gost/releases/latest 2>/dev/null | grep -oP '"tag_name":\s*"v\K[^"]+' | head -n 1 || echo "")

if [ -z "$GOST_VERSION" ]; then
    # Try with jq if available
    if command -v jq &> /dev/null; then
        GOST_VERSION=$(curl -s --connect-timeout 5 --max-time 10 https://api.github.com/repos/ginuerzh/gost/releases/latest 2>/dev/null | jq -r '.tag_name' 2>/dev/null | sed 's/v//' || echo "")
    fi
fi

if [ -z "$GOST_VERSION" ] || [ "$GOST_VERSION" = "null" ]; then
    GOST_VERSION="3.0.0-rc8"
    echo "⚠️  Using fallback version: $GOST_VERSION"
else
    echo "✅ Found version: $GOST_VERSION"
fi
echo ""

# Download to temp directory
TMP_DIR=$(mktemp -d)
cd "$TMP_DIR"

echo "📌 Downloading Gost v${GOST_VERSION}..."
GOST_URL="https://github.com/ginuerzh/gost/releases/download/v${GOST_VERSION}/gost_${GOST_VERSION}_linux_${GOST_ARCH}.tar.gz"

if command -v wget &> /dev/null; then
    wget -q --timeout=30 "$GOST_URL" -O gost.tar.gz || {
        echo "❌ Failed to download from primary URL, trying alternative..."
        # Try alternative URL
        GOST_URL="https://github.com/ginuerzh/gost/releases/download/v${GOST_VERSION}/gost-linux-${GOST_ARCH}-${GOST_VERSION}.gz"
        wget -q --timeout=30 "$GOST_URL" -O gost.gz || {
            echo "❌ Download failed"
            exit 1
        }
    }
else
    curl -fsSL --connect-timeout 10 --max-time 60 "$GOST_URL" -o gost.tar.gz || {
        echo "❌ Failed to download from primary URL, trying alternative..."
        GOST_URL="https://github.com/ginuerzh/gost/releases/download/v${GOST_VERSION}/gost-linux-${GOST_ARCH}-${GOST_VERSION}.gz"
        curl -fsSL --connect-timeout 10 --max-time 60 "$GOST_URL" -o gost.gz || {
            echo "❌ Download failed"
            exit 1
        }
    }
fi

echo "✅ Download completed"
echo ""

# Extract
echo "📌 Extracting Gost binary..."
if [ -f gost.tar.gz ]; then
    tar -xzf gost.tar.gz
    # Find the binary
    if [ -f "gost_${GOST_VERSION}_linux_${GOST_ARCH}/gost" ]; then
        mv "gost_${GOST_VERSION}_linux_${GOST_ARCH}/gost" gost
        echo "✅ Extracted from tar.gz"
    elif [ -f "gost" ]; then
        echo "✅ Found gost binary"
    else
        # Search for binary
        FOUND=$(find . -name "gost" -type f ! -name "*.gz" ! -name "*.tar" 2>/dev/null | head -n 1)
        if [ -n "$FOUND" ]; then
            mv "$FOUND" gost
            echo "✅ Found binary at: $FOUND"
        else
            echo "❌ Could not find gost binary in archive"
            ls -la
            exit 1
        fi
    fi
elif [ -f gost.gz ]; then
    gunzip -f gost.gz
    if [ -f "gost-linux-${GOST_ARCH}-${GOST_VERSION}" ]; then
        mv "gost-linux-${GOST_ARCH}-${GOST_VERSION}" gost
    fi
    echo "✅ Extracted from .gz"
fi

# Verify it's a binary
if [ ! -f gost ]; then
    echo "❌ Gost binary not found after extraction"
    ls -la
    exit 1
fi

BINARY_TYPE=$(file gost 2>/dev/null || echo "")
echo "📌 Binary type: $BINARY_TYPE"

if ! echo "$BINARY_TYPE" | grep -qi "executable\|ELF"; then
    echo "⚠️  Warning: File may not be a valid binary"
    echo "   Type: $BINARY_TYPE"
    read -p "   Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Make executable
chmod +x gost

# Test the binary
echo ""
echo "📌 Testing binary..."
if ./gost -V &> /dev/null; then
    VERSION=$(./gost -V 2>&1 || echo "unknown")
    echo "✅ Binary works! Version: $VERSION"
else
    echo "⚠️  Binary test failed, but continuing..."
fi
echo ""

# Install
echo "📌 Installing to /usr/local/bin/gost..."
sudo mv gost /usr/local/bin/gost
sudo chmod +x /usr/local/bin/gost

# Verify installation
echo ""
echo "📌 Verifying installation..."
if command -v gost &> /dev/null; then
    INSTALLED_VERSION=$(gost -V 2>&1 || echo "unknown")
    echo "✅ Gost installed successfully!"
    echo "   Location: $(command -v gost)"
    echo "   Version: $INSTALLED_VERSION"
else
    echo "❌ Installation verification failed"
    exit 1
fi

# Cleanup
cd /
rm -rf "$TMP_DIR"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Gost reinstallation completed!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 You can now restart Gost services:"
echo "   cd ~/mac_proxy"
echo "   ./manage_gost.sh restart"
echo ""

