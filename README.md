# Hệ thống Proxy trên macOS

Hệ thống proxy với HAProxy, Wiresock (WireGuard SOCKS5 client) và Cloudflare WARP làm fallback.

## 🏗️ Kiến trúc

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  Client     │────────▶│  HAProxy 1   │────────▶│ Wiresock 1  │
│             │         │  Port 7891   │         │ Port 18181  │
└─────────────┘         └──────────────┘         └─────────────┘
                               │                         │
                               │ Fallback                │ Down
                               ▼                         ▼
                        ┌──────────────┐         ┌─────────────┐
                        │ Cloudflare   │◀────────│             │
                        │ WARP Proxy   │                       
                        │ Port 8111    │         
                        └──────────────┘         

┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  Client     │────────▶│  HAProxy 2   │────────▶│ Wiresock 2  │
│             │         │  Port 7892   │         │ Port 18182  │
└─────────────┘         └──────────────┘         └─────────────┘
                               │                         │
                               │ Fallback                │ Down
                               ▼                         ▼
                        ┌──────────────┐         ┌─────────────┐
                        │ Cloudflare   │◀────────│             │
                        │ WARP Proxy   │                       
                        │ Port 8111    │         
                        └──────────────┘         
```

## ✨ Tính năng chính

- ✅ **Auto-failover thông minh**: Tự động chuyển sang WARP khi Wiresock down
- ✅ **Health monitoring**: Kiểm tra backend mỗi 30 giây, chọn backend nhanh nhất
- ✅ **Dynamic reload**: HAProxy reload không downtime khi thay đổi backend
- ✅ **Multi-instance**: Chạy nhiều HAProxy instance độc lập
- ✅ **Stats dashboard**: Web UI theo dõi trạng thái real-time
- ✅ **External access**: Bind 0.0.0.0 cho phép truy cập từ mạng ngoài
- ✅ **Latency-based routing**: Tự động chọn backend có latency thấp nhất
- ✅ **Graceful degradation**: Fallback cascade từ WG → WARP
- ✅ **NordVPN Integration**: Tích hợp NordVPN với 5000+ servers, chọn server theo quốc gia

## 📋 Yêu cầu

- macOS 10.15 hoặc mới hơn
- Homebrew
- Quyền sudo (cho WireGuard)
- 3proxy (cho HTTPS proxy, optional)

## 🚀 Cài đặt nhanh

### 1. Cài đặt HAProxy và 3proxy

```bash
# macOS
brew install haproxy
brew install 3proxy  # Optional, cho HTTPS proxy

# Linux
sudo apt install haproxy  # Debian/Ubuntu
sudo apt install 3proxy   # Optional
sudo yum install haproxy  # CentOS/RHEL
```

### 2. Cấu hình Cloudflare WARP (Fallback)

```bash
# Tải và cài đặt từ: https://1.1.1.1/

# Đăng ký và kết nối
warp-cli register
warp-cli connect

# Cấu hình WARP làm SOCKS5 proxy trên cổng 8111
warp-cli set-mode proxy
warp-cli set-proxy-port 8111
```

### 3. Khởi động Wireproxy (WireGuard SOCKS5 Client)

**Wireproxy** là WireGuard client hỗ trợ SOCKS5 proxy.

**Lưu ý quan trọng:** Nếu bạn đang chạy wireproxy ở dự án khác trên cùng port, hệ thống sẽ tự động kill và restart.

```bash
# Kiểm tra port đang được sử dụng
./check_ports.sh

# Kill tất cả process trên port 18181 và 18182
./kill_ports.sh
```

**Cấu hình wireproxy:**

```bash
# Wireproxy config files (auto-generated when needed)
# Chỉnh sửa Endpoint trong file config để thay đổi server

# Ví dụ nội dung file:
[Interface]
PrivateKey = YOUR_PRIVATE_KEY
Address = 10.5.0.2/16
DNS = 8.8.8.8

[Peer]
PublicKey = SERVER_PUBLIC_KEY
Endpoint = 81.17.123.100:51820  # <-- Thay đổi IP:Port ở đây
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25

[Socks5]
BindAddress = 0.0.0.0:18181  # <-- Port cho wireproxy 1
```

### 4. Khởi động hệ thống

```bash
# Cấp quyền thực thi
chmod +x *.sh

# Khởi động tất cả (tự động kill port cũ và start wireproxy + HAProxy)
./start_all.sh

# Hoặc chỉ quản lý wireproxy
./manage_wireproxy.sh start   # Tự động kill port cũ trước khi start
./manage_wireproxy.sh stop
./manage_wireproxy.sh restart
./manage_wireproxy.sh status
```

## 📊 Sử dụng

### Web UI (Khuyến nghị) 🌐

```bash
# Khởi động Web UI
./start_webui.sh

# Truy cập: http://127.0.0.1:5000
```

**Tính năng Web UI:**
- ✅ Dashboard trực quan
- ✅ Start/Stop/Restart services
- ✅ Edit Wireproxy config (thay đổi server IP)
- ✅ View logs real-time
- ✅ Test proxy connections
- ✅ **NordVPN Server Selection** - Chọn server NordVPN theo quốc gia và áp dụng ngay

👉 Xem chi tiết: [WEBUI_README.md](WEBUI_README.md)

### Command Line

```bash
# Kiểm tra trạng thái
./status_all.sh

# Dừng hệ thống
./stop_all.sh

# Quản lý Wireproxy
./manage_wireproxy.sh start|stop|restart|status
```

### Test proxy

```bash
# Test tự động
./test_proxy.sh

# Test thủ công
curl -x socks5h://127.0.0.1:7891 https://api.ipify.org
curl -x socks5h://127.0.0.1:7892 https://api.ipify.org
```

### Sử dụng proxy trong ứng dụng

Cấu hình ứng dụng của bạn để sử dụng:

**SOCKS5 Proxy (HAProxy):**
- **HAProxy 1:** `socks5://127.0.0.1:7891` hoặc `socks5://0.0.0.0:7891` (external)
- **HAProxy 2:** `socks5://127.0.0.1:7892` hoặc `socks5://0.0.0.0:7892` (external)


### Xem HAProxy Stats Dashboard

Mở trình duyệt:
- **Instance 1:** http://127.0.0.1:8091/haproxy?stats
- **Instance 2:** http://127.0.0.1:8092/haproxy?stats
- **Username:** admin
- **Password:** admin123

### Xem logs

```bash
# Xem logs real-time
tail -f logs/haproxy_health_7891.log
tail -f logs/haproxy_health_7892.log

# Xem logs cả 2 instance
tail -f logs/haproxy_health_*.log
```

## 🔧 Cấu hình nâng cao

### Chạy instance tùy chỉnh

```bash
# Chạy HAProxy với cổng tùy chỉnh
./setup_haproxy.sh \
  --sock-port 7893 \
  --stats-port 8093 \
  --wg-ports 18181,18182 \
  --host-proxy 127.0.0.1:8111 \
  --stats-auth myuser:mypass \
  --health-interval 20 \
  --daemon
```

### Điều chỉnh health check interval

Trong `start_all.sh`, thay đổi `--health-interval`:

```bash
--health-interval 15  # Kiểm tra mỗi 15 giây (mặc định: 30)
```

### Thay đổi stats authentication

```bash
--stats-auth newuser:newpassword
```

### Bind vào interface cụ thể

Sửa trong `setup_haproxy.sh`, dòng:

```bash
bind 0.0.0.0:${SOCK_PORT}  # Tất cả interfaces
```

Thành:

```bash
bind 127.0.0.1:${SOCK_PORT}  # Chỉ localhost
```

### Sử dụng nhiều wiresock backends cho 1 HAProxy

```bash
./setup_haproxy.sh \
  --sock-port 7891 \
  --stats-port 8091 \
  --wg-ports 18181,18182,18183 \  # 3 backends
  --daemon
```

## 🔍 Troubleshooting

### HAProxy không khởi động

```bash
# Kiểm tra cấu hình
# Kiểm tra cấu hình HAProxy (nếu có)
ls config/haproxy_*.cfg | head -1 | xargs haproxy -f -c

# Xem logs
tail -f logs/haproxy_health_7891.log

# Kiểm tra port đã được sử dụng chưa
lsof -i :7891
```

### Wiresock không kết nối

```bash
# Kiểm tra wiresock đang chạy
ps aux | grep wiresock

# Test trực tiếp wiresock
curl -x socks5h://127.0.0.1:18181 https://api.ipify.org

# Khởi động lại wiresock
pkill wiresock-client
wiresock-client run -config wg1.conf -socks-bind 127.0.0.1:18181 &
```

### Cloudflare WARP không hoạt động

```bash
# Kiểm tra trạng thái
warp-cli status

# Kết nối lại
warp-cli disconnect
warp-cli connect

# Kiểm tra cổng proxy
lsof -i :8111
nc -zv 127.0.0.1 8111

# Test WARP proxy
curl -x socks5h://127.0.0.1:8111 https://api.ipify.org
```

### Health monitor không hoạt động

```bash
# Kiểm tra health monitor process
ps aux | grep setup_haproxy.sh

# Xem health monitor logs
tail -f logs/haproxy_health_*.log

# Khởi động lại
./stop_all.sh
./start_all.sh
```

### HAProxy luôn dùng fallback (WARP)

```bash
# Kiểm tra wiresock backends
./status_all.sh

# Test từng backend
curl -x socks5h://127.0.0.1:18181 https://api.ipify.org
curl -x socks5h://127.0.0.1:18182 https://api.ipify.org

# Xem HAProxy stats để biết backend nào down
open http://127.0.0.1:8091/haproxy?stats
```

## 📝 Cấu trúc thư mục

```
mac_proxy/
├── setup_haproxy.sh      # Script chính - khởi động HAProxy instance
├── start_all.sh          # Khởi động tất cả instances
├── stop_all.sh           # Dừng tất cả instances
├── status_all.sh         # Kiểm tra trạng thái
├── test_proxy.sh         # Test proxy endpoints
├── config/               # Thư mục cấu hình (auto-generated)
│   ├── haproxy_*.cfg     # HAProxy config files
│   └── gost_*.config     # Gost config files
├── logs/                 # Thư mục logs (auto-generated)
│   ├── haproxy_7891.pid
│   ├── haproxy_7892.pid
│   ├── haproxy_health_7891.log
│   ├── haproxy_health_7892.log
│   ├── health_7891.pid
│   └── health_7892.pid
├── wireguard/            # Thư mục cấu hình WireGuard/Wiresock
│   ├── wg1.conf
│   ├── wg2.conf
│   ├── wireproxy1.conf   # Nếu dùng wireproxy
│   └── wireproxy2.conf
└── README.md             # Tài liệu này
```

## 🌍 NordVPN Integration

Hệ thống đã tích hợp NordVPN với 5000+ servers trên 46 quốc gia.

### Quick Start

```bash
# List countries
bash apply_nordvpn.sh --list-countries

# List servers in Japan
bash apply_nordvpn.sh --list-servers JP

# Apply best server in Japan to Wireproxy 1
bash apply_nordvpn.sh --instance 1 --country JP

# Apply specific server to Wireproxy 2
bash apply_nordvpn.sh --instance 2 --server "Singapore #528"
```

### Sử dụng qua Web UI

1. Mở http://localhost:5000
2. Scroll xuống phần "🌍 NordVPN Server Selection"
3. Chọn quốc gia → Chọn server → Click "Apply to Wireproxy"

### CLI Commands

```bash
# List countries
python3 nordvpn_cli.py countries

# List servers by country
python3 nordvpn_cli.py servers --country JP --limit 20

# Get best server
python3 nordvpn_cli.py best --country SG

# Apply server
python3 nordvpn_cli.py apply 1 --server "Japan #720"
```

👉 Xem chi tiết: [NORDVPN.md](NORDVPN.md) | [NORDVPN_QUICKSTART.md](NORDVPN_QUICKSTART.md)






## 🛡️ Bảo mật

- Không chia sẻ file cấu hình WireGuard (chứa private key)
- Sử dụng firewall để giới hạn truy cập vào các cổng proxy
- Thường xuyên cập nhật các thành phần

## 📄 License

MIT License

## 🤝 Đóng góp

Mọi đóng góp đều được hoan nghênh! Vui lòng tạo issue hoặc pull request.

