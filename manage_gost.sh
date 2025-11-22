#!/usr/bin/env bash
# manage_gost.sh
# Quản lý gost services thay thế wireproxy

set -euo pipefail

# Gost binary path - try bin/gost first, then system gost
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/bin/gost" ]; then
    GOST_BIN="$SCRIPT_DIR/bin/gost"
elif command -v gost &> /dev/null; then
    GOST_BIN="gost"
else
    GOST_BIN="gost"  # Will fail with clear error if not found
fi
LOG_DIR="./logs"
PID_DIR="./logs"
CONFIG_DIR="./config"

mkdir -p "$LOG_DIR"

timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(timestamp)] $*"; }

# Rotate log file nếu quá lớn (max 50MB, giữ 5 files)
rotate_log_if_needed() {
    local log_file=$1
    local max_size_mb=50
    local max_files=5
    
    if [ ! -f "$log_file" ]; then
        return 0
    fi
    
    # Kiểm tra kích thước file (MB)
    local size_mb=$(du -m "$log_file" | cut -f1)
    
    if [ "$size_mb" -ge "$max_size_mb" ]; then
        log "🔄 Rotating log file $log_file (size: ${size_mb}MB)"
        
        # Rotate: gost_7890.log -> gost_7890.log.1, gost_7890.log.1 -> gost_7890.log.2, etc.
        for i in $(seq $((max_files - 1)) -1 1); do
            if [ -f "${log_file}.${i}" ]; then
                mv "${log_file}.${i}" "${log_file}.$((i + 1))" 2>/dev/null || true
            fi
        done
        
        # Move current log to .1
        mv "$log_file" "${log_file}.1" 2>/dev/null || true
        
        # Truncate log file mới
        touch "$log_file"
        log "✅ Log rotated: ${log_file}.1 created"
    fi
}

# Cleanup old log files (giữ tối đa max_files)
cleanup_old_logs() {
    local log_file=$1
    local max_files=5
    
    # Xóa các log files cũ hơn max_files
    for i in $(seq $((max_files + 1)) 20); do
        if [ -f "${log_file}.${i}" ]; then
            rm -f "${log_file}.${i}"
        fi
    done
}

# Gost ports được quản lý động dựa trên config files

# Lấy thông tin proxy từ API
get_proxy_info() {
    local provider=$1
    local country=$2
    local proxy_host=$3
    local proxy_port=$4
    
    if [ "$provider" = "nordvpn" ]; then
        # Format: https://user:pass@proxy_host:proxy_port
        echo "https://USMbUonbFpF9xEx8xR3MHSau:buKKKPURZNMTW7A6rwm3qtBn@${proxy_host}:${proxy_port}"
    elif [ "$provider" = "protonvpn" ]; then
        # Lấy auth token từ function riêng
        local auth_token=$(get_protonvpn_auth)
        if [ -n "$auth_token" ]; then
            # Sử dụng proxy_host và proxy_port trực tiếp
            echo "https://${auth_token}@${proxy_host}:${proxy_port}"
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
    local proxy_host=$5
    local proxy_port=$6
    
    local config_file="$CONFIG_DIR/gost_${port}.config"
    cat > "$config_file" <<EOF
{
    "port": "$port",
    "provider": "$provider",
    "country": "$country",
    "proxy_url": "$proxy_url",
    "proxy_host": "$proxy_host",
    "proxy_port": "$proxy_port",
    "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
    log "💾 Saved config for gost port $port: $provider ($country) - $proxy_host:$proxy_port"
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

# Lấy auth token cho ProtonVPN (sử dụng script riêng)
get_protonvpn_auth() {
    local script_dir="$(dirname "$0")"
    local auth_token=$("$script_dir/get_protonvpn_auth.sh" 2>/dev/null || echo "")
    if [ -n "$auth_token" ]; then
        echo "$auth_token"
        return 0
    else
        echo ""
        return 1
    fi
}


# Cập nhật auth cho tất cả ProtonVPN services
update_all_protonvpn_auth() {
    log "🔄 Updating auth for all ProtonVPN services..."
    
    local auth_token=$(get_protonvpn_auth)
    if [ -z "$auth_token" ]; then
        log "❌ Failed to get ProtonVPN auth token"
        return 1
    fi
    
    local updated_count=0
    
    # Tìm tất cả ProtonVPN config files
    for config_file in "$CONFIG_DIR"/gost_*.config; do
        if [ -f "$config_file" ]; then
            local provider=$(cat "$config_file" | jq -r '.provider // ""' 2>/dev/null || echo "")
            if [ "$provider" = "protonvpn" ]; then
                local port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
                local country=$(cat "$config_file" | jq -r '.country // ""' 2>/dev/null || echo "")
                local proxy_host=$(cat "$config_file" | jq -r '.proxy_host // ""' 2>/dev/null || echo "")
                local proxy_port=$(cat "$config_file" | jq -r '.proxy_port // ""' 2>/dev/null || echo "")
                
                if [ -n "$proxy_host" ] && [ -n "$proxy_port" ]; then
                    # Tạo proxy URL mới với auth token mới
                    local new_proxy_url="https://${auth_token}@${proxy_host}:${proxy_port}"
                    
                    # Cập nhật config file
                    local temp_file=$(mktemp)
                    cat "$config_file" | jq --arg new_url "$new_proxy_url" '.proxy_url = $new_url' > "$temp_file"
                    mv "$temp_file" "$config_file"
                    
                    log "✅ Updated auth for port $port ($country)"
                    updated_count=$((updated_count + 1))
                fi
            fi
        fi
    done
    
    if [ $updated_count -gt 0 ]; then
        log "✅ Updated auth for $updated_count ProtonVPN services"
    else
        log "⚠️  No ProtonVPN services found to update"
    fi
}

check_and_kill_port() {
    local port=$1
    local service_name=$2
    
    log "🔍 Checking port $port..."
    
    # Tìm process đang sử dụng port
    local pids=""
    
    # Try lsof first
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
    
    # Tự động tạo lại config cho port 7890 nếu bị mất (WARP service)
    local gost_7890_config="$CONFIG_DIR/gost_7890.config"
    if [ ! -f "$gost_7890_config" ]; then
        log "🛡️  Port 7890 config missing, recreating..."
        mkdir -p "$CONFIG_DIR"
        cat > "$gost_7890_config" <<EOF
{
    "port": "7890",
    "provider": "warp",
    "country": "cloudflare",
    "proxy_url": "socks5://127.0.0.1:8111",
    "proxy_host": "127.0.0.1",
    "proxy_port": "8111",
    "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
        log "✅ Port 7890 config recreated"
    fi
    
    # Test ProtonVPN auth availability
    if get_protonvpn_auth >/dev/null 2>&1; then
        log "✅ ProtonVPN auth available"
    else
        log "⚠️  ProtonVPN auth not available (API may be down)"
    fi
    
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
                
                # Parse JSON config using Python (fallback if jq not available)
                if [ "$config_json" != "{}" ]; then
                    # Try jq first, fallback to Python
                    if command -v jq &> /dev/null; then
                        proxy_url=$(echo "$config_json" | jq -r '.proxy_url // ""' 2>/dev/null || echo "")
                        provider=$(echo "$config_json" | jq -r '.provider // ""' 2>/dev/null || echo "")
                        country=$(echo "$config_json" | jq -r '.country // ""' 2>/dev/null || echo "")
                    else
                        # Use Python to parse JSON
                        proxy_url=$(echo "$config_json" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('proxy_url', '') or '')" 2>/dev/null || echo "")
                        provider=$(echo "$config_json" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('provider', '') or '')" 2>/dev/null || echo "")
                        country=$(echo "$config_json" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('country', '') or '')" 2>/dev/null || echo "")
                    fi
                fi
                
                # Nếu không có config hoặc config rỗng, skip port này
                if [ -z "$proxy_url" ] || [ "$proxy_url" = "null" ]; then
                    log "⚠️  No config for port $port, skipping..."
                    continue
                fi
                
                # Tối ưu đặc biệt cho port 7890 (Cloudflare WARP)
                if [ "$port" = "7890" ]; then
                    # Tối ưu dựa trên kết quả test:
                    # - Giảm ttl từ 60s xuống 30s để giảm connection latency overhead
                    # - Tối ưu keepalive settings để duy trì connection tốt hơn
                    # - Thêm buffer size và connection pooling options
                    # Options:
                    # - ttl=30s: timeout 30 giây (cân bằng giữa latency và stability)
                    # - so_keepalive=true: enable TCP keepalive
                    # - so_keepalive_time=30s: keepalive interval 30 giây
                    # - so_keepalive_intvl=10s: keepalive probe interval 10 giây
                    # - so_keepalive_probes=3: số lần probe trước khi đóng connection
                    # - so_rcvbuf=65536: tăng receive buffer size để tăng throughput
                    # - so_sndbuf=65536: tăng send buffer size để tăng throughput
                    local optimized_proxy_url="$proxy_url"
                    # Thêm keepalive và timeout vào proxy URL nếu chưa có
                    if [[ "$proxy_url" == *"socks5://"* ]] && [[ "$proxy_url" != *"?"* ]]; then
                        optimized_proxy_url="${proxy_url}?so_keepalive=true&so_keepalive_time=30s&so_keepalive_intvl=10s&so_keepalive_probes=3&ttl=30s&so_rcvbuf=65536&so_sndbuf=65536"
                    fi
                    # Listener với timeout và keepalive tối ưu để giảm latency và tăng performance
                    local listener_opts="socks5://:$port?ttl=30s&so_keepalive=true&so_keepalive_time=30s&so_keepalive_intvl=10s&so_keepalive_probes=3&so_rcvbuf=65536&so_sndbuf=65536"
                    # Rotate log nếu cần trước khi start (đặc biệt quan trọng cho port 7890 chạy 24/7)
                    rotate_log_if_needed "$LOG_DIR/gost_${port}.log"
                    cleanup_old_logs "$LOG_DIR/gost_${port}.log"
                    nohup $GOST_BIN -D -L "$listener_opts" -F "$optimized_proxy_url" >> "$LOG_DIR/gost_${port}.log" 2>&1 &
                    local pid=$!
                    echo $pid > "$pid_file"
                    log "✅ Gost on port $port started with optimized settings (PID: $pid, proxy: $optimized_proxy_url)"
                else
                    # Khởi động gost với socks5 proxy (các port khác)
                    # Tối ưu đặc biệt cho ProtonVPN với các options:
                    # -D: debug mode để xem log chi tiết hơn khi có lỗi kết nối
                    # -L: listener với timeout và keepalive để tăng độ ổn định
                    #   - ttl=30s: timeout 30 giây cho connection (cân bằng giữa stability và performance)
                    #   - so_keepalive=true: enable TCP keepalive để duy trì connection
                    #   - so_keepalive_time=30s: keepalive interval 30 giây
                    #   - so_keepalive_intvl=10s: keepalive probe interval 10 giây
                    #   - so_keepalive_probes=3: số lần probe trước khi đóng connection
                    # -F: forwarder với timeout tối ưu cho ProtonVPN HTTPS proxy
                    # Gost tự động retry và reconnect khi connection drop
                    
                    # Tối ưu đặc biệt cho ProtonVPN
                    if [ "$provider" = "protonvpn" ]; then
                        # Tối ưu dựa trên kết quả test với cùng server (node-us-215b.protonvpn.net:4449):
                        # - Latency: Gost tốt hơn ProtonVPN trực tiếp (nhanh hơn 36-42%)
                        # - Connection latency: Gost nhanh hơn 332-1615ms
                        # - Ping average: Gost tốt hơn 1568-1895ms (36-41%)
                        # - Tối ưu keepalive settings để duy trì connection tốt
                        # Options:
                        # - Listener ttl=10s: timeout 10 giây cho client connections (tối ưu cho latency)
                        # - Forwarder ttl=30s: timeout 30 giây cho upstream proxy (đảm bảo đủ thời gian cho TLS handshake và authentication)
                        # - so_keepalive=true: enable TCP keepalive
                        # - so_keepalive_time=10s: keepalive interval 10 giây
                        # - so_keepalive_intvl=3s: keepalive probe interval 3 giây
                        # - so_keepalive_probes=3: số lần probe trước khi đóng connection
                        # - so_rcvbuf=65536: tăng receive buffer size để tăng throughput
                        # - so_sndbuf=65536: tăng send buffer size để tăng throughput
                        local listener_opts="socks5://:$port?ttl=10s&so_keepalive=true&so_keepalive_time=10s&so_keepalive_intvl=3s&so_keepalive_probes=3&so_rcvbuf=65536&so_sndbuf=65536"
                        # Forwarder với timeout dài hơn để tránh timeout khi TLS handshake chậm hoặc server xa
                        local forwarder_opts="$proxy_url?ttl=30s&so_keepalive=true&so_keepalive_time=10s&so_keepalive_intvl=3s&so_keepalive_probes=3&so_rcvbuf=65536&so_sndbuf=65536"
                        # Rotate log nếu cần trước khi start
                        rotate_log_if_needed "$LOG_DIR/gost_${port}.log"
                        cleanup_old_logs "$LOG_DIR/gost_${port}.log"
                        nohup $GOST_BIN -D -L "$listener_opts" -F "$forwarder_opts" >> "$LOG_DIR/gost_${port}.log" 2>&1 &
                        local pid=$!
                        echo $pid > "$pid_file"
                        log "✅ Gost on port $port started with ProtonVPN optimizations (PID: $pid, proxy: $proxy_url)"
                    else
                        # Default settings cho các provider khác
                        rotate_log_if_needed "$LOG_DIR/gost_${port}.log"
                        cleanup_old_logs "$LOG_DIR/gost_${port}.log"
                        nohup $GOST_BIN -D -L socks5://:$port -F "$proxy_url" >> "$LOG_DIR/gost_${port}.log" 2>&1 &
                        local pid=$!
                        echo $pid > "$pid_file"
                        log "✅ Gost on port $port started (PID: $pid, proxy: $proxy_url)"
                    fi
                fi
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
        
        # Parse JSON config using Python (fallback if jq not available)
        if [ "$config_json" != "{}" ]; then
            # Try jq first, fallback to Python
            if command -v jq &> /dev/null; then
                proxy_url=$(echo "$config_json" | jq -r '.proxy_url // ""' 2>/dev/null || echo "")
                provider=$(echo "$config_json" | jq -r '.provider // ""' 2>/dev/null || echo "")
                country=$(echo "$config_json" | jq -r '.country // ""' 2>/dev/null || echo "")
            else
                # Use Python to parse JSON
                proxy_url=$(echo "$config_json" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('proxy_url', '') or '')" 2>/dev/null || echo "")
                provider=$(echo "$config_json" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('provider', '') or '')" 2>/dev/null || echo "")
                country=$(echo "$config_json" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('country', '') or '')" 2>/dev/null || echo "")
            fi
        fi
        
        # Nếu không có config hoặc config rỗng, skip port này
        if [ -z "$proxy_url" ] || [ "$proxy_url" = "null" ]; then
            log "⚠️  No config for port $port, skipping..."
            return 0
        fi
        
        # Tối ưu đặc biệt cho port 7890 (Cloudflare WARP)
        if [ "$port" = "7890" ]; then
            # Tối ưu dựa trên kết quả test:
            # - Giảm ttl từ 60s xuống 30s để giảm connection latency overhead
            # - Tối ưu keepalive settings để duy trì connection tốt hơn
            # - Thêm buffer size và connection pooling options
            # Options:
            # - ttl=30s: timeout 30 giây (cân bằng giữa latency và stability)
            # - so_keepalive=true: enable TCP keepalive
            # - so_keepalive_time=30s: keepalive interval 30 giây
            # - so_keepalive_intvl=10s: keepalive probe interval 10 giây
            # - so_keepalive_probes=3: số lần probe trước khi đóng connection
            # - so_rcvbuf=65536: tăng receive buffer size để tăng throughput
            # - so_sndbuf=65536: tăng send buffer size để tăng throughput
            local optimized_proxy_url="$proxy_url"
            # Thêm keepalive và timeout vào proxy URL nếu chưa có
            if [[ "$proxy_url" == *"socks5://"* ]] && [[ "$proxy_url" != *"?"* ]]; then
                optimized_proxy_url="${proxy_url}?so_keepalive=true&so_keepalive_time=30s&so_keepalive_intvl=10s&so_keepalive_probes=3&ttl=30s&so_rcvbuf=65536&so_sndbuf=65536"
            fi
            # Listener với timeout và keepalive tối ưu để giảm latency và tăng performance
            local listener_opts="socks5://:$port?ttl=30s&so_keepalive=true&so_keepalive_time=30s&so_keepalive_intvl=10s&so_keepalive_probes=3&so_rcvbuf=65536&so_sndbuf=65536"
            # Rotate log nếu cần trước khi start (đặc biệt quan trọng cho port 7890 chạy 24/7)
            rotate_log_if_needed "$LOG_DIR/gost_${port}.log"
            cleanup_old_logs "$LOG_DIR/gost_${port}.log"
            nohup $GOST_BIN -D -L "$listener_opts" -F "$optimized_proxy_url" >> "$LOG_DIR/gost_${port}.log" 2>&1 &
            local pid=$!
            echo $pid > "$pid_file"
            log "✅ Gost on port $port started with optimized settings (PID: $pid, proxy: $optimized_proxy_url)"
        else
            # Khởi động gost với socks5 proxy (các port khác)
            # Tối ưu đặc biệt cho ProtonVPN với các options:
            # -D: debug mode để xem log chi tiết hơn khi có lỗi kết nối
            # -L: listener với timeout và keepalive để tăng độ ổn định
            #   - ttl=30s: timeout 30 giây cho connection (cân bằng giữa stability và performance)
            #   - so_keepalive=true: enable TCP keepalive để duy trì connection
            #   - so_keepalive_time=30s: keepalive interval 30 giây
            #   - so_keepalive_intvl=10s: keepalive probe interval 10 giây
            #   - so_keepalive_probes=3: số lần probe trước khi đóng connection
            # -F: forwarder với timeout tối ưu cho ProtonVPN HTTPS proxy
            # Gost tự động retry và reconnect khi connection drop
            
            # Tối ưu đặc biệt cho ProtonVPN
            if [ "$provider" = "protonvpn" ]; then
                # Tối ưu dựa trên kết quả test với cùng server (node-us-215b.protonvpn.net:4449):
                # - Latency: Gost tốt hơn ProtonVPN trực tiếp (nhanh hơn 36-42%)
                # - Connection latency: Gost nhanh hơn 332-1615ms
                # - Ping average: Gost tốt hơn 1568-1895ms (36-41%)
                # - Tối ưu keepalive settings để duy trì connection tốt
                # Options:
                # - Listener ttl=10s: timeout 10 giây cho client connections (tối ưu cho latency)
                # - Forwarder ttl=30s: timeout 30 giây cho upstream proxy (đảm bảo đủ thời gian cho TLS handshake và authentication)
                # - so_keepalive=true: enable TCP keepalive
                # - so_keepalive_time=10s: keepalive interval 10 giây
                # - so_keepalive_intvl=3s: keepalive probe interval 3 giây
                # - so_keepalive_probes=3: số lần probe trước khi đóng connection
                # - so_rcvbuf=65536: tăng receive buffer size để tăng throughput
                # - so_sndbuf=65536: tăng send buffer size để tăng throughput
                local listener_opts="socks5://:$port?ttl=10s&so_keepalive=true&so_keepalive_time=10s&so_keepalive_intvl=3s&so_keepalive_probes=3&so_rcvbuf=65536&so_sndbuf=65536"
                # Forwarder với timeout dài hơn để tránh timeout khi TLS handshake chậm hoặc server xa
                local forwarder_opts="$proxy_url?ttl=30s&so_keepalive=true&so_keepalive_time=10s&so_keepalive_intvl=3s&so_keepalive_probes=3&so_rcvbuf=65536&so_sndbuf=65536"
                nohup $GOST_BIN -D -L "$listener_opts" -F "$forwarder_opts" > "$LOG_DIR/gost_${port}.log" 2>&1 &
                local pid=$!
                echo $pid > "$pid_file"
                log "✅ Gost on port $port started with ProtonVPN optimizations (PID: $pid, proxy: $proxy_url)"
            else
                # Default settings cho các provider khác
                nohup $GOST_BIN -D -L socks5://:$port -F "$proxy_url" > "$LOG_DIR/gost_${port}.log" 2>&1 &
                local pid=$!
                echo $pid > "$pid_file"
                log "✅ Gost on port $port started (PID: $pid, proxy: $proxy_url)"
            fi
        fi
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
    local proxy_host=$4
    local proxy_port=$5
    
    # Validate port format (should be a number)
    if ! [[ "$port" =~ ^[0-9]+$ ]]; then
        log "❌ Invalid port format. Must be a number"
        return 1
    fi
    
    if [ "$provider" != "nordvpn" ] && [ "$provider" != "protonvpn" ]; then
        log "❌ Invalid provider. Available: nordvpn, protonvpn"
        return 1
    fi
    
    # Validate proxy_host and proxy_port
    if [ -z "$proxy_host" ] || [ -z "$proxy_port" ]; then
        log "❌ proxy_host and proxy_port are required"
        return 1
    fi
    
    # Lấy proxy URL
    local proxy_url=$(get_proxy_info "$provider" "$country" "$proxy_host" "$proxy_port")
    if [ -z "$proxy_url" ]; then
        log "❌ Failed to get proxy info for $provider ($country)"
        return 1
    fi
    
    # Lưu cấu hình
    save_proxy_config $port "$provider" "$country" "$proxy_url" "$proxy_host" "$proxy_port"
    log "✅ Configured gost port $port: $provider ($country) - $proxy_host:$proxy_port"
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
            echo "  port: 7891-7999"
            exit 1
        fi
        restart_gost_port "$2"
        ;;
    restart-port)
        if [ $# -lt 2 ]; then
            echo "Usage: $0 restart-port <port>"
            echo "  port: 7891-7999"
            exit 1
        fi
        restart_gost_port "$2"
        ;;
    status)
        status_gost
        ;;
    config)
        if [ $# -lt 6 ]; then
            echo "Usage: $0 config <port> <provider> <country> <proxy_host> <proxy_port>"
            echo "  port: 7891-7999"
            echo "  provider: nordvpn, protonvpn"
            echo "  country: server identifier"
            echo "  proxy_host: proxy hostname"
            echo "  proxy_port: proxy port"
            exit 1
        fi
        configure_gost "$2" "$3" "$4" "$5" "$6"
        ;;
    show-config)
        show_config "${2:-}"
        ;;
    update-protonvpn-auth)
        update_all_protonvpn_auth
        ;;
    rotate-logs)
        # Rotate logs cho tất cả Gost services
        log "🔄 Rotating logs for all Gost services..."
        for config_file in "$CONFIG_DIR"/gost_*.config; do
            if [ -f "$config_file" ]; then
                local port=$(basename "$config_file" | sed 's/gost_\(.*\)\.config/\1/')
                local log_file="$LOG_DIR/gost_${port}.log"
                if [ -f "$log_file" ]; then
                    rotate_log_if_needed "$log_file"
                    cleanup_old_logs "$log_file"
                    log "✅ Checked log rotation for port $port"
                fi
            fi
        done
        log "✅ Log rotation complete"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|restart-instance|restart-port|status|config|show-config|update-protonvpn-auth|rotate-logs}"
        echo ""
        echo "Commands:"
        echo "  start                    - Start all gost services"
        echo "  stop                     - Stop all gost services"
        echo "  restart                  - Restart all gost services"
        echo "  restart-instance <p>     - Restart specific gost service on port p"
        echo "  restart-port <p>         - Restart gost on specific port p"
        echo "  status                   - Show status of all services"
        echo "  config <p> <pr> <c>      - Configure port p with provider pr and country c"
        echo "  show-config [p]          - Show configuration for port p (or all)"
        echo "  update-protonvpn-auth    - Update auth for all ProtonVPN services"
        echo "  rotate-logs              - Rotate logs for all Gost services (if > 50MB)"
        echo ""
        echo "Examples:"
        echo "  $0 config 7891 protonvpn node-uk-29.protonvpn.net"
        echo "  $0 config 7892 nordvpn us"
        echo "  $0 restart-instance 7892"
        echo "  $0 restart-port 7892"
        echo "  $0 show-config 7891"
        echo "  $0 show-config"
        exit 1
        ;;
esac
