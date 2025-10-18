# HAProxy Failover Logic

## Vấn đề

Khi Wireproxy đang chạy (port listening) nhưng WireGuard tunnel down, HAProxy vẫn coi backend là "UP" vì TCP connection thành công. Điều này dẫn đến:

```
Client → HAProxy → Wireproxy (port open) → WireGuard tunnel (DOWN) → ❌ ERR_SOCKS_CONNECTION_FAILED
```

## Giải pháp

### 1. Health Check nâng cao

Health monitor script (`setup_haproxy.sh`) thực hiện 2 bước kiểm tra:

**Bước 1: TCP Check**
```bash
timeout 1 bash -c "echo > /dev/tcp/127.0.0.1/$port"
```
- Kiểm tra port có đang listen không
- Nếu fail → Backend = `offline`

**Bước 2: SOCKS Proxy Test**
```bash
timeout 3 curl -s --max-time 2 -x "socks5h://127.0.0.1:$port" https://1.1.1.1
```
- Test thực tế proxy có forward traffic được không
- Nếu fail → Backend = `degraded`

### 2. Backend States

| State | Ý nghĩa | Hành động |
|-------|---------|-----------|
| `online` | Port listening + Proxy hoạt động | Sử dụng backend |
| `degraded` | Port listening + Proxy KHÔNG hoạt động | Coi như offline, failover |
| `offline` | Port không listening | Coi như offline, failover |

### 3. Failover Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Health Check (mỗi 10 giây)                                  │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
        ┌─────────────────────────────────┐
        │ Check Backend Status            │
        └─────────────────────────────────┘
                          │
        ┌─────────────────┴─────────────────┐
        │                                   │
        ▼                                   ▼
┌───────────────┐                  ┌────────────────┐
│ Port Check    │                  │ Proxy Test     │
│ (TCP connect) │                  │ (curl via SOCKS)│
└───────────────┘                  └────────────────┘
        │                                   │
        ├─ Fail → offline                  │
        └─ OK ──────────────────────────────┤
                                            │
                          ┌─────────────────┴─────────────────┐
                          │                                   │
                          ▼                                   ▼
                    ┌──────────┐                      ┌──────────────┐
                    │ online   │                      │ degraded     │
                    │ (use it) │                      │ (failover)   │
                    └──────────┘                      └──────────────┘
```

### 4. HAProxy Config Update

Khi phát hiện tất cả backends degraded/offline:

```haproxy
backend socks_back_7891
    balance first
    # All WG servers disabled
    server wg1 127.0.0.1:18181 check backup disabled
    server wg2 127.0.0.1:18182 check backup disabled
    # WARP becomes active
    server cloudflare_warp 127.0.0.1:8111 check backup
```

→ Traffic tự động chuyển sang Cloudflare WARP

### 5. Auto Recovery

Khi WireGuard tunnel phục hồi:

1. Health check phát hiện backend `online`
2. Tính latency của backend
3. So sánh với backend hiện tại
4. Nếu tốt hơn → Reload HAProxy config
5. Traffic chuyển về WireGuard

## Scenarios

### Scenario 1: WireGuard Tunnel Down

```
Initial State:
  Wireproxy: Running (PID 12345)
  WireGuard: Tunnel DOWN
  
Health Check:
  TCP Check: ✅ OK (port listening)
  Proxy Test: ❌ FAIL (tunnel down)
  Status: degraded
  
Action:
  → Rebuild HAProxy config with WG disabled
  → Reload HAProxy
  → Traffic → WARP
  
Result:
  Client → HAProxy → WARP → ✅ Success
```

### Scenario 2: Wireproxy Crashed

```
Initial State:
  Wireproxy: Crashed (port not listening)
  
Health Check:
  TCP Check: ❌ FAIL
  Status: offline
  
Action:
  → Rebuild HAProxy config with WG disabled
  → Reload HAProxy
  → Traffic → WARP
  
Result:
  Client → HAProxy → WARP → ✅ Success
```

### Scenario 3: WireGuard Recovery

```
Initial State:
  Using: WARP
  Wireproxy: Running + Tunnel UP
  
Health Check:
  TCP Check: ✅ OK
  Proxy Test: ✅ OK (latency 50ms)
  Status: online
  
Action:
  → Rebuild HAProxy config with WG primary
  → Reload HAProxy
  → Traffic → WireGuard
  
Result:
  Client → HAProxy → WireGuard → ✅ Success
```

## Configuration

### Health Check Interval
```bash
HEALTH_INTERVAL=10  # seconds
```

### Timeouts
```bash
TCP Check: 1 second
Proxy Test: 2 seconds (with 3s timeout)
```

### HAProxy Check Settings
```haproxy
check inter 1s    # Check every 1 second
rise 1            # 1 success = UP
fall 2            # 2 failures = DOWN
on-error fastinter # Check faster on error
```

## Logs

Health monitor logs tại: `logs/haproxy_health_7891.log`

```
[2025-10-18 23:11:42] ⚠️  Backend 18181 is degraded (port open but proxy not working)
[2025-10-18 23:11:42] 🔄 Backend changed to: Cloudflare WARP (127.0.0.1:8111)
[2025-10-18 23:11:42] ♻️  Reloaded HAProxy (pid 80048)
```

## Testing

### Test degraded state manually

```bash
# Start wireproxy với invalid WireGuard config
# Port sẽ listen nhưng tunnel không hoạt động

# Check health
bash -c 'source setup_haproxy.sh && check_backend 18181'
# Output: 18181,degraded,N/A

# Verify failover
curl -x socks5h://127.0.0.1:7891 https://api.ipify.org
# Should return WARP IP, not WireGuard IP
```

### Monitor failover

```bash
# Watch health logs
tail -f logs/haproxy_health_7891.log

# Watch HAProxy stats
open http://localhost:8091/haproxy?stats
```

## Benefits

1. ✅ **No ERR_SOCKS_CONNECTION_FAILED**: Auto failover khi tunnel down
2. ✅ **Fast Detection**: 2-3 seconds để phát hiện degraded state
3. ✅ **Auto Recovery**: Tự động quay về WireGuard khi tunnel up
4. ✅ **Zero Downtime**: HAProxy reload không ảnh hưởng connections
5. ✅ **Transparent**: Client không cần biết backend nào đang active

