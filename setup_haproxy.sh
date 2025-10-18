#!/usr/bin/env bash
# setup_haproxy.sh
# Multi-instance HAProxy with wiresock backends & Cloudflare WARP fallback
# macOS/Linux compatible | 2025-10

set -euo pipefail

### --- Default settings ---
HAPROXY_BIN="$(command -v haproxy || echo /opt/homebrew/sbin/haproxy)"
WIRESOCK_BIN="$(command -v wiresock-client || echo /usr/local/bin/wiresock-client)"
WIRESOCK_DIR="./wireguard"
HOST_PROXY="127.0.0.1:8111"  # Cloudflare WARP proxy
WG_PORTS=(18181 18182)
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
  $0 [--host-proxy IP:PORT] [--wg-ports 18181,18182]
     [--sock-port 1080] [--stats-port 8080]
     [--wiresock-folder DIR] [--stats-auth user:pass] 
     [--health-interval 30] [--daemon]
     
Examples:
  # HAProxy instance 1 (port 7891)
  $0 --sock-port 7891 --stats-port 8091 --wg-ports 18181 --daemon
  
  # HAProxy instance 2 (port 7892)
  $0 --sock-port 7892 --stats-port 8092 --wg-ports 18182 --daemon"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --host-proxy) HOST_PROXY="$2"; shift 2 ;;
    --wg-ports) IFS=',' read -r -a WG_PORTS <<< "$2"; shift 2 ;;
    --wiresock-folder) WIRESOCK_DIR="$2"; shift 2 ;;
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
  # Use lightweight TCP check instead of HTTP request
  if timeout 2 bash -c "echo > /dev/tcp/127.0.0.1/$port" 2>/dev/null; then
    echo "$port,online,0s"
  else
    echo "$port,offline,N/A"
  fi
}

build_haproxy_cfg() {
  local active_port="$1"
  local wg_servers=""
  local i=1
  
  for p in "${WG_PORTS[@]}"; do
    if [[ "$p" == "$active_port" ]]; then
      wg_servers+="    server wg${i} 127.0.0.1:${p} check inter 1s rise 1 fall 2 on-error fastinter\n"
    else
      wg_servers+="    server wg${i} 127.0.0.1:${p} check inter 1s rise 1 fall 2 on-error fastinter backup\n"
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
$(printf "%b" "$wg_servers")
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

  for p in "${WG_PORTS[@]}"; do
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
    fi
  done

  # Determine current best backend
  if [[ -n "$best_port" ]]; then
    current_best="wiresock:$best_port"
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
      log "🔄 Backend changed to: wiresock:$best_port (${best_latency}s)"
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
log "   Wiresock Backends: ${WG_PORTS[*]}"
log "   Fallback: Cloudflare WARP ($HOST_PROXY)"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Initial config with first WG port as primary
build_haproxy_cfg "${WG_PORTS[0]}"
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

