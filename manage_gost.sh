#!/usr/bin/env bash
# manage_gost.sh
# Quản lý gost services thay thế wireproxy

set -euo pipefail

GOST_BIN="gost"
LOG_DIR="./logs"
PID_DIR="./logs"
CONFIG_DIR="./config"

mkdir -p "$LOG_DIR"

timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(timestamp)] $*"; }

# Gost ports được quản lý động dựa trên config files

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
            # Ưu tiên lấy label khác "0" nếu có, nếu không thì lấy label đầu tiên
            local server_label=$(grep -A 5 "\"domain\": \"$country\"" /Volumes/Ssd/Projects/mac_proxy/protonvpn_servers_cache.json | grep '"label": "[^0]' | head -1 | cut -d'"' -f4)
            if [ -z "$server_label" ]; then
                # Fallback: lấy label đầu tiên
                server_label=$(grep -A 5 "\"domain\": \"$country\"" /Volumes/Ssd/Projects/mac_proxy/protonvpn_servers_cache.json | grep '"label":' | head -1 | cut -d'"' -f4)
            fi
            if [ -z "$server_label" ]; then
                # Fallback: tìm số trong country name
                server_label=$(echo "$country" | grep -o '[0-9]\+' | head -1)
            fi
            if [ -z "$server_label" ]; then
                # Final fallback: default to 0
                server_label=0
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

# Lưu cấu hình proxy cho port
save_proxy_config() {
    local port=$1
    local provider=$2
    local country=$3
    local proxy_url=$4
    
    local config_file="$CONFIG_DIR/gost_${port}.config"
    cat > "$config_file" <<EOF
{
    "port": "$port",
    "provider": "$provider",
    "country": "$country",
    "proxy_url": "$proxy_url",
    "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
    log "💾 Saved config for gost port $port: $provider ($country)"
}

# Đọc cấu hình proxy cho port
load_proxy_config() {
    local port=$1
    local config_file="$CONFIG_DIR/gost_${port}.config"
    
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
    log "🚀 Starting gost services..."
    
    # Cập nhật ProtonVPN credentials trước khi start
    update_protonvpn_credentials
    
    # Start services dựa trên config files có sẵn
    for config_file in "$CONFIG_DIR"/gost_*.config; do
        if [ -f "$config_file" ]; then
            local port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
            
            # Check and kill any process using this port
            check_and_kill_port "$port" "Gost on port $port"
            
            # Start gost service
            local pid_file="$PID_DIR/gost_${port}.pid"
            
            if [ -f "$pid_file" ] && kill -0 $(cat "$pid_file") 2>/dev/null; then
                log "⚠️  Gost on port $port already running"
            else
                # Đọc cấu hình đã lưu
                local config_json=$(load_proxy_config $port)
                local proxy_url=""
                local provider=""
                local country=""
                
                # Parse JSON config using jq
                if [ "$config_json" != "{}" ]; then
                    proxy_url=$(echo "$config_json" | jq -r '.proxy_url // ""' 2>/dev/null || echo "")
                    provider=$(echo "$config_json" | jq -r '.provider // ""' 2>/dev/null || echo "")
                    country=$(echo "$config_json" | jq -r '.country // ""' 2>/dev/null || echo "")
                fi
                
                # Nếu không có config hoặc config rỗng, skip port này
                if [ -z "$proxy_url" ] || [ "$proxy_url" = "null" ]; then
                    log "⚠️  No config for port $port, skipping..."
                    continue
                fi
                
                # Khởi động gost với socks5 proxy
                nohup $GOST_BIN -L socks5://:$port -F "$proxy_url" > "$LOG_DIR/gost_${port}.log" 2>&1 &
                local pid=$!
                echo $pid > "$pid_file"
                log "✅ Gost on port $port started (PID: $pid, proxy: $proxy_url)"
            fi
        fi
    done
    
    sleep 2
    status_gost
}

stop_gost() {
    log "🛑 Stopping gost services..."
    
    local stopped_any=false
    
    # Stop all gost services
    for pid_file in "$PID_DIR"/gost_*.pid; do
        if [ -f "$pid_file" ]; then
            local port=$(basename "$pid_file" | sed 's/gost_\(.*\)\.pid/\1/')
            pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null && log "✅ Stopped gost on port $port (PID: $pid)"
                stopped_any=true
            else
                log "⚠️  Gost on port $port not running (stale PID)"
            fi
            rm -f "$pid_file"
        fi
    done
    
    if [ "$stopped_any" = false ] && [ ! -f "$PID_DIR"/gost_*.pid ]; then
        log "⚠️  No gost services running"
    fi
    
    # Cleanup any remaining gost processes on detected ports
    log "🧹 Cleaning up any remaining processes on ports..."
    
    # Cleanup based on config files
    for config_file in "$CONFIG_DIR"/gost_*.config; do
        if [ -f "$config_file" ]; then
            local port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
            if command -v lsof &> /dev/null; then
                lsof -ti ":$port" 2>/dev/null | xargs kill -9 2>/dev/null || true
            fi
        fi
    done
    
    # Also try to kill by process name pattern
    pkill -9 -f "gost.*socks5" 2>/dev/null || true
    
    log "✅ Cleanup complete"
}

restart_gost() {
    log "♻️  Restarting gost services..."
    stop_gost
    sleep 2
    start_gost
}

# Restart specific gost service by port
restart_gost_port() {
    local port=$1
    if [ -z "$port" ] || ! [[ "$port" =~ ^[0-9]+$ ]]; then
        log "❌ Invalid port format. Must be a number"
        return 1
    fi
    
    log "♻️  Restarting gost on port $port..."
    
    # Stop specific service
    local pid_file="$PID_DIR/gost_${port}.pid"
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null && log "✅ Stopped gost on port $port (PID: $pid)"
        else
            log "⚠️  Gost on port $port not running (stale PID)"
        fi
        rm -f "$pid_file"
    else
        log "⚠️  Gost on port $port not running"
    fi
    
    # Cleanup port
    if command -v lsof &> /dev/null; then
        local pid_on_port=$(lsof -ti:$port 2>/dev/null)
        if [ -n "$pid_on_port" ]; then
            kill "$pid_on_port" 2>/dev/null && log "🧹 Cleaned up process on port $port"
        fi
    fi
    
    sleep 1
    
    # Check and kill any process using this port
    check_and_kill_port "$port" "Gost on port $port"
    
    # Start gost service
    local pid_file="$PID_DIR/gost_${port}.pid"
    
    if [ -f "$pid_file" ] && kill -0 $(cat "$pid_file") 2>/dev/null; then
        log "⚠️  Gost on port $port already running"
    else
        # Đọc cấu hình đã lưu
        local config_json=$(load_proxy_config $port)
        local proxy_url=""
        local provider=""
        local country=""
        
        # Parse JSON config using jq
        if [ "$config_json" != "{}" ]; then
            proxy_url=$(echo "$config_json" | jq -r '.proxy_url // ""' 2>/dev/null || echo "")
            provider=$(echo "$config_json" | jq -r '.provider // ""' 2>/dev/null || echo "")
            country=$(echo "$config_json" | jq -r '.country // ""' 2>/dev/null || echo "")
        fi
        
        # Nếu không có config hoặc config rỗng, skip port này
        if [ -z "$proxy_url" ] || [ "$proxy_url" = "null" ]; then
            log "⚠️  No config for port $port, skipping..."
            return 0
        fi
        
        # Khởi động gost với socks5 proxy
        nohup $GOST_BIN -L socks5://:$port -F "$proxy_url" > "$LOG_DIR/gost_${port}.log" 2>&1 &
        local pid=$!
        echo $pid > "$pid_file"
        log "✅ Gost on port $port started (PID: $pid, proxy: $proxy_url)"
    fi
}

status_gost() {
    log "📊 Gost Status:"
    
    local any_running=false
    
    # Hiển thị status dựa trên PID files có sẵn
    for pid_file in "$PID_DIR"/gost_*.pid; do
        if [ -f "$pid_file" ]; then
            local port=$(basename "$pid_file" | sed 's/gost_\(.*\)\.pid/\1/')
            pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                log "  ✅ Port $port: Running (PID: $pid)"
                any_running=true
                
                # Test connection
                if timeout 15 bash -c "curl -s --max-time 10 -x socks5h://127.0.0.1:$port https://api.ipify.org" &>/dev/null; then
                    log "     🌐 Connection: OK"
                else
                    log "     ⚠️  Connection: Failed (may need more time to establish)"
                fi
            else
                log "  ❌ Port $port: Not running"
            fi
        fi
    done
    
    if [ "$any_running" = false ]; then
        log "  ⚠️  No gost services are running"
    fi
}

# Cấu hình proxy cho port
configure_gost() {
    local port=$1
    local provider=$2
    local country=$3
    
    # Validate port format (should be a number)
    if ! [[ "$port" =~ ^[0-9]+$ ]]; then
        log "❌ Invalid port format. Must be a number"
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
    save_proxy_config $port "$provider" "$country" "$proxy_url"
    log "✅ Configured gost port $port: $provider ($country)"
}

# Hiển thị cấu hình
show_config() {
    local port=$1
    
    if [ -n "$port" ]; then
        # Validate port format (should be a number)
        if ! [[ "$port" =~ ^[0-9]+$ ]]; then
            log "❌ Invalid port format. Must be a number"
            return 1
        fi
        
        local config_json=$(load_proxy_config $port)
        if [ "$config_json" != "{}" ]; then
            echo "$config_json" | python3 -m json.tool 2>/dev/null || echo "$config_json"
        else
            log "❌ No config found for gost port $port"
        fi
    else
        # Hiển thị tất cả configs dựa trên files có sẵn
        log "📋 Gost Configurations:"
        local found_any=false
        
        # Tìm tất cả config files
        for config_file in "$CONFIG_DIR"/gost_*.config; do
            if [ -f "$config_file" ]; then
                local port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
                local config_json=$(cat "$config_file")
                if [ "$config_json" != "{}" ]; then
                local provider=$(echo "$config_json" | jq -r '.provider // ""' 2>/dev/null || echo "")
                local country=$(echo "$config_json" | jq -r '.country // ""' 2>/dev/null || echo "")
                local proxy_url=$(echo "$config_json" | jq -r '.proxy_url // ""' 2>/dev/null || echo "")
                    log "  Port $port: $provider ($country) - $proxy_url"
                    found_any=true
                fi
            fi
        done
        
        if [ "$found_any" = false ]; then
            log "  No configurations found"
        fi
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
    restart-instance)
        if [ $# -lt 2 ]; then
            echo "Usage: $0 restart-instance <port>"
            echo "  port: 18181-18187"
            exit 1
        fi
        restart_gost_port "$2"
        ;;
    restart-port)
        if [ $# -lt 2 ]; then
            echo "Usage: $0 restart-port <port>"
            echo "  port: 18181-18187"
            exit 1
        fi
        restart_gost_port "$2"
        ;;
    status)
        status_gost
        ;;
    config)
        if [ $# -lt 4 ]; then
            echo "Usage: $0 config <port> <provider> <country>"
            echo "  port: 18181-18187"
            echo "  provider: nordvpn, protonvpn"
            echo "  country: server identifier"
            exit 1
        fi
        configure_gost "$2" "$3" "$4"
        ;;
    show-config)
        show_config "${2:-}"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|restart-instance|restart-port|status|config|show-config}"
        echo ""
        echo "Commands:"
        echo "  start                    - Start all gost services"
        echo "  stop                     - Stop all gost services"
        echo "  restart                  - Restart all gost services"
        echo "  restart-instance <p>     - Restart specific gost service on port p"
        echo "  restart-port <p>         - Restart gost on specific port p"
        echo "  status                   - Show status of all services"
        echo "  config <p> <pr> <c>      - Configure port p with provider pr and country c"
        echo "  show-config [p]           - Show configuration for port p (or all)"
        echo ""
        echo "Examples:"
        echo "  $0 config 18181 protonvpn node-uk-29.protonvpn.net"
        echo "  $0 config 18182 nordvpn us"
        echo "  $0 restart-instance 18182"
        echo "  $0 restart-port 18182"
        echo "  $0 show-config 18181"
        echo "  $0 show-config"
        exit 1
        ;;
esac
