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
  local start=$(date +%s%3N 2>/dev/null || echo $(($(date +%s) * 1000)))
  local ip=$(curl -s --max-time 8 -x socks5h://127.0.0.1:${port} "$TEST_IP_URL" 2>/dev/null || echo "N/A")
  local end=$(date +%s%3N 2>/dev/null || echo $(($(date +%s) * 1000)))
  local latency=$((end - start))
  
  if [[ "$ip" == "N/A" || -z "$ip" ]]; then
    echo "$port,offline,N/A"
  else
    echo "$port,online,$latency"
  fi
}

build_haproxy_cfg() {
  local active_port="$1"
  local wg_servers=""
  local i=1
  
  for p in "${WG_PORTS[@]}"; do
    if [[ "$p" == "$active_port" ]]; then
      wg_servers+="    server wg${i} 127.0.0.1:${p} check inter 5s rise 2 fall 3\n"
    else
      wg_servers+="    server wg${i} 127.0.0.1:${p} check inter 5s rise 2 fall 3 backup\n"
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
    timeout client 1m
    timeout server 1m
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
    server cloudflare_warp ${HOST_PROXY} check inter 5s rise 2 fall 3 backup

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

health_loop() {
  log "🩺 Health monitor started (interval ${HEALTH_INTERVAL}s, SOCKS $SOCK_PORT)"
  
  while true; do
    declare -A latencies=()
    best_port=""
    best_latency=999999

    for p in "${WG_PORTS[@]}"; do
      result=$(check_backend "$p")
      IFS=',' read -r port status latency <<< "$result"
      
      if [[ "$status" == "online" ]]; then
        log "✅ Wiresock port $port OK (${latency}ms)"
        latencies["$port"]=$latency
        if (( latency < best_latency )); then
          best_latency=$latency
          best_port=$port
        fi
      else
        log "❌ Wiresock port $port offline"
      fi
    done

    if [[ -n "$best_port" ]]; then
      log "🏆 Best backend: wiresock:$best_port (${best_latency}ms)"
      build_haproxy_cfg "$best_port"
      reload_haproxy
    else
      log "⚠️  No wiresock backend online — fallback to Cloudflare WARP ($HOST_PROXY)"
      build_haproxy_cfg "none"
      reload_haproxy
    fi
    
    sleep "$HEALTH_INTERVAL"
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

