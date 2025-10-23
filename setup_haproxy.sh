#!/usr/bin/env bash
# setup_haproxy.sh
# HAProxy with gost backends & Cloudflare WARP fallback
# macOS/Linux compatible | 2025-10

set -euo pipefail

### --- Default settings ---
HAPROXY_BIN="$(command -v haproxy || echo /opt/homebrew/sbin/haproxy)"
GOST_BIN="$(command -v gost || echo gost)"
GOST_DIR="./logs"
HOST_PROXY="127.0.0.1:8111"  # Cloudflare WARP proxy
GOST_PORTS=(18181 18182 18183 18184 18185 18186 18187)
STATS_AUTH="admin:admin123"
TEST_IP_URL="https://api.ipify.org"
HEALTH_INTERVAL=30
DAEMON_MODE=false

SOCK_PORT=1080
STATS_PORT=8080
CFG_DIR="./config"
LOG_DIR="./logs"

### --- CLI parsing ---
usage() {
  echo "Usage:
  $0 [--host-proxy IP:PORT] [--gost-ports 18181,18182]
     [--sock-port 1080] [--stats-port 8080]
     [--gost-folder DIR] [--stats-auth user:pass] 
     [--health-interval 30] [--daemon]
     
Examples:
  # HAProxy service (port 7891)
  $0 --sock-port 7891 --stats-port 8091 --gost-ports 18181 --daemon
  
  # HAProxy service (port 7892)
  $0 --sock-port 7892 --stats-port 8092 --gost-ports 18182 --daemon"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --host-proxy) HOST_PROXY="$2"; shift 2 ;;
    --gost-ports) IFS=',' read -r -a GOST_PORTS <<< "$2"; shift 2 ;;
    --gost-folder) GOST_DIR="$2"; shift 2 ;;
    --stats-auth) STATS_AUTH="$2"; shift 2 ;;
    --sock-port) SOCK_PORT="$2"; shift 2 ;;
    --stats-port) STATS_PORT="$2"; shift 2 ;;
    --health-interval) HEALTH_INTERVAL="$2"; shift 2 ;;
    --daemon) DAEMON_MODE=true; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

### --- Derived paths ---
CFG_FILE="${CFG_DIR}/haproxy_${SOCK_PORT}.cfg"
PID_FILE="${LOG_DIR}/haproxy_${SOCK_PORT}.pid"
LOG_FILE="${LOG_DIR}/haproxy_health_${SOCK_PORT}.log"

mkdir -p "$CFG_DIR" "$LOG_DIR"

### --- Helpers ---
timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(timestamp)] $*" | tee -a "$LOG_FILE"; }

reload_haproxy() {
  if [ -f "$PID_FILE" ] && pid=$(cat "$PID_FILE" 2>/dev/null) && kill -0 "$pid" 2>/dev/null; then
    "$HAPROXY_BIN" -f "$CFG_FILE" -p "$PID_FILE" -sf "$pid" 2>&1 | tee -a "$LOG_FILE"
    log "♻️  Reloaded HAProxy (pid $pid)"
  else
    "$HAPROXY_BIN" -f "$CFG_FILE" -p "$PID_FILE" -D 2>&1 | tee -a "$LOG_FILE"
    log "🚀 Started HAProxy on SOCKS port $SOCK_PORT"
  fi
}

# Cleanup function to stop background processes
cleanup_processes() {
  local monitor_pid_file="${LOG_DIR}/gost_monitor_${SOCK_PORT}.pid"
  if [[ -f "$monitor_pid_file" ]]; then
    local monitor_pid=$(cat "$monitor_pid_file" 2>/dev/null)
    if [[ -n "$monitor_pid" ]] && kill -0 "$monitor_pid" 2>/dev/null; then
      kill "$monitor_pid" 2>/dev/null
      log "🛑 Stopped background gost monitoring (PID: $monitor_pid)"
    fi
    rm -f "$monitor_pid_file"
  fi
}

check_backend() {
  local port=$1
  
  # Step 1: Check if port is listening
  if ! bash -c "exec 3<>/dev/tcp/127.0.0.1/$port && exec 3>&-" 2>/dev/null; then
    echo "$port,offline,N/A"
    return
  fi
  
  # Step 2: Test actual SOCKS proxy functionality
  # Try to connect through the proxy to a reliable endpoint
  local start_time=$(date +%s)
  
  # Use faster timeout when checking for recovery from WARP
  local last_backend_file="${LOG_DIR}/last_backend_${SOCK_PORT}"
  local last_backend=""
  [[ -f "$last_backend_file" ]] && last_backend=$(cat "$last_backend_file")
  
  local connect_timeout=5
  local max_time=10
  
  if [[ "$last_backend" == "warp" ]]; then
    # Faster check when trying to recover from WARP
    connect_timeout=3
    max_time=6
  fi
  
  if curl -s --connect-timeout $connect_timeout --max-time $max_time -x "socks5h://127.0.0.1:$port" https://1.1.1.1 >/dev/null 2>&1; then
    local end_time=$(date +%s)
    local latency=$((end_time - start_time))
    echo "$port,online,${latency}s"
    
    # If gost just came online and we're using WARP, trigger immediate HAProxy update
    if [[ "$last_backend" == "warp" ]]; then
      log "⚡ Gost $port just came online - triggering immediate HAProxy update"
      touch "${LOG_DIR}/trigger_check_${SOCK_PORT}"
    fi
  else
    # Port is open but proxy is not working (e.g., WireGuard tunnel down)
    echo "$port,degraded,N/A"
  fi
}

build_haproxy_cfg() {
  local active_port="$1"
  local gost_servers=""
  local i=1
  
  for p in "${GOST_PORTS[@]}"; do
    if [[ "$active_port" == "none" ]]; then
      # All gost servers as backup when forcing WARP - use faster check intervals
      gost_servers+="    server gost${i} 127.0.0.1:${p} check inter 2s rise 2 fall 3 on-error fastinter backup disabled\n"
    elif [[ "$p" == "$active_port" ]]; then
      gost_servers+="    server gost${i} 127.0.0.1:${p} check inter 5s rise 3 fall 5 on-error fastinter\n"
    else
      gost_servers+="    server gost${i} 127.0.0.1:${p} check inter 5s rise 3 fall 5 on-error fastinter backup\n"
    fi
    i=$((i+1))
  done

  cat > "$CFG_FILE" <<EOF
global
    log stdout format raw local0
    maxconn 4096
    pidfile $PID_FILE
    daemon

defaults
    mode tcp
    timeout connect 5s
    timeout client 2m
    timeout server 2m
    timeout check 10s
    retries 3
    option redispatch
    option tcplog
    log global

frontend socks_front_${SOCK_PORT}
    bind 0.0.0.0:${SOCK_PORT}
    default_backend socks_back_${SOCK_PORT}

backend socks_back_${SOCK_PORT}
    balance first
    option tcp-check
    tcp-check connect
$(printf "%b" "$gost_servers")
    server cloudflare_warp ${HOST_PROXY} check inter 3s rise 2 fall 3 on-error fastinter backup

listen stats_${SOCK_PORT}
    bind 0.0.0.0:${STATS_PORT}
    mode http
    stats enable
    stats uri /haproxy?stats
    stats refresh 2s
    stats show-legends
    stats show-desc HAProxy Service - SOCKS:${SOCK_PORT}
EOF

  [[ -n "$STATS_AUTH" ]] && echo "    stats auth ${STATS_AUTH}" >> "$CFG_FILE"
}

do_health_check() {
  declare -A latencies=()
  best_port=""
  best_latency=999999
  local config_changed=false
  local current_best=""

  for p in "${GOST_PORTS[@]}"; do
    result=$(check_backend "$p")
    IFS=',' read -r port status latency <<< "$result"
    
    if [[ "$status" == "online" ]]; then
      # Extract numeric value for comparison
      local lat_num=${latency%s}
      latencies["$port"]=$lat_num
      if (( lat_num < best_latency )); then
        best_latency=$lat_num
        best_port=$port
      fi
    elif [[ "$status" == "degraded" ]]; then
      # Port is listening but proxy not working - treat as offline
      log "⚠️  Backend $port is degraded (port open but proxy not working)"
    fi
  done

  # Determine current best backend
  if [[ -n "$best_port" ]]; then
    current_best="gost:$best_port"
  else
    current_best="warp"
  fi

  # Only reload if backend changed
  local last_backend_file="${LOG_DIR}/last_backend_${SOCK_PORT}"
  local last_backend=""
  [[ -f "$last_backend_file" ]] && last_backend=$(cat "$last_backend_file")

  if [[ "$current_best" != "$last_backend" ]]; then
    config_changed=true
    echo "$current_best" > "$last_backend_file"
    
    if [[ -n "$best_port" ]]; then
      log "🔄 Backend changed to: gost:$best_port (${best_latency}s)"
      build_haproxy_cfg "$best_port"
      reload_haproxy
      
      # If recovering from WARP to Gost, trigger immediate next check for faster detection
      if [[ "$last_backend" == "warp" ]]; then
        log "⚡ Gost recovery detected - triggering immediate next check"
        touch "${LOG_DIR}/trigger_check_${SOCK_PORT}"
      fi
    else
      log "🔄 Backend changed to: Cloudflare WARP ($HOST_PROXY)"
      build_haproxy_cfg "none"
      reload_haproxy
    fi
  fi
}

# Background gost monitoring function
monitor_gost_connections() {
  local last_backend_file="${LOG_DIR}/last_backend_${SOCK_PORT}"
  local trigger_file="${LOG_DIR}/trigger_check_${SOCK_PORT}"
  
  while true; do
    # Only monitor when using WARP
    if [[ -f "$last_backend_file" ]] && [[ "$(cat "$last_backend_file")" == "warp" ]]; then
      # Quick check if any gost port is listening
      for p in "${GOST_PORTS[@]}"; do
        if bash -c "exec 3<>/dev/tcp/127.0.0.1/$p && exec 3>&-" 2>/dev/null; then
          # Port is listening, do a quick proxy test
          if curl -s --connect-timeout 2 --max-time 3 -x "socks5h://127.0.0.1:$p" https://1.1.1.1 >/dev/null 2>&1; then
            log "⚡ Gost $p connection detected - triggering immediate HAProxy update"
            touch "$trigger_file"
            break
          fi
        fi
      done
    fi
    sleep 1  # Check every second when using WARP
  done
}

health_loop() {
  log "🩺 Health monitor started (interval ${HEALTH_INTERVAL}s, SOCKS $SOCK_PORT)"
  
  local trigger_file="${LOG_DIR}/trigger_check_${SOCK_PORT}"
  local last_backend_file="${LOG_DIR}/last_backend_${SOCK_PORT}"
  local current_interval="${HEALTH_INTERVAL}"
  
  # Start background gost monitoring
  monitor_gost_connections &
  local monitor_pid=$!
  echo "$monitor_pid" > "${LOG_DIR}/gost_monitor_${SOCK_PORT}.pid"
  log "🔍 Started background gost monitoring (PID: $monitor_pid)"
  
  while true; do
    # Check if triggered by file
    if [[ -f "$trigger_file" ]]; then
      log "⚡ Triggered immediate health check"
      rm -f "$trigger_file"
      do_health_check
    fi
    
    # Regular check
    do_health_check
    
    # Dynamic interval based on current backend
    # If using WARP, check more frequently to detect Gost recovery
    local last_backend=""
    [[ -f "$last_backend_file" ]] && last_backend=$(cat "$last_backend_file")
    
    if [[ "$last_backend" == "warp" ]]; then
      current_interval=5  # Check every 5s when using WARP
      log "🔄 Using WARP - checking Gost servers every 5s for faster recovery"
    else
      current_interval="${HEALTH_INTERVAL}"  # Normal interval when using Gost
    fi
    
    # Sleep with inotify-like behavior
    local elapsed=0
    while (( elapsed < current_interval )); do
      sleep 2
      elapsed=$((elapsed + 2))
      
      # Check trigger during sleep
      if [[ -f "$trigger_file" ]]; then
        log "⚡ Triggered immediate health check"
        rm -f "$trigger_file"
        do_health_check
        break
      fi
    done
  done
}

### --- Signal handlers ---
trap 'cleanup_processes; exit 0' INT TERM

### --- Main ---
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "🚀 Starting HAProxy service"
log "   SOCKS Port: $SOCK_PORT"
log "   Stats Port: $STATS_PORT (http://0.0.0.0:$STATS_PORT/haproxy?stats)"
log "   Gost Backends: ${GOST_PORTS[*]}"
log "   Fallback: Cloudflare WARP ($HOST_PROXY)"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Initial config with first gost port as primary
build_haproxy_cfg "${GOST_PORTS[0]}"
reload_haproxy

if $DAEMON_MODE; then
  # Start health monitor in background
  health_loop &
  HEALTH_PID=$!
  echo "$HEALTH_PID" > "${LOG_DIR}/health_${SOCK_PORT}.pid"
  log "✅ Running in background — Health monitor PID: $HEALTH_PID"
  log "   Log file: $LOG_FILE"
  log "   Stop with: kill $HEALTH_PID"
  
  # Exit immediately after starting background process
  log "🚀 HAProxy daemon started successfully"
  exit 0
else
  # Run health monitor in foreground
  health_loop
fi

