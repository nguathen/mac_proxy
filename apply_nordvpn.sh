#!/usr/bin/env bash
# apply_nordvpn.sh
# Script helper để áp dụng NordVPN server vào wireproxy

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}ℹ${NC} $*"; }
log_success() { echo -e "${GREEN}✓${NC} $*"; }
log_warning() { echo -e "${YELLOW}⚠${NC} $*"; }
log_error() { echo -e "${RED}✗${NC} $*"; }

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Apply NordVPN server to wireproxy instance

OPTIONS:
    -i, --instance <1|2>    Wireproxy instance (required)
    -s, --server <name>     Server name (e.g., "Japan #720")
    -c, --country <code>    Country code (will use best server)
    -l, --list-countries    List all countries
    -L, --list-servers <country>  List servers by country
    -h, --help              Show this help

EXAMPLES:
    # List countries
    $0 --list-countries
    
    # List servers in Japan
    $0 --list-servers JP
    
    # Apply specific server to instance 1
    $0 --instance 1 --server "Japan #720"
    
    # Apply best server in US to instance 2
    $0 --instance 2 --country US

EOF
}

# Parse arguments
INSTANCE=""
SERVER=""
COUNTRY=""
LIST_COUNTRIES=false
LIST_SERVERS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--instance)
            INSTANCE="$2"
            shift 2
            ;;
        -s|--server)
            SERVER="$2"
            shift 2
            ;;
        -c|--country)
            COUNTRY="$2"
            shift 2
            ;;
        -l|--list-countries)
            LIST_COUNTRIES=true
            shift
            ;;
        -L|--list-servers)
            LIST_SERVERS="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# List countries
if [ "$LIST_COUNTRIES" = true ]; then
    python3 nordvpn_cli.py countries
    exit 0
fi

# List servers
if [ -n "$LIST_SERVERS" ]; then
    python3 nordvpn_cli.py servers --country "$LIST_SERVERS" --limit 50
    exit 0
fi

# Validate instance
if [ -z "$INSTANCE" ]; then
    log_error "Instance is required"
    show_usage
    exit 1
fi

if [ "$INSTANCE" != "1" ] && [ "$INSTANCE" != "2" ]; then
    log_error "Instance must be 1 or 2"
    exit 1
fi

# Get server name
if [ -n "$SERVER" ]; then
    SERVER_NAME="$SERVER"
elif [ -n "$COUNTRY" ]; then
    log_info "Finding best server in $COUNTRY..."
    SERVER_INFO=$(python3 nordvpn_cli.py best --country "$COUNTRY")
    SERVER_NAME=$(echo "$SERVER_INFO" | grep "Name:" | cut -d: -f2- | xargs)
    
    if [ -z "$SERVER_NAME" ]; then
        log_error "No server found in $COUNTRY"
        exit 1
    fi
    
    log_success "Found best server: $SERVER_NAME"
else
    log_error "Either --server or --country must be specified"
    show_usage
    exit 1
fi

# Apply server
log_info "Applying server '$SERVER_NAME' to Wireproxy $INSTANCE..."

python3 nordvpn_cli.py apply "$INSTANCE" --server "$SERVER_NAME"

if [ $? -eq 0 ]; then
    log_success "Config updated successfully"
    
    # Ask to restart
    echo ""
    read -p "Restart Wireproxy $INSTANCE now? (y/n) " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Restarting Wireproxy $INSTANCE..."
        
        # Stop wireproxy instance
        if [ -f "logs/wireproxy${INSTANCE}.pid" ]; then
            PID=$(cat "logs/wireproxy${INSTANCE}.pid")
            if kill -0 "$PID" 2>/dev/null; then
                kill "$PID" 2>/dev/null || true
                rm -f "logs/wireproxy${INSTANCE}.pid"
                log_success "Stopped Wireproxy $INSTANCE"
            fi
        fi
        
        # Kill any process on the port
        PORT="1818${INSTANCE}"
        lsof -ti ":$PORT" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
        
        sleep 1
        
        # Start wireproxy
        CONFIG_FILE="wg1818${INSTANCE}.conf"
        LOG_FILE="logs/wireproxy${INSTANCE}.log"
        
        nohup ./wireproxy -c "$CONFIG_FILE" > "$LOG_FILE" 2>&1 &
        NEW_PID=$!
        echo "$NEW_PID" > "logs/wireproxy${INSTANCE}.pid"
        
        log_success "Started Wireproxy $INSTANCE (PID: $NEW_PID)"
        
        # Wait a bit and test
        sleep 2
        
        log_info "Testing proxy connection..."
        if timeout 5 curl -s --max-time 3 -x "socks5h://127.0.0.1:$PORT" https://api.ipify.org &>/dev/null; then
            IP=$(curl -s --max-time 3 -x "socks5h://127.0.0.1:$PORT" https://api.ipify.org)
            log_success "Proxy is working! IP: $IP"
        else
            log_warning "Proxy test failed. Check logs: tail -f $LOG_FILE"
        fi
    else
        log_info "Skipped restart. Run 'bash manage_wireproxy.sh restart' to apply changes."
    fi
else
    log_error "Failed to apply server"
    exit 1
fi

