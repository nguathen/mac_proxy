#!/usr/bin/env bash
# simple_gost.sh - Simple gost startup script

set -euo pipefail

LOG_DIR="./logs"
mkdir -p "$LOG_DIR"

echo "🚀 Starting simple gost instances..."

# Start gost instances
for i in {1..7}; do
    port=$((18180 + i))
    pid_file="$LOG_DIR/gost${i}.pid"
    log_file="$LOG_DIR/gost${i}.log"
    
    echo "Starting gost $i on port $port..."
    
    # Kill any existing process on this port
    lsof -ti :$port 2>/dev/null | xargs kill -9 2>/dev/null || true
    
    # Start gost
    nohup gost -L socks5://:$port -F "https://user:pass@az-01.protonvpn.net:4465" > "$log_file" 2>&1 &
    echo $! > "$pid_file"
    
    echo "✅ Gost $i started (PID: $!, port: $port)"
    sleep 1
done

echo "✅ All gost instances started!"
