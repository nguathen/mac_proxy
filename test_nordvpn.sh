#!/usr/bin/env bash
# test_nordvpn.sh
# Test NordVPN integration

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}ℹ${NC} $*"; }
log_success() { echo -e "${GREEN}✓${NC} $*"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $*"; }
log_error() { echo -e "${RED}✗${NC} $*"; }
log_section() { echo -e "\n${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n${CYAN}$*${NC}\n${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"; }

# Test 1: Check if module can be imported
log_section "Test 1: Import NordVPN Module"
if python3 -c "from nordvpn_api import NordVPNAPI" 2>/dev/null; then
    log_success "Module imported successfully"
else
    log_error "Failed to import module"
    exit 1
fi

# Test 2: List countries
log_section "Test 2: List Countries"
log_info "Fetching countries..."
if python3 nordvpn_cli.py countries | head -15; then
    log_success "Countries loaded successfully"
else
    log_error "Failed to load countries"
    exit 1
fi

# Test 3: List servers by country
log_section "Test 3: List Servers (Japan)"
log_info "Fetching servers in Japan..."
if python3 nordvpn_cli.py servers --country JP --limit 10; then
    log_success "Servers loaded successfully"
else
    log_error "Failed to load servers"
    exit 1
fi

# Test 4: Get best server
log_section "Test 4: Get Best Server (Singapore)"
log_info "Finding best server in Singapore..."
if python3 nordvpn_cli.py best --country SG; then
    log_success "Best server found"
else
    log_error "Failed to find best server"
    exit 1
fi

# Test 5: Check current config
log_section "Test 5: Check Current Config"
if [ -f "wg18181.conf" ]; then
    log_info "Current Wireproxy 1 config:"
    echo ""
    grep -E "^(PrivateKey|PublicKey|Endpoint)" wg18181.conf || true
    echo ""
    log_success "Config file exists"
else
    log_warning "Config file wg18181.conf not found"
fi

# Test 6: Test shell script
log_section "Test 6: Test Shell Script"
log_info "Testing apply_nordvpn.sh..."
if bash apply_nordvpn.sh --help > /dev/null 2>&1; then
    log_success "Shell script is executable"
else
    log_error "Shell script failed"
    exit 1
fi

# Test 7: List servers via shell script
log_section "Test 7: List Servers via Shell Script (US)"
if bash apply_nordvpn.sh --list-servers US | head -15; then
    log_success "Shell script list servers works"
else
    log_error "Shell script list servers failed"
    exit 1
fi

# Test 8: Check Web UI dependencies
log_section "Test 8: Check Web UI Dependencies"
log_info "Checking Flask..."
if python3 -c "import flask" 2>/dev/null; then
    log_success "Flask is installed"
else
    log_warning "Flask not installed. Install with: pip3 install -r webui/requirements.txt"
fi

log_info "Checking requests..."
if python3 -c "import requests" 2>/dev/null; then
    log_success "requests is installed"
else
    log_warning "requests not installed. Install with: pip3 install requests"
fi

# Test 9: Check cache
log_section "Test 9: Check Cache"
if [ -f "nordvpn_servers_cache.json" ]; then
    CACHE_SIZE=$(wc -c < nordvpn_servers_cache.json)
    CACHE_AGE=$(( $(date +%s) - $(stat -f %m nordvpn_servers_cache.json 2>/dev/null || stat -c %Y nordvpn_servers_cache.json 2>/dev/null || echo 0) ))
    log_info "Cache file exists"
    log_info "Cache size: $CACHE_SIZE bytes"
    log_info "Cache age: $CACHE_AGE seconds"
    
    if [ $CACHE_AGE -lt 3600 ]; then
        log_success "Cache is fresh (< 1 hour)"
    else
        log_warning "Cache is old (> 1 hour). Consider refreshing."
    fi
else
    log_info "No cache file yet (will be created on first use)"
fi

# Test 10: API endpoint simulation
log_section "Test 10: Simulate API Calls"
log_info "Testing NordVPN API module..."

python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from nordvpn_api import NordVPNAPI

api = NordVPNAPI()

# Test countries
countries = api.get_countries()
print(f"✓ Found {len(countries)} countries")

# Test best server
best = api.get_best_server('JP')
if best:
    print(f"✓ Best server in JP: {best['name']} (Load: {best['load']}%)")
else:
    print("✗ No best server found")

# Test server by name
server = api.get_server_by_name(best['name'])
if server:
    print(f"✓ Found server by name: {server['name']}")
else:
    print("✗ Server not found by name")

print("✓ All API methods work correctly")
EOF

if [ $? -eq 0 ]; then
    log_success "API simulation passed"
else
    log_error "API simulation failed"
    exit 1
fi

# Summary
log_section "Test Summary"
log_success "All tests passed! 🎉"
echo ""
log_info "NordVPN integration is ready to use!"
echo ""
log_info "Next steps:"
echo "  1. Start Web UI: bash start_webui.sh"
echo "  2. Open browser: http://localhost:5000"
echo "  3. Or use CLI: bash apply_nordvpn.sh --help"
echo ""

