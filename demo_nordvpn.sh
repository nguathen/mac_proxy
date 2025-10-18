#!/usr/bin/env bash
# demo_nordvpn.sh
# Demo script để showcase NordVPN integration

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
BOLD='\033[1m'
NC='\033[0m' # No Color

print_header() {
    echo -e "\n${MAGENTA}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║${NC} ${CYAN}${BOLD}$1${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════╝${NC}\n"
}

print_step() {
    echo -e "${BLUE}▶${NC} ${BOLD}$1${NC}"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_info() {
    echo -e "${CYAN}ℹ${NC} $1"
}

pause() {
    echo -e "\n${YELLOW}Press Enter to continue...${NC}"
    read -r
}

clear

cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   ███╗   ██╗ ██████╗ ██████╗ ██████╗ ██╗   ██╗██████╗ ███╗   ██╗
║   ████╗  ██║██╔═══██╗██╔══██╗██╔══██╗██║   ██║██╔══██╗████╗  ██║
║   ██╔██╗ ██║██║   ██║██████╔╝██║  ██║██║   ██║██████╔╝██╔██╗ ██║
║   ██║╚██╗██║██║   ██║██╔══██╗██║  ██║╚██╗ ██╔╝██╔═══╝ ██║╚██╗██║
║   ██║ ╚████║╚██████╔╝██║  ██║██████╔╝ ╚████╔╝ ██║     ██║ ╚████║
║   ╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═╝╚═════╝   ╚═══╝  ╚═╝     ╚═╝  ╚═══╝
║                                                               ║
║              Integration Demo - Mac Proxy System             ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF

echo -e "\n${CYAN}This demo will showcase the NordVPN integration features.${NC}\n"
pause

# Demo 1: List Countries
print_header "Demo 1: List Available Countries"
print_step "Fetching list of countries with NordVPN servers..."
sleep 1

python3 nordvpn_cli.py countries | head -20

print_success "Found 46 countries with NordVPN servers!"
pause

# Demo 2: List Servers by Country
print_header "Demo 2: List Servers in Japan"
print_step "Fetching top 10 servers in Japan (sorted by load)..."
sleep 1

python3 nordvpn_cli.py servers --country JP --limit 10

print_success "Servers are automatically sorted by load (lowest first)!"
pause

# Demo 3: Get Best Server
print_header "Demo 3: Find Best Server"
print_step "Finding the best server in Singapore..."
sleep 1

python3 nordvpn_cli.py best --country SG

print_success "Best server found based on lowest load!"
pause

# Demo 4: Show Current Config
print_header "Demo 4: Current Wireproxy Configuration"
print_step "Showing current Wireproxy 1 configuration..."
sleep 1

if [ -f "wg18181.conf" ]; then
    echo -e "${CYAN}Current config:${NC}"
    echo ""
    cat wg18181.conf
    echo ""
    print_info "Private key is preserved when switching servers"
else
    echo -e "${YELLOW}Config file not found${NC}"
fi
pause

# Demo 5: Shell Script Features
print_header "Demo 5: Shell Script Helper"
print_step "The apply_nordvpn.sh script provides easy server management..."
sleep 1

echo -e "${CYAN}Available commands:${NC}\n"
bash apply_nordvpn.sh --help

pause

# Demo 6: List Servers via Shell Script
print_header "Demo 6: List Servers via Shell Script"
print_step "Using shell script to list servers in United States..."
sleep 1

bash apply_nordvpn.sh --list-servers US | head -15

print_success "Shell script provides a user-friendly interface!"
pause

# Demo 7: Show Cache
print_header "Demo 7: Server Cache"
print_step "Checking server cache..."
sleep 1

if [ -f "nordvpn_servers_cache.json" ]; then
    CACHE_SIZE=$(wc -c < nordvpn_servers_cache.json)
    CACHE_SIZE_MB=$(echo "scale=2; $CACHE_SIZE / 1024 / 1024" | bc)
    CACHE_AGE=$(( $(date +%s) - $(stat -f %m nordvpn_servers_cache.json 2>/dev/null || stat -c %Y nordvpn_servers_cache.json 2>/dev/null || echo 0) ))
    CACHE_AGE_MIN=$(( $CACHE_AGE / 60 ))
    
    print_info "Cache file: nordvpn_servers_cache.json"
    print_info "Cache size: ${CACHE_SIZE_MB} MB"
    print_info "Cache age: ${CACHE_AGE_MIN} minutes"
    print_info "Cache expires after 60 minutes"
    
    if [ $CACHE_AGE -lt 3600 ]; then
        print_success "Cache is fresh and will be used for faster lookups!"
    else
        echo -e "${YELLOW}⚠${NC} Cache is old. Will refresh on next API call."
    fi
else
    print_info "No cache file yet (will be created on first use)"
fi
pause

# Demo 8: API Endpoints
print_header "Demo 8: Web UI API Endpoints"
print_step "The Web UI provides REST API endpoints..."
sleep 1

cat << EOF
${CYAN}Available API endpoints:${NC}

${BOLD}GET${NC}  /api/nordvpn/countries
      → List all countries

${BOLD}GET${NC}  /api/nordvpn/servers
      → List all servers (with optional ?refresh=true)

${BOLD}GET${NC}  /api/nordvpn/servers/:country_code
      → List servers by country (e.g., /api/nordvpn/servers/JP)

${BOLD}GET${NC}  /api/nordvpn/best?country=:code
      → Get best server (optionally filtered by country)

${BOLD}POST${NC} /api/nordvpn/apply/:instance
      → Apply server to wireproxy instance
      Body: {"server_name": "Japan #720"}

${CYAN}Example:${NC}
  curl http://localhost:5000/api/nordvpn/countries
  curl http://localhost:5000/api/nordvpn/servers/JP
  curl http://localhost:5000/api/nordvpn/best?country=SG

EOF

pause

# Demo 9: Workflow Example
print_header "Demo 9: Typical Workflow"
print_step "Here's how you would switch to a Japan server..."
sleep 1

cat << 'EOF'
# Step 1: List servers in Japan
bash apply_nordvpn.sh --list-servers JP

# Step 2: Apply best server automatically
bash apply_nordvpn.sh --instance 1 --country JP

# Or apply specific server
bash apply_nordvpn.sh --instance 1 --server "Japan #720"

# Step 3: Script will:
#   - Backup current config
#   - Update config with new server
#   - Ask to restart wireproxy
#   - Test connection
#   - Show your new IP

# Alternative: Use Web UI
# 1. Open http://localhost:5000
# 2. Scroll to "NordVPN Server Selection"
# 3. Select country → Select server → Click "Apply"
EOF

print_success "Simple and automated workflow!"
pause

# Demo 10: Features Summary
print_header "Demo 10: Features Summary"

cat << EOF
${BOLD}${GREEN}✓${NC} ${BOLD}Key Features:${NC}

  🌍 ${CYAN}5000+ Servers${NC} across 46 countries
  
  ⚡ ${CYAN}Automatic Best Server${NC} selection based on load
  
  🔄 ${CYAN}Auto Cache${NC} with 1-hour expiration
  
  🖥️  ${CYAN}Web UI Integration${NC} for easy management
  
  💻 ${CYAN}CLI Tools${NC} for automation
  
  🛡️  ${CYAN}Private Key Preservation${NC} when switching servers
  
  📦 ${CYAN}Automatic Backup${NC} before config changes
  
  🔌 ${CYAN}One-Click Apply${NC} and restart
  
  🧪 ${CYAN}Connection Testing${NC} after apply

${BOLD}${MAGENTA}Files Created:${NC}

  📄 nordvpn_api.py          - Core API module
  📄 nordvpn_cli.py          - CLI tool
  📄 apply_nordvpn.sh        - Shell helper script
  📄 test_nordvpn.sh         - Test suite
  📄 NORDVPN.md              - Full documentation
  📄 NORDVPN_QUICKSTART.md   - Quick start guide
  📄 webui/app.py            - Updated with NordVPN endpoints
  📄 webui/templates/index.html - Updated with NordVPN UI

${BOLD}${YELLOW}Quick Commands:${NC}

  ${CYAN}bash apply_nordvpn.sh --list-countries${NC}
  ${CYAN}bash apply_nordvpn.sh --list-servers JP${NC}
  ${CYAN}bash apply_nordvpn.sh -i 1 -c JP${NC}
  ${CYAN}bash test_nordvpn.sh${NC}

EOF

echo -e "\n${GREEN}${BOLD}Demo Complete! 🎉${NC}\n"
print_info "To start using NordVPN integration:"
echo -e "  1. ${CYAN}bash start_webui.sh${NC}  - Start Web UI"
echo -e "  2. Open ${CYAN}http://localhost:5000${NC}"
echo -e "  3. Or use ${CYAN}bash apply_nordvpn.sh --help${NC}\n"

