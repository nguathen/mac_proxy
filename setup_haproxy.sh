#!/usr/bin/env bash
# setup_haproxy.sh
# Multi-instance HAProxy with gost backends & Cloudflare WARP fallback
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
  # HAProxy instance 1 (port 7891)
  $0 --sock-port 7891 --stats-port 8091 --gost-ports 18181 --daemon
  
  # HAProxy instance 2 (port 7892)
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
  if curl -s --connect-timeout 2 --max-time 3 -x "socks5h://127.0.0.1:$port" https://1.1.1.1 >/dev/null 2>&1; then
    local end_time=$(date +%s)
    local latency=$((end_time - start_time))
    echo "$port,online,${latency}s"
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
      # All gost servers as backup when forcing WARP
      gost_servers+="    server gost${i} 127.0.0.1:${p} check inter 1s rise 1 fall 2 on-error fastinter backup disabled\n"
    elif [[ "$p" == "$active_port" ]]; then
      gost_servers+="    server gost${i} 127.0.0.1:${p} check inter 1s rise 1 fall 2 on-error fastinter\n"
    else
      gost_servers+="    server gost${i} 127.0.0.1:${p} check inter 1s rise 1 fall 2 on-error fastinter backup\n"
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
    timeout connect 2s
    timeout client 1m
    timeout server 1m
    timeout check 2s
    retries 2
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
    server cloudflare_warp ${HOST_PROXY} check inter 1s rise 1 fall 2 on-error fastinter backup

listen stats_${SOCK_PORT}
    bind 0.0.0.0:${STATS_PORT}
    mode http
    stats enable
    stats uri /haproxy?stats
    stats refresh 2s
    stats show-legends
    stats show-desc HAProxy Instance - SOCKS:${SOCK_PORT}
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
    else
      log "🔄 Backend changed to: Cloudflare WARP ($HOST_PROXY)"
      build_haproxy_cfg "none"
      reload_haproxy
    fi
  fi
}

health_loop() {
  log "🩺 Health monitor started (interval ${HEALTH_INTERVAL}s, SOCKS $SOCK_PORT)"
  
  local trigger_file="${LOG_DIR}/trigger_check_${SOCK_PORT}"
  
  while true; do
    # Check if triggered by file
    if [[ -f "$trigger_file" ]]; then
      log "⚡ Triggered immediate health check"
      rm -f "$trigger_file"
      do_health_check
    fi
    
    # Regular check
    do_health_check
    
    # Sleep with inotify-like behavior (check every 2s instead of 1s)
    local elapsed=0
    while (( elapsed < HEALTH_INTERVAL )); do
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

### --- Main ---
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "🚀 Starting HAProxy instance"
log "   SOCKS Port: $SOCK_PORT"
log "   Stats Port: $STATS_PORT (http://0.0.0.0:$STATS_PORT/haproxy?stats)"
log "   Gost Backends: ${GOST_PORTS[*]}"
log "   Fallback: Cloudflare WARP ($HOST_PROXY)"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Initial config with first gost port as primary
build_haproxy_cfg "${GOST_PORTS[0]}"
reload_haproxy

if $DAEMON_MODE; then
  health_loop &
  HEALTH_PID=$!
  echo "$HEALTH_PID" > "${LOG_DIR}/health_${SOCK_PORT}.pid"
  log "✅ Running in background — Health monitor PID: $HEALTH_PID"
  log "   Log file: $LOG_FILE"
  log "   Stop with: kill $HEALTH_PID"
else
  health_loop
fi

