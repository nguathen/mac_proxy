#!/usr/bin/env bash
# get_protonvpn_auth.sh
# Script để lấy ProtonVPN auth password từ protonvpn_service

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function để lấy auth password từ protonvpn_service
get_protonvpn_auth() {
    # Sử dụng Python để lấy password từ protonvpn_service.Instance.password
    # Ensure we're in the right directory and can import the module
    # Remove old .pyc files that might contain hardcoded paths
    cd "$SCRIPT_DIR" && find . -name "*.pyc" -delete 2>/dev/null
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    
    local password=$(cd "$SCRIPT_DIR" && python3 -B -c "
import sys
import os

# Add script directory to path
script_dir = '$SCRIPT_DIR'
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

try:
    from protonvpn_service import Instance
    Instance.load()
    if Instance and hasattr(Instance, 'user_name') and hasattr(Instance, 'password'):
        if Instance.user_name and Instance.password:
            print(f'{Instance.user_name}:{Instance.password}')
        else:
            print('', end='')
    else:
        print('', end='')
except Exception as e:
    # Print error to stderr for debugging
    import sys
    import traceback
    print(f'Error: {e}', file=sys.stderr)
    print(traceback.format_exc(), file=sys.stderr)
    print('', end='')
" 2>&1)
    
    # Extract password (everything before any error messages)
    password=$(echo "$password" | grep -v "^Error:" | head -n 1)
    
    if [ -n "$password" ] && [ "$password" != "" ]; then
        echo "$password"
        return 0
    else
        echo ""
        return 1
    fi
}

# Call the function
get_protonvpn_auth