# Hệ thống Gost Proxy

Hệ thống proxy sử dụng Gost với hỗ trợ NordVPN, ProtonVPN và Cloudflare WARP.

## 🏗️ Kiến trúc

```
┌─────────────┐         ┌──────────────┐         ┌─────────────────┐
│  Client     │────────▶│  Gost Proxy  │────────▶│ NordVPN/Proton  │
│             │         │  Port 7891+  │         │ HTTPS Proxy     │
└─────────────┘         └──────────────┘         └─────────────────┘

┌─────────────┐         ┌──────────────┐         ┌─────────────────┐
│  Client     │────────▶│  Gost 7890   │────────▶│ Cloudflare WARP │
│             │         │  (Fallback)  │         │ Port 8111       │
└─────────────┘         └──────────────┘         └─────────────────┘
```

## ✨ Tính năng

- ✅ **Gost Proxy**: SOCKS5 proxy với khả năng forward tới upstream proxy
- ✅ **Multi-instance**: Hỗ trợ nhiều Gost instances (port 7891-7999)
- ✅ **NordVPN Integration**: 5000+ servers, chọn theo quốc gia
- ✅ **ProtonVPN Integration**: API mode và config mode
- ✅ **Cloudflare WARP**: Fallback proxy trên port 7890
- ✅ **Web UI**: Quản lý qua giao diện web
- ✅ **Chrome API**: Tự động tạo proxy cho Chrome profiles
- ✅ **Auto-recovery**: Tự động khôi phục cấu hình khi restart
- ✅ **Systemd Services**: Chạy như system service trên Linux

## 📋 Yêu cầu

- Linux (Ubuntu/Debian) hoặc macOS
- Gost (`brew install gost` hoặc download từ GitHub)
- Python 3.8+
- Cloudflare WARP (optional, cho fallback)

## 🚀 Cài đặt

### Linux (Systemd)

```bash
# Cài đặt tự động
sudo ./install_linux.sh

# Script sẽ:
# - Cài đặt Gost
# - Tạo systemd services
# - Cấu hình autostart
# - Khởi động Web UI
```

### macOS

```bash
# Cài đặt Gost
brew install gost

# Cài đặt Python dependencies
pip3 install -r webui/requirements.txt

# Khởi động hệ thống
./start_all.sh
```

## 🎯 Sử dụng

### 1. Khởi động hệ thống

```bash
# Khởi động tất cả
./start_all.sh

# Kiểm tra trạng thái
./status_all.sh

# Dừng tất cả
./stop_all.sh
```

### 2. Web UI

```bash
# Khởi động Web UI
./start_webui_daemon.sh

# Truy cập: http://localhost:5000
```

**Tính năng Web UI:**
- Dashboard hiển thị trạng thái Gost instances
- Quản lý Gost: Start/Stop/Restart
- Chọn server NordVPN/ProtonVPN
- Xem logs real-time
- Test proxy connections
- Chrome API integration

### 3. Quản lý Gost

```bash
# Khởi động/dừng/restart
./manage_gost.sh start
./manage_gost.sh stop
./manage_gost.sh restart

# Kiểm tra trạng thái
./manage_gost.sh status

# Cấu hình instance
./manage_gost.sh config <port> <provider> <country> <proxy_host> <proxy_port>

# Ví dụ:
./manage_gost.sh config 7891 protonvpn "node-uk-29.protonvpn.net" "node-uk-29.protonvpn.net" "4443"
./manage_gost.sh config 7892 nordvpn "us" "us.nordvpn.com" "89"

# Xem cấu hình
./manage_gost.sh show-config
```

### 4. Test Proxy

```bash
# Test proxy
curl -x socks5h://127.0.0.1:7891 https://api.ipify.org
curl -x socks5h://127.0.0.1:7892 https://api.ipify.org

# Test WARP fallback
curl -x socks5h://127.0.0.1:7890 https://api.ipify.org
```

## 🌍 NordVPN

### Qua Web UI
1. Mở http://localhost:5000
2. Chọn tab "NordVPN"
3. Chọn quốc gia → Chọn server
4. Click "Apply to Gost"

### Qua API
```bash
# Lấy danh sách quốc gia
curl http://localhost:5000/api/nordvpn/countries

# Lấy servers theo quốc gia
curl http://localhost:5000/api/nordvpn/servers/JP

# Lấy best server
curl http://localhost:5000/api/nordvpn/best?country=US

# Áp dụng server
curl -X POST http://localhost:5000/api/nordvpn/apply/7891 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "Japan #720"}'
```

## 🔐 ProtonVPN

### API Mode (Khuyến nghị)

1. Lấy credentials từ ProtonVPN web:
   - Login vào https://account.protonvpn.com/
   - Mở DevTools (F12) → Network tab
   - Tìm API request, copy `Authorization: Bearer <token>` và `x-pm-uid`

2. Tạo file credentials:
```bash
cat > protonvpn_credentials.json <<EOF
{
  "bearer_token": "your_token_here",
  "uid": "your_uid_here"
}
EOF
```

3. Restart Web UI:
```bash
./start_webui_daemon.sh
```

### Qua Web UI
1. Mở http://localhost:5000
2. Chọn tab "ProtonVPN"
3. Chọn quốc gia → Chọn server
4. Click "Apply to Gost"

### Qua API
```bash
# Lấy servers
curl http://localhost:5000/api/protonvpn/servers

# Lấy best server
curl http://localhost:5000/api/protonvpn/best?country=JP&tier=2

# Áp dụng server
curl -X POST http://localhost:5000/api/protonvpn/apply/7891 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "JP#10"}'
```

## 🌐 Chrome API

API tự động tạo Gost proxy cho Chrome profiles.

### Endpoint
```
POST /api/chrome/proxy-check
```

### Request
```json
{
  "proxy_check": "socks5://server:7891:vn42.nordvpn.com:",
  "data": {
    "count": 1,
    "profiles": [
      {"id": 1, "name": "Profile 1", "proxy": "127.0.0.1:7891:vn42.nordvpn.com"}
    ]
  }
}
```

### Response
```json
{
  "success": true,
  "message": "Created new Gost on port 7891",
  "proxy_check": "socks5://127.0.0.1:7891:vn42.nordvpn.com:",
  "action": "created_new",
  "port": 7891,
  "server": "vn42.nordvpn.com"
}
```

## 🔧 Cấu hình nâng cao

### Systemd Services

```bash
# Cài đặt services
sudo ./install_systemd_main.sh      # Main service
sudo ./install_gostmonitor_systemd.sh  # Gost monitor
sudo ./install_gost7890monitor_systemd.sh  # WARP monitor
sudo ./install_auto_updater_systemd.sh  # Auto credential updater

# Quản lý services
sudo systemctl start mac-proxy
sudo systemctl stop mac-proxy
sudo systemctl status mac-proxy

# Xem logs
sudo journalctl -u mac-proxy -f
sudo journalctl -u gost-monitor -f
```

### Cloudflare WARP

```bash
# Cài đặt WARP
# Download từ: https://1.1.1.1/

# Cấu hình
warp-cli register
warp-cli set-mode proxy
warp-cli set-proxy-port 8111
warp-cli connect

# Kiểm tra
curl -x socks5h://127.0.0.1:8111 https://api.ipify.org
```

### Auto Credential Updater

```bash
# Tự động cập nhật ProtonVPN credentials mỗi 30 phút
sudo systemctl start auto-credential-updater
sudo systemctl enable auto-credential-updater
```

## 📁 Cấu trúc

```
mac_proxy/
├── config/                    # Cấu hình Gost instances
│   ├── gost_7890.config       # WARP fallback
│   ├── gost_7891.config       # Instance 1
│   └── gost_7892.config       # Instance 2
├── logs/                      # Logs và PID files
│   ├── gost_7890.log
│   ├── gost_7890.pid
│   └── ...
├── webui/                     # Web UI
│   ├── app.py                 # Flask app
│   ├── gost_handler.py        # Gost API handler
│   ├── nordvpn_handler.py     # NordVPN API handler
│   ├── protonvpn_handler.py   # ProtonVPN API handler
│   └── chrome_handler.py      # Chrome API handler
├── manage_gost.sh             # Quản lý Gost
├── start_all.sh               # Khởi động hệ thống
├── stop_all.sh                # Dừng hệ thống
├── status_all.sh              # Kiểm tra trạng thái
├── install_linux.sh           # Cài đặt tự động (Linux)
└── *.service                  # Systemd service files
```

## 🔍 Troubleshooting

### Gost không khởi động
```bash
# Kiểm tra logs
tail -f logs/gost_7891.log

# Kiểm tra port
lsof -i :7891

# Restart
./manage_gost.sh restart
```

### ProtonVPN credentials expired
```bash
# Cập nhật credentials thủ công
./get_protonvpn_auth.sh

# Hoặc chạy auto updater
./start_auto_updater.sh
```

### WARP không hoạt động
```bash
# Kiểm tra WARP
warp-cli status

# Kết nối lại
warp-cli disconnect
warp-cli connect

# Test
curl -x socks5h://127.0.0.1:8111 https://api.ipify.org
```

## 📝 Port Ranges

- **7890**: Cloudflare WARP fallback
- **7891-7999**: Gost proxy instances (SOCKS5)
- **5000**: Web UI
- **8111**: Cloudflare WARP SOCKS5

## 📄 License

MIT License

