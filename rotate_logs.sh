#!/usr/bin/env bash
# rotate_logs.sh
# Rotate logs để tránh đầy disk

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="./logs"
MAX_SIZE_MB=50  # Rotate khi file > 50MB
KEEP_BACKUPS=3  # Giữ 3 backup

echo "🔄 Rotating logs..."

for log_file in "$LOG_DIR"/*.log; do
    [ -f "$log_file" ] || continue
    
    # Get file size in MB
    size_mb=$(du -m "$log_file" | cut -f1)
    
    if (( size_mb > MAX_SIZE_MB )); then
        echo "📦 Rotating $log_file (${size_mb}MB)"
        
        # Remove oldest backup
        [ -f "${log_file}.${KEEP_BACKUPS}" ] && rm -f "${log_file}.${KEEP_BACKUPS}"
        
        # Shift backups
        for i in $(seq $((KEEP_BACKUPS - 1)) -1 1); do
            [ -f "${log_file}.$i" ] && mv "${log_file}.$i" "${log_file}.$((i + 1))"
        done
        
        # Rotate current log
        mv "$log_file" "${log_file}.1"
        touch "$log_file"
        
        echo "  ✅ Rotated to ${log_file}.1"
    fi
done

echo "✅ Log rotation complete"

