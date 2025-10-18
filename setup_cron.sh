#!/usr/bin/env bash
# setup_cron.sh
# Setup cron job để rotate logs hàng ngày

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "⏰ Setting up cron job for log rotation..."

# Create cron job
CRON_CMD="0 3 * * * cd $SCRIPT_DIR && bash rotate_logs.sh >> logs/cron.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "rotate_logs.sh"; then
    echo "⚠️  Cron job already exists"
else
    # Add cron job
    (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
    echo "✅ Cron job added: Daily log rotation at 3 AM"
fi

echo ""
echo "📋 Current cron jobs:"
crontab -l | grep rotate_logs || echo "  (none)"
echo ""
echo "💡 To remove: crontab -e (then delete the line)"

