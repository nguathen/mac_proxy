# HTTPS Proxy Integration

Hệ thống đã được tích hợp thêm HTTPS proxy sử dụng 3proxy, hoạt động song song với Wireproxy SOCKS5.

## Kiến trúc

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  Client     │────────▶│  HAProxy 1   │────────▶│ Wireproxy 1 │
│             │         │  Port 7891   │         │ Port 18181  │
│             │         │  (SOCKS5)    │         │ (SOCKS5)    │
└─────────────┘         └──────────────┘         └─────────────┘

┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  Client     │────────▶│ HTTPS Proxy 1│────────▶│ WireGuard   │
│             │         │  Port 8181   │         │ Tunnel      │
│             │         │  (HTTP/S)    │         │             │
└─────────────┘         └──────────────┘         └─────────────┘
```

## Cài đặt

### 1. Cài đặt 3proxy

```bash
# macOS
brew install 3proxy

# Linux (Ubuntu/Debian)
sudo apt install 3proxy

# Linux (CentOS/RHEL)
sudo yum install 3proxy
```

### 2. Khởi động HTTPS Proxy

```bash
# Khởi động tất cả (bao gồm HTTPS proxy)
./start_all.sh

# Hoặc chỉ khởi động HTTPS proxy
./manage_https_proxy.sh start
```

## Sử dụng

### Proxy Endpoints

- **HTTPS Proxy 1:** `http://127.0.0.1:8181` hoặc `http://0.0.0.0:8181` (external)
- **HTTPS Proxy 2:** `http://127.0.0.1:8182` hoặc `http://0.0.0.0:8182` (external)

### Test Proxy

```bash
# Test tự động
./test_https_proxy.sh

# Test thủ công
curl -x http://127.0.0.1:8181 https://api.ipify.org
curl -x http://127.0.0.1:8182 https://api.ipify.org

# Test với HTTP
curl -x http://127.0.0.1:8181 http://api.ipify.org

# Test với ipinfo
curl -x http://127.0.0.1:8181 https://ipinfo.io/json
```

### Sử dụng trong ứng dụng

#### Python (requests)

```python
import requests

proxies = {
    'http': 'http://127.0.0.1:8181',
    'https': 'http://127.0.0.1:8181',
}

response = requests.get('https://api.ipify.org', proxies=proxies)
print(f"Your IP: {response.text}")
```

#### Node.js

```javascript
const axios = require('axios');

const proxy = {
  host: '127.0.0.1',
  port: 8181,
  protocol: 'http'
};

axios.get('https://api.ipify.org', { proxy })
  .then(response => console.log('Your IP:', response.data))
  .catch(error => console.error('Error:', error));
```

#### cURL

```bash
# HTTP request
curl -x http://127.0.0.1:8181 http://example.com

# HTTPS request
curl -x http://127.0.0.1:8181 https://example.com

# With authentication (if configured)
curl -x http://user:pass@127.0.0.1:8181 https://example.com
```

#### Browser (Chrome/Firefox)

```bash
# Chrome
google-chrome --proxy-server="http://127.0.0.1:8181"

# Firefox (via about:preferences -> Network Settings)
# Manual proxy configuration:
# HTTP Proxy: 127.0.0.1, Port: 8181
# Use this proxy server for all protocols: checked
```

## Quản lý

### Lệnh quản lý

```bash
# Khởi động
./manage_https_proxy.sh start

# Dừng
./manage_https_proxy.sh stop

# Khởi động lại
./manage_https_proxy.sh restart

# Kiểm tra trạng thái
./manage_https_proxy.sh status
```

### Kiểm tra trạng thái hệ thống

```bash
# Kiểm tra tất cả services
./status_all.sh

# Dừng tất cả
./stop_all.sh
```

### Xem logs

```bash
# Logs của HTTPS proxy
tail -f logs/https_proxy_8181.log
tail -f logs/https_proxy_8182.log

# Logs stdout/stderr
tail -f logs/https_proxy_8181_stdout.log
tail -f logs/https_proxy_8182_stdout.log
```

## Cấu hình

### Cấu hình 3proxy

File cấu hình được tạo tự động tại `https_config/3proxy_<port>.cfg`:

```
daemon
maxconn 1024
nscache 65536
timeouts 1 5 30 60 180 1800 15 60
log "logs/https_proxy_<port>.log" D
logformat "- +_L%t.%. %N.%p %E %U %C:%c %R:%r %O %I %h %T"
auth none
allow *

proxy -p<port> -a -n -i0.0.0.0 -e0.0.0.0
flush
```

### Thay đổi port

Chỉnh sửa trong `manage_https_proxy.sh`:

```bash
HTTPS_PORT_1=8181  # Thay đổi port này
HTTPS_PORT_2=8182  # Thay đổi port này
```

### Thêm authentication

Chỉnh sửa hàm `create_3proxy_config` trong `manage_https_proxy.sh`:

```bash
cat > "$config_file" <<EOF
daemon
maxconn 1024
auth strong
users username:CL:password
allow username
proxy -p${port} -a -n -i0.0.0.0 -e0.0.0.0
flush
EOF
```

## So sánh SOCKS5 vs HTTPS Proxy

| Tính năng | SOCKS5 (HAProxy + Wireproxy) | HTTPS Proxy (3proxy) |
|-----------|------------------------------|----------------------|
| Protocol | SOCKS5 | HTTP/HTTPS |
| Port | 7891, 7892 | 8181, 8182 |
| Failover | Có (WARP fallback) | Không |
| Health monitoring | Có | Không |
| Tương thích | Ứng dụng hỗ trợ SOCKS5 | Hầu hết ứng dụng web |
| Performance | Cao | Cao |
| Cấu hình | Phức tạp | Đơn giản |

## Troubleshooting

### HTTPS proxy không khởi động

```bash
# Kiểm tra 3proxy đã cài đặt
which 3proxy

# Kiểm tra port đã được sử dụng
lsof -i :8181
lsof -i :8182

# Xem logs
tail -f logs/https_proxy_8181.log
```

### Proxy không kết nối

```bash
# Kiểm tra proxy đang chạy
./manage_https_proxy.sh status

# Test trực tiếp
curl -v -x http://127.0.0.1:8181 https://api.ipify.org

# Kiểm tra firewall
# macOS
sudo pfctl -sr | grep 8181

# Linux
sudo iptables -L -n | grep 8181
```

### Port conflict

```bash
# Kill process đang sử dụng port
lsof -ti :8181 | xargs kill -9
lsof -ti :8182 | xargs kill -9

# Khởi động lại
./manage_https_proxy.sh restart
```

## Tích hợp với Web UI

Web UI hiện tại chưa hỗ trợ quản lý HTTPS proxy. Sử dụng CLI để quản lý:

```bash
# Kiểm tra trạng thái
./status_all.sh

# Quản lý HTTPS proxy
./manage_https_proxy.sh start|stop|restart|status
```

## Performance

### Benchmarks

```bash
# Test throughput với SOCKS5
time curl -x socks5h://127.0.0.1:7891 https://speed.cloudflare.com/__down?bytes=10000000 -o /dev/null

# Test throughput với HTTPS proxy
time curl -x http://127.0.0.1:8181 https://speed.cloudflare.com/__down?bytes=10000000 -o /dev/null
```

### Tối ưu hóa

1. **Tăng maxconn**: Chỉnh sửa `maxconn` trong config
2. **Tăng buffer**: Thêm `sysctl` settings
3. **Sử dụng nhiều instances**: Chạy nhiều 3proxy instances trên các port khác nhau

## Roadmap

- [ ] Tích hợp HTTPS proxy vào Web UI
- [ ] Thêm authentication cho HTTPS proxy
- [ ] Health monitoring cho HTTPS proxy
- [ ] Failover support cho HTTPS proxy
- [ ] Load balancing giữa nhiều HTTPS proxy instances

