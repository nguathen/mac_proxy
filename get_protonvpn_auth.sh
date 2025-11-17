#!/usr/bin/env bash
# get_protonvpn_auth.sh
# Script để lấy ProtonVPN auth password từ protonvpn_service

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function để lấy auth password từ protonvpn_service
get_protonvpn_auth() {
    # Sử dụng Python để lấy password từ protonvpn_service.Instance.password
    local password=$(python3 -c "
import sys
import os
sys.path.insert(0, '$SCRIPT_DIR')
try:
    from protonvpn_service import Instance
    if Instance.password:
        print(Instance.password)
    else:
        print('', end='')
except Exception as e:
    print('', end='')
" 2>/dev/null)
    
    if [ -n "$password" ]; then
        echo "$password"
        return 0
    else
        echo ""
        return 1
    fi
}

# Call the function
get_protonvpn_auth