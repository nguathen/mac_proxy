# Gost Configuration System

Hệ thống cấu hình và quản lý Gost proxy instances.

## 🚀 Tính năng

- ✅ **Lưu trữ cấu hình**: Mỗi Gost instance có file config riêng
- ✅ **Khôi phục tự động**: Tự động khôi phục cấu hình khi restart
- ✅ **Cập nhật credentials**: Tự động cập nhật ProtonVPN credentials
- ✅ **Multi-instance**: Hỗ trợ nhiều instances (port 7891-7999)
- ✅ **CLI Management**: Quản lý qua command line
- ✅ **Web UI**: Quản lý qua giao diện web
- ✅ **Monitoring**: Tự động monitor và restart nếu down

## 📁 Cấu trúc file

```
config/
├── gost_7890.config          # WARP fallback
├── gost_7891.config          # Instance 1
├── gost_7892.config          # Instance 2
└── ...

logs/
├── gost_7890.log             # Logs
├── gost_7890.pid             # PID file
├── gost_7891.log
├── gost_7891.pid
└── ...
```

## 🔧 Quản lý Gost

### Khởi động/Dừng

```bash
# Khởi động tất cả instances
./manage_gost.sh start

# Dừng tất cả instances
./manage_gost.sh stop

# Khởi động lại tất cả
./manage_gost.sh restart

# Kiểm tra trạng thái
./manage_gost.sh status
```

### Cấu hình Instance

```bash
# Cấu hình instance
./manage_gost.sh config <port> <provider> <country> <proxy_host> <proxy_port>

# Ví dụ ProtonVPN:
./manage_gost.sh config 7891 protonvpn "node-uk-29.protonvpn.net" "node-uk-29.protonvpn.net" "4443"

# Ví dụ NordVPN:
./manage_gost.sh config 7892 nordvpn "us" "us1234.nordvpn.com" "89"

# Ví dụ WARP:
./manage_gost.sh config 7890 warp "cloudflare" "127.0.0.1" "8111"
```

### Xem cấu hình

```bash
# Xem tất cả cấu hình
./manage_gost.sh show-config

# Xem cấu hình instance cụ thể
./manage_gost.sh show-config 7891
```

## 📋 Format cấu hình

File config JSON (`config/gost_<port>.config`):

```json
{
  "port": "7891",
  "provider": "protonvpn",
  "country": "node-uk-29.protonvpn.net",
  "proxy_url": "https://user:pass@node-uk-29.protonvpn.net:4443",
  "proxy_host": "node-uk-29.protonvpn.net",
  "proxy_port": "4443",
  "created_at": "2025-01-27T10:30:00Z"
}
```

## 🔄 Quy trình khởi động

1. **Đọc cấu hình**: Load từ `config/gost_<port>.config`
2. **Cập nhật credentials**: Nếu là ProtonVPN, lấy credentials mới
3. **Tạo proxy URL**: Format `https://user:pass@host:port`
4. **Khởi động Gost**: `gost -L socks5://:port -F proxy_url`
5. **Lưu PID**: Lưu PID vào `logs/gost_<port>.pid`
6. **Monitor**: Tự động monitor và restart nếu down

## 🌐 Providers

### ProtonVPN

```bash
# Cấu hình
./manage_gost.sh config 7891 protonvpn "node-jp-10.protonvpn.net" "node-jp-10.protonvpn.net" "4453"

# Proxy URL format:
# https://username+password:password@node-jp-10.protonvpn.net:4453

# Port calculation:
# port = server_label + 4443
# Ví dụ: JP#10 → label=10 → port=4453
```

### NordVPN

```bash
# Cấu hình
./manage_gost.sh config 7892 nordvpn "us" "us1234.nordvpn.com" "89"

# Proxy URL format:
# https://USMbUonbFpF9xEx8xR3MHSau:buKKKPURZNMTW7A6rwm3qtBn@us1234.nordvpn.com:89

# Port: 89 (cố định cho NordVPN)
```

### Cloudflare WARP

```bash
# Cấu hình
./manage_gost.sh config 7890 warp "cloudflare" "127.0.0.1" "8111"

# Proxy URL format:
# socks5://127.0.0.1:8111

# Port 7890 được tối ưu với:
# - Timeout: 60s
# - Keepalive: enabled
```

## 🔍 Monitoring

### Gost Monitor

```bash
# Khởi động monitor
./gost_monitor.sh

# Monitor sẽ:
# - Kiểm tra Gost instances mỗi 60 giây
# - Restart nếu process down
# - Ghi logs vào logs/gost_monitor.log
```

### WARP Monitor

```bash
# Khởi động WARP monitor
./gost_7890_monitor.sh

# Monitor sẽ:
# - Kiểm tra Gost 7890 và WARP
# - Restart nếu down
# - Ghi logs vào logs/gost_7890_monitor.log
```

### Systemd Services

```bash
# Cài đặt services
sudo ./install_gostmonitor_systemd.sh
sudo ./install_gost7890monitor_systemd.sh

# Quản lý services
sudo systemctl start gost-monitor
sudo systemctl start gost-7890-monitor

# Xem logs
sudo journalctl -u gost-monitor -f
sudo journalctl -u gost-7890-monitor -f
```

## 🧪 Testing

### Test Gost Instance

```bash
# Test connection
curl -x socks5h://127.0.0.1:7891 https://api.ipify.org

# Test với timeout
curl --max-time 10 -x socks5h://127.0.0.1:7891 https://api.ipify.org

# Kiểm tra IP location
curl -x socks5h://127.0.0.1:7891 https://ipinfo.io/json
```

### Test Script

```bash
# Test tất cả instances
./test_gost.sh

# Output:
# Testing Gost 7890 (WARP)...
# ✅ Gost 7890: OK (IP: 1.2.3.4)
# Testing Gost 7891...
# ✅ Gost 7891: OK (IP: 5.6.7.8)
```

## 🔧 Advanced Configuration

### Custom Timeout

```bash
# Edit manage_gost.sh
# Tìm dòng:
nohup $GOST_BIN -D -L "socks5://:$port" -F "$proxy_url" > "$LOG_DIR/gost_${port}.log" 2>&1 &

# Thêm timeout:
nohup $GOST_BIN -D -L "socks5://:$port?ttl=60s" -F "$proxy_url" > "$LOG_DIR/gost_${port}.log" 2>&1 &
```

### Custom Keepalive

```bash
# Thêm keepalive:
nohup $GOST_BIN -D -L "socks5://:$port?so_keepalive=true" -F "$proxy_url" > "$LOG_DIR/gost_${port}.log" 2>&1 &
```

### Multiple Upstream Proxies

```bash
# Gost hỗ trợ chain proxies:
gost -L socks5://:7891 -F https://proxy1 -F https://proxy2
```

## 📊 Port Ranges

| Port | Usage |
|------|-------|
| 7890 | Cloudflare WARP (fallback) |
| 7891-7999 | Gost instances (109 instances) |

## 🐛 Troubleshooting

### Gost không khởi động

```bash
# Kiểm tra logs
tail -f logs/gost_7891.log

# Kiểm tra config
cat config/gost_7891.config

# Kiểm tra port
lsof -i :7891

# Test thủ công
gost -L socks5://:7891 -F "https://user:pass@host:port"
```

### Credentials không hoạt động

```bash
# ProtonVPN: Cập nhật credentials
./get_protonvpn_auth.sh

# Hoặc chạy auto updater
./start_auto_updater.sh

# NordVPN: Kiểm tra credentials trong manage_gost.sh
grep "USMbUonbFpF9xEx8xR3MHSau" manage_gost.sh
```

### Connection timeout

```bash
# Kiểm tra upstream proxy
curl -x https://user:pass@host:port https://api.ipify.org

# Tăng timeout trong Gost
# Edit manage_gost.sh, thêm ?ttl=120s

# Restart Gost
./manage_gost.sh restart
```

### Monitor không hoạt động

```bash
# Kiểm tra monitor process
ps aux | grep gost_monitor

# Xem logs
tail -f logs/gost_monitor.log

# Restart monitor
pkill -f gost_monitor.sh
./gost_monitor.sh &
```

## 🔐 Security

**Lưu ý:**
- Config files chứa credentials
- Không commit vào git
- Sử dụng .gitignore

**Khuyến nghị:**
- Encrypt config files
- Sử dụng environment variables
- Rotate credentials định kỳ

## 📝 Examples

### Example 1: Setup ProtonVPN instance

```bash
# 1. Cấu hình
./manage_gost.sh config 7891 protonvpn "node-jp-10.protonvpn.net" "node-jp-10.protonvpn.net" "4453"

# 2. Khởi động
./manage_gost.sh start

# 3. Test
curl -x socks5h://127.0.0.1:7891 https://api.ipify.org

# 4. Kiểm tra logs
tail -f logs/gost_7891.log
```

### Example 2: Setup NordVPN instance

```bash
# 1. Cấu hình
./manage_gost.sh config 7892 nordvpn "us" "us1234.nordvpn.com" "89"

# 2. Khởi động
./manage_gost.sh start

# 3. Test
curl -x socks5h://127.0.0.1:7892 https://api.ipify.org
```

### Example 3: Setup WARP fallback

```bash
# 1. Đảm bảo WARP đang chạy
warp-cli status

# 2. Cấu hình Gost 7890
./manage_gost.sh config 7890 warp "cloudflare" "127.0.0.1" "8111"

# 3. Khởi động
./manage_gost.sh start

# 4. Test
curl -x socks5h://127.0.0.1:7890 https://api.ipify.org
```

### Example 4: Multiple instances

```bash
# Setup 3 instances
./manage_gost.sh config 7891 protonvpn "node-jp-10.protonvpn.net" "node-jp-10.protonvpn.net" "4453"
./manage_gost.sh config 7892 nordvpn "us" "us1234.nordvpn.com" "89"
./manage_gost.sh config 7893 protonvpn "node-uk-29.protonvpn.net" "node-uk-29.protonvpn.net" "4443"

# Khởi động tất cả
./manage_gost.sh start

# Test tất cả
curl -x socks5h://127.0.0.1:7891 https://api.ipify.org  # JP IP
curl -x socks5h://127.0.0.1:7892 https://api.ipify.org  # US IP
curl -x socks5h://127.0.0.1:7893 https://api.ipify.org  # UK IP
```

## 🚀 Auto-start

### Systemd Service

```bash
# Cài đặt main service
sudo ./install_systemd_main.sh

# Service sẽ:
# - Khởi động tất cả Gost instances
# - Khởi động Web UI
# - Khởi động monitors

# Quản lý service
sudo systemctl start mac-proxy
sudo systemctl stop mac-proxy
sudo systemctl restart mac-proxy
sudo systemctl status mac-proxy

# Enable autostart
sudo systemctl enable mac-proxy
```

### Manual Autostart

```bash
# Thêm vào crontab
crontab -e

# Thêm dòng:
@reboot /path/to/mac_proxy/start_all.sh
```

## 📊 Performance

### Benchmarking

```bash
# Test latency
time curl -x socks5h://127.0.0.1:7891 https://api.ipify.org

# Test throughput
curl -x socks5h://127.0.0.1:7891 -o /dev/null https://speed.cloudflare.com/__down?bytes=100000000

# Test concurrent connections
for i in {1..10}; do
  curl -x socks5h://127.0.0.1:7891 https://api.ipify.org &
done
wait
```

### Optimization

- Sử dụng `ttl` để tăng timeout
- Sử dụng `so_keepalive` để duy trì connection
- Sử dụng multiple instances để load balance
- Monitor và restart tự động nếu down

