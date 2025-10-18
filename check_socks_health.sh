#!/usr/bin/env bash
# check_socks_health.sh
# Health check script for SOCKS proxy - kiểm tra thực tế proxy có hoạt động không

set -euo pipefail

PORT="${1:-18181}"

# Test SOCKS proxy bằng cách connect đến endpoint đơn giản
# Nếu proxy không hoạt động (WireGuard tunnel down), sẽ fail
if timeout 2 curl -s --max-time 1.5 -x "socks5h://127.0.0.1:$PORT" https://1.1.1.1 >/dev/null 2>&1; then
    exit 0  # Success - proxy hoạt động
else
    exit 1  # Failure - proxy không hoạt động (có thể port đang listen nhưng tunnel down)
fi

