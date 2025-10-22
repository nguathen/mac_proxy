#!/usr/bin/env bash
# get_protonvpn_auth.sh
# Script để lấy ProtonVPN auth token

# Function để lấy auth token
get_protonvpn_auth() {
    local api_response=$(curl -s "http://localhost:5267/mmo/getpassproxy" 2>/dev/null || echo "")
    if [ -n "$api_response" ]; then
        echo "$api_response"
        return 0
    else
        echo ""
        return 1
    fi
}

# Call the function
get_protonvpn_auth