#!/usr/bin/env bash
# manage_gost.sh
# Quản lý gost instances thay thế wireproxy

set -euo pipefail

GOST_BIN="gost"
LOG_DIR="./logs"
PID_DIR="./logs"

mkdir -p "$LOG_DIR"

timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(timestamp)] $*"; }

# Cấu hình gost instances
declare -A GOST_INSTANCES=(
    ["1"]="18181"
    ["2"]="18182" 
    ["3"]="18183"
    ["4"]="18184"
    ["5"]="18185"
    ["6"]="18186"
    ["7"]="18187"
)

# Lấy thông tin proxy từ API
get_proxy_info() {
    local provider=$1
    local country=$2
    
    if [ "$provider" = "nordvpn" ]; then
        # Format: https://user:pass@hostname:port
        echo "https://USMbUonbFpF9xEx8xR3MHSau:buKKKPURZNMTW7A6rwm3qtBn@${country}:89"
    elif [ "$provider" = "protonvpn" ]; then
        # Gọi API để lấy user:pass
        local api_response=$(curl -s "http://localhost:5267/mmo/getpassproxy" 2>/dev/null || echo "")
        if [ -n "$api_response" ]; then
            # Tính port từ server label + 4443
            # Tìm server trong cache để lấy label chính xác
            # Ưu tiên lấy label "6" nếu có, nếu không thì lấy label đầu tiên
            local server_label=$(grep -A 5 "\"domain\": \"$country\"" /Volumes/Ssd/Projects/mac_proxy/protonvpn_servers_cache.json | grep '"label": "6"' | head -1 | cut -d'"' -f4)
            if [ -z "$server_label" ]; then
                # Fallback: lấy label đầu tiên
                server_label=$(grep -A 5 "\"domain\": \"$country\"" /Volumes/Ssd/Projects/mac_proxy/protonvpn_servers_cache.json | grep '"label":' | head -1 | cut -d'"' -f4)
            fi
            if [ -z "$server_label" ]; then
                # Fallback: tìm số trong country name
                server_label=$(echo "$country" | grep -o '[0-9]\+' | head -1)
            fi
            local port=$((server_label + 4443))
            echo "https://${api_response}@${country}:${port}"
        else
            echo ""
        fi
    else
        echo ""
    fi
}

# Lưu cấu hình proxy cho instance
save_proxy_config() {
    local instance=$1
    local provider=$2
    local country=$3
    local proxy_url=$4
    
    # Trích xuất port từ proxy_url
    local port=$(echo "$proxy_url" | sed 's/.*:\([0-9]*\)$/\1/')
    
    local config_file="$LOG_DIR/gost${instance}.config"
    cat > "$config_file" <<EOF
{
    "instance": $instance,
    "provider": "$provider",
    "country": "$country",
    "proxy_url": "$proxy_url",
    "port": "$port",
    "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
    log "💾 Saved config for gost $instance: $provider ($country)"
}

# Đọc cấu hình proxy cho instance
load_proxy_config() {
    local instance=$1
    local config_file="$LOG_DIR/gost${instance}.config"
    
    if [ -f "$config_file" ]; then
        cat "$config_file"
    else
        echo "{}"
    fi
}

# Cập nhật proxy URL cho ProtonVPN
update_protonvpn_credentials() {
    log "🔄 Updating ProtonVPN credentials..."
    local api_response=$(curl -s "http://localhost:5267/mmo/getpassproxy" 2>/dev/null || echo "")
    if [ -n "$api_response" ]; then
        log "✅ ProtonVPN credentials updated"
    else
        log "⚠️  Failed to update ProtonVPN credentials (API not available)"
    fi
    return 0  # Always return success to continue
}

check_and_kill_port() {
    local port=$1
    local service_name=$2
    
    log "🔍 Checking port $port..."
    
    # Tìm process đang sử dụng port (macOS/Linux compatible)
    local pids=""
    
    # Try lsof first (macOS/Linux)
    if command -v lsof &> /dev/null; then
        pids=$(lsof -ti :$port 2>/dev/null || echo "")
    fi
    
    # Try netstat if lsof not available (Linux)
    if [ -z "$pids" ] && command -v netstat &> /dev/null; then
        pids=$(netstat -tlnp 2>/dev/null | grep ":$port " | awk '{print $7}' | cut -d'/' -f1 || echo "")
    fi
    
    # Try ss if available (Linux)
    if [ -z "$pids" ] && command -v ss &> /dev/null; then
        pids=$(ss -tlnp 2>/dev/null | grep ":$port " | grep -oP 'pid=\K[0-9]+' || echo "")
    fi
    
    if [ -n "$pids" ]; then
        for pid in $pids; do
            if [ -n "$pid" ] && [ "$pid" != "0" ]; then
                # Get process name
                local proc_name=$(ps -p $pid -o comm= 2>/dev/null || echo "unknown")
                log "⚠️  Found process on port $port: $proc_name (PID: $pid)"
                
                # Kill the process
                if kill -9 $pid 2>/dev/null; then
                    log "✅ Killed process $pid on port $port"
                else
                    log "❌ Failed to kill process $pid (may need sudo)"
                fi
            fi
        done
        sleep 1
    else
        log "✅ Port $port is free"
    fi
}

start_gost() {
    log "🚀 Starting gost instances..."
    
    # Cập nhật ProtonVPN credentials trước khi start
    update_protonvpn_credentials
    
    local instance=1
    for port in 18181 18182 18183 18184 18185 18186 18187; do
        # Check and kill any process using this port
        check_and_kill_port "$port" "Gost $instance"
        
        # Start gost instance
        local pid_file="$PID_DIR/gost${instance}.pid"
        
        if [ -f "$pid_file" ] && kill -0 $(cat "$pid_file") 2>/dev/null; then
            log "⚠️  Gost $instance already running"
        else
            # Đọc cấu hình đã lưu
            local config_json=$(load_proxy_config $instance)
            local proxy_url=""
            local provider=""
            local country=""
            
            # Parse JSON config using jq
            if [ "$config_json" != "{}" ]; then
                proxy_url=$(echo "$config_json" | jq -r '.proxy_url // ""' 2>/dev/null || echo "")
                provider=$(echo "$config_json" | jq -r '.provider // ""' 2>/dev/null || echo "")
                country=$(echo "$config_json" | jq -r '.country // ""' 2>/dev/null || echo "")
            fi
            
            # Nếu không có config hoặc config rỗng, skip instance này
            if [ -z "$proxy_url" ] || [ "$proxy_url" = "null" ]; then
                log "⚠️  No config for instance $instance, skipping..."
                ((instance++))
                continue
            fi
            
            # Khởi động gost với socks5 proxy
            nohup $GOST_BIN -L socks5://:$port -F "$proxy_url" > "$LOG_DIR/gost${instance}.log" 2>&1 &
            local pid=$!
            echo $pid > "$pid_file"
            log "✅ Gost $instance started (PID: $pid, port $port, proxy: $proxy_url)"
        fi
        
        ((instance++))
    done
    
    sleep 2
    status_gost
}

stop_gost() {
    log "🛑 Stopping gost instances..."
    
    local instance=1
    local stopped_any=false
    
    # Stop all gost instances
    for pid_file in "$PID_DIR"/gost*.pid; do
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null && log "✅ Stopped gost $instance (PID: $pid)"
                stopped_any=true
            else
                log "⚠️  Gost $instance not running (stale PID)"
            fi
            rm -f "$pid_file"
            ((instance++))
        fi
    done
    
    if [ "$stopped_any" = false ] && [ ! -f "$PID_DIR"/gost*.pid ]; then
        log "⚠️  No gost instances running"
    fi
    
    # Cleanup any remaining gost processes on detected ports
    log "🧹 Cleaning up any remaining processes on ports..."
    
    for port in "${GOST_INSTANCES[@]}"; do
        if command -v lsof &> /dev/null; then
            lsof -ti ":$port" 2>/dev/null | xargs kill -9 2>/dev/null || true
        fi
    done
    
    # Also try to kill by process name pattern
    pkill -9 -f "gost.*socks5" 2>/dev/null || true
    
    log "✅ Cleanup complete"
}

restart_gost() {
    log "♻️  Restarting gost instances..."
    stop_gost
    sleep 2
    start_gost
}

status_gost() {
    log "📊 Gost Status:"
    
    local instance=1
    local any_running=false
    
    for port in "${GOST_INSTANCES[@]}"; do
        local pid_file="$PID_DIR/gost${instance}.pid"
        
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                log "  ✅ Gost $instance (port $port): Running (PID: $pid)"
                any_running=true
                
                # Test connection
                if timeout 15 bash -c "curl -s --max-time 10 -x socks5h://127.0.0.1:$port https://api.ipify.org" &>/dev/null; then
                    log "     🌐 Connection: OK"
                else
                    log "     ⚠️  Connection: Failed (may need more time to establish)"
                fi
            else
                log "  ❌ Gost $instance (port $port): Not running"
            fi
        else
            log "  ❌ Gost $instance (port $port): Not running"
        fi
        
        ((instance++))
    done
    
    if [ "$any_running" = false ]; then
        log "  ⚠️  No gost instances are running"
    fi
}

# Cấu hình proxy cho instance
configure_gost() {
    local instance=$1
    local provider=$2
    local country=$3
    
    if [ $instance -lt 1 ] || [ $instance -gt 7 ]; then
        log "❌ Invalid instance. Available: 1-7"
        return 1
    fi
    
    if [ "$provider" != "nordvpn" ] && [ "$provider" != "protonvpn" ]; then
        log "❌ Invalid provider. Available: nordvpn, protonvpn"
        return 1
    fi
    
    # Lấy proxy URL
    local proxy_url=$(get_proxy_info "$provider" "$country")
    if [ -z "$proxy_url" ]; then
        log "❌ Failed to get proxy info for $provider ($country)"
        return 1
    fi
    
    # Lưu cấu hình
    save_proxy_config $instance "$provider" "$country" "$proxy_url"
    log "✅ Configured gost $instance: $provider ($country)"
}

# Hiển thị cấu hình
show_config() {
    local instance=$1
    
    if [ -n "$instance" ]; then
        if [ $instance -lt 1 ] || [ $instance -gt 7 ]; then
            log "❌ Invalid instance. Available: 1-7"
            return 1
        fi
        
        local config_json=$(load_proxy_config $instance)
        if [ "$config_json" != "{}" ]; then
            echo "$config_json" | python3 -m json.tool 2>/dev/null || echo "$config_json"
        else
            log "❌ No config found for gost $instance"
        fi
    else
        # Hiển thị tất cả configs
        log "📋 Gost Configurations:"
        for i in {1..7}; do
            local config_json=$(load_proxy_config $i)
            if [ "$config_json" != "{}" ]; then
                local provider=$(echo "$config_json" | grep -o '"provider":"[^"]*"' | cut -d'"' -f4)
                local country=$(echo "$config_json" | grep -o '"country":"[^"]*"' | cut -d'"' -f4)
                local proxy_url=$(echo "$config_json" | grep -o '"proxy_url":"[^"]*"' | cut -d'"' -f4)
                log "  Instance $i: $provider ($country) - $proxy_url"
            else
                log "  Instance $i: No configuration"
            fi
        done
    fi
}

case "${1:-}" in
    start)
        start_gost
        ;;
    stop)
        stop_gost
        ;;
    restart)
        restart_gost
        ;;
    status)
        status_gost
        ;;
    config)
        if [ $# -lt 4 ]; then
            echo "Usage: $0 config <instance> <provider> <country>"
            echo "  instance: 1-7"
            echo "  provider: nordvpn, protonvpn"
            echo "  country: server identifier"
            exit 1
        fi
        configure_gost "$2" "$3" "$4"
        ;;
    show-config)
        show_config "$2"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|config|show-config}"
        echo ""
        echo "Commands:"
        echo "  start                    - Start all gost instances"
        echo "  stop                     - Stop all gost instances"
        echo "  restart                  - Restart all gost instances"
        echo "  status                   - Show status of all instances"
        echo "  config <i> <p> <c>       - Configure instance i with provider p and country c"
        echo "  show-config [i]          - Show configuration for instance i (or all)"
        echo ""
        echo "Examples:"
        echo "  $0 config 1 protonvpn node-uk-29.protonvpn.net"
        echo "  $0 config 2 nordvpn us"
        echo "  $0 show-config 1"
        echo "  $0 show-config"
        exit 1
        ;;
esac
