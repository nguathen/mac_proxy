#!/usr/bin/env bash
# kill_all_processes.sh
# Kill tất cả các process liên quan đến mac_proxy (kể cả khi thư mục đã bị xóa)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🛑 Killing All Mac Proxy Processes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 1. Kill Web UI (Flask app.py)
echo "📌 Killing Web UI (Flask app.py)..."
pkill -9 -f "python.*app.py" 2>/dev/null || true
pkill -9 -f "flask.*run" 2>/dev/null || true
# Kill process on port 5000
if command -v lsof &> /dev/null; then
    lsof -ti :5000 2>/dev/null | xargs kill -9 2>/dev/null || true
elif command -v fuser &> /dev/null; then
    fuser -k 5000/tcp 2>/dev/null || true
elif command -v ss &> /dev/null; then
    ss -lptn 'sport = :5000' | grep -oP 'pid=\K[0-9]+' | xargs kill -9 2>/dev/null || true
fi
echo "✅ Web UI killed"

# 2. Kill Auto Credential Updater
echo ""
echo "📌 Killing Auto Credential Updater..."
pkill -9 -f "auto_credential_updater" 2>/dev/null || true
pkill -9 -f "python.*auto_credential_updater.py" 2>/dev/null || true
echo "✅ Auto Credential Updater killed"

# 3. Kill Gost processes
echo ""
echo "📌 Killing Gost processes..."
pkill -9 -f "gost.*socks5" 2>/dev/null || true
pkill -9 -f "gost -L" 2>/dev/null || true
pkill -9 gost 2>/dev/null || true
echo "✅ Gost processes killed"

# 4. Kill Gost Monitor
echo ""
echo "📌 Killing Gost Monitor..."
pkill -9 -f "gost_monitor.sh" 2>/dev/null || true
pkill -9 -f "bash.*gost_monitor" 2>/dev/null || true
echo "✅ Gost Monitor killed"

# 5. Kill WARP Monitor
echo ""
echo "📌 Killing WARP Monitor..."
pkill -9 -f "warp_monitor.sh" 2>/dev/null || true
pkill -9 -f "bash.*warp_monitor" 2>/dev/null || true
echo "✅ WARP Monitor killed"

# 6. Kill any remaining processes on common ports
echo ""
echo "📌 Cleaning up ports 7891-7999..."
for port in {7891..7999}; do
    if command -v lsof &> /dev/null; then
        lsof -ti :$port 2>/dev/null | xargs kill -9 2>/dev/null || true
    elif command -v fuser &> /dev/null; then
        fuser -k ${port}/tcp 2>/dev/null || true
    fi
done
echo "✅ Ports cleaned"

# 9. Wait a moment
sleep 1

# 10. Verify
echo ""
echo "🔍 Verifying..."
REMAINING=false

if pgrep -f "python.*app.py" > /dev/null 2>&1; then
    echo "⚠️  Web UI processes still running"
    REMAINING=true
fi

if pgrep -f "gost" > /dev/null 2>&1; then
    echo "⚠️  Gost processes still running"
    REMAINING=true
fi

if pgrep -f "auto_credential_updater" > /dev/null 2>&1; then
    echo "⚠️  Auto Credential Updater still running"
    REMAINING=true
fi

if pgrep -f "monitor" > /dev/null 2>&1; then
    echo "⚠️  Monitor processes still running"
    REMAINING=true
fi

if [ "$REMAINING" = true ]; then
    echo ""
    echo "💡 Some processes may still be running. Try:"
    echo "   ps aux | grep -E 'gost|app.py|monitor|auto_credential'"
    echo "   kill -9 <PID>"
else
    echo "✅ All processes killed successfully"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Kill operation completed"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 To check remaining processes:"
echo "   ps aux | grep -E 'gost|app.py|monitor|auto_credential'"
echo ""

