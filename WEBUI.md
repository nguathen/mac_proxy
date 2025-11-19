# Web UI - Gost Proxy Manager

Giao diện web để quản lý hệ thống Gost proxy.

## ✨ Tính năng

- ✅ **Dashboard**: Xem trạng thái tất cả Gost instances
- ✅ **Quản lý Gost**: Start/Stop/Restart instances
- ✅ **NordVPN**: Chọn và áp dụng server NordVPN
- ✅ **ProtonVPN**: Chọn và áp dụng server ProtonVPN
- ✅ **Chrome API**: Tự động tạo proxy cho Chrome profiles
- ✅ **View Logs**: Xem logs real-time
- ✅ **Test Proxy**: Test kết nối và xem IP
- ✅ **Auto-refresh**: Cập nhật trạng thái tự động

## 🚀 Khởi động

### Cách 1: Daemon mode (Khuyến nghị)

```bash
./start_webui_daemon.sh
```

### Cách 2: Foreground mode

```bash
cd webui
python3 app.py
```

### Cách 3: Systemd service (Linux)

```bash
# Đã được cài đặt bởi install_linux.sh
sudo systemctl start mac-proxy
sudo systemctl status mac-proxy
```

## 📱 Truy cập

- **Local**: http://127.0.0.1:5000
- **Network**: http://YOUR_IP:5000

## 🎯 Sử dụng

### 1. Dashboard

**Hiển thị:**
- Danh sách Gost instances (7890, 7891, 7892, ...)
- Trạng thái: Running/Stopped
- PID của process
- Cấu hình: Provider, Country, Proxy URL

**Thao tác:**
- Start/Stop/Restart từng instance
- Start/Stop/Restart tất cả instances
- Xem logs
- Test connection

### 2. NordVPN

**Chọn server:**
1. Chọn quốc gia từ dropdown
2. Danh sách servers hiển thị (sắp xếp theo load)
3. Xem thông tin server: hostname, load, location
4. Chọn Gost port (7891, 7892, ...)
5. Click "Apply to Gost"

**Kết quả:**
- Server được áp dụng vào Gost instance
- Gost tự động restart
- Test connection tự động

### 3. ProtonVPN

**API Mode:**
1. Đảm bảo đã cấu hình credentials (xem README.md)
2. Chọn quốc gia
3. Chọn server (hiển thị tier, load, score)
4. Chọn Gost port
5. Click "Apply to Gost"

**Config Mode:**
- Scan local config files từ `protonvpn_configs/`
- Chọn config và áp dụng

### 4. Chrome API

**Tự động:**
- Chrome extension gửi request tới `/api/chrome/proxy-check`
- Web UI tự động tạo Gost instance nếu cần
- Trả về proxy URL cho Chrome

**Thủ công:**
```bash
curl -X POST http://localhost:5000/api/chrome/proxy-check \
  -H "Content-Type: application/json" \
  -d '{
    "proxy_check": "socks5://server:7891:vn42.nordvpn.com:",
    "data": {"count": 0, "profiles": []}
  }'
```

### 5. Logs Viewer

**Xem logs:**
- Click "View Logs" trên instance
- Hiển thị 100 dòng logs gần nhất
- Auto-scroll xuống cuối
- Refresh để cập nhật

**Logs bao gồm:**
- Gost startup logs
- Connection logs
- Error logs
- Credential update logs

### 6. Test Proxy

**Test connection:**
- Click "Test" trên instance
- Hiển thị IP public
- Hiển thị response time
- Hiển thị lỗi nếu có

## 🔧 API Endpoints

### Status

```bash
# Lấy trạng thái tất cả instances
GET /api/status

# Response:
{
  "gost_instances": [
    {
      "port": "7891",
      "running": true,
      "pid": 12345,
      "config": {
        "provider": "protonvpn",
        "country": "node-uk-29.protonvpn.net",
        "proxy_url": "https://..."
      }
    }
  ]
}
```

### Gost Control

```bash
# Khởi động tất cả
POST /api/gost/start

# Dừng tất cả
POST /api/gost/stop

# Restart tất cả
POST /api/gost/restart

# Khởi động instance cụ thể
POST /api/gost/7891/start

# Dừng instance cụ thể
POST /api/gost/7891/stop

# Restart instance cụ thể
POST /api/gost/7891/restart
```

### Config Management

```bash
# Lấy cấu hình
GET /api/gost/config/7891

# Response:
{
  "port": "7891",
  "provider": "protonvpn",
  "country": "node-uk-29.protonvpn.net",
  "proxy_url": "https://...",
  "proxy_host": "node-uk-29.protonvpn.net",
  "proxy_port": "4443",
  "created_at": "2025-01-27T10:30:00Z"
}

# Lưu cấu hình
POST /api/gost/config/7891
Content-Type: application/json

{
  "provider": "nordvpn",
  "country": "us",
  "proxy_host": "us.nordvpn.com",
  "proxy_port": "89"
}
```

### Logs

```bash
# Xem logs instance
GET /api/logs/gost/7891

# Response:
{
  "success": true,
  "logs": "2025-01-27 10:30:00 Starting gost...\n..."
}
```

### Test Proxy

```bash
# Test instance
GET /api/test/proxy/7891

# Response:
{
  "success": true,
  "ip": "1.2.3.4",
  "response_time": 0.5
}
```

### NordVPN API

```bash
# Lấy danh sách quốc gia
GET /api/nordvpn/countries

# Lấy servers theo quốc gia
GET /api/nordvpn/servers/JP

# Lấy best server
GET /api/nordvpn/best?country=US

# Áp dụng server
POST /api/nordvpn/apply/7891
Content-Type: application/json

{
  "server_name": "Japan #720"
}
```

### ProtonVPN API

```bash
# Lấy danh sách quốc gia
GET /api/protonvpn/countries

# Lấy servers theo quốc gia
GET /api/protonvpn/servers/JP

# Lấy best server
GET /api/protonvpn/best?country=JP&tier=2

# Áp dụng server
POST /api/protonvpn/apply/7891
Content-Type: application/json

{
  "server_name": "JP#10"
}
```

### Chrome API

```bash
# Kiểm tra và tạo proxy
POST /api/chrome/proxy-check
Content-Type: application/json

{
  "proxy_check": "socks5://server:7891:vn42.nordvpn.com:",
  "data": {
    "count": 1,
    "profiles": [
      {"id": 1, "name": "Profile 1", "proxy": "127.0.0.1:7891:vn42.nordvpn.com"}
    ]
  }
}

# Response:
{
  "success": true,
  "message": "Created new Gost on port 7891",
  "proxy_check": "socks5://127.0.0.1:7891:vn42.nordvpn.com:",
  "action": "created_new",
  "port": 7891,
  "server": "vn42.nordvpn.com"
}
```

## 📁 Cấu trúc

```
webui/
├── app.py                    # Flask application
├── gost_handler.py           # Gost API handler
├── nordvpn_handler.py        # NordVPN API handler
├── protonvpn_handler.py      # ProtonVPN API handler
├── chrome_handler.py         # Chrome API handler
├── requirements.txt          # Python dependencies
└── templates/
    └── index.html            # Frontend UI
```

## 🔒 Bảo mật

**Lưu ý:**
- Web UI bind vào `0.0.0.0:5000` - có thể truy cập từ mạng ngoài
- Không có authentication mặc định
- Có thể xem proxy credentials trong logs

**Khuyến nghị:**

1. **Chỉ bind localhost:**
```python
# webui/app.py
app.run(host='127.0.0.1', port=5000)
```

2. **Sử dụng reverse proxy với auth:**
```nginx
location / {
    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://127.0.0.1:5000;
}
```

3. **Firewall:**
```bash
# Chỉ cho phép localhost
sudo ufw deny 5000
sudo ufw allow from 127.0.0.1 to any port 5000
```

## 🐛 Troubleshooting

### Web UI không khởi động

```bash
# Kiểm tra Python
python3 --version

# Cài đặt dependencies
pip3 install -r webui/requirements.txt

# Kiểm tra port 5000
lsof -i :5000

# Kill process cũ
lsof -ti :5000 | xargs kill -9
```

### Không thể control Gost

```bash
# Kiểm tra quyền thực thi
chmod +x manage_gost.sh

# Kiểm tra Gost binary
which gost

# Test thủ công
./manage_gost.sh status
```

### NordVPN/ProtonVPN không load servers

```bash
# Kiểm tra cache files
ls -la nordvpn_servers_cache.json
ls -la protonvpn_servers_cache.json

# Xóa cache để force refresh
rm nordvpn_servers_cache.json
rm protonvpn_servers_cache.json

# Restart Web UI
./start_webui_daemon.sh
```

### ProtonVPN credentials không hoạt động

```bash
# Kiểm tra credentials file
cat protonvpn_credentials.json

# Lấy credentials mới từ browser
# (Xem hướng dẫn trong README.md)

# Restart Web UI
./start_webui_daemon.sh
```

## 🎨 Customization

### Thay đổi port

```python
# webui/app.py
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
```

### Thay đổi refresh interval

```javascript
// webui/templates/index.html
setInterval(loadStatus, 10000);  // 10 giây
```

### Thêm authentication

```python
# webui/app.py
from flask_httpauth import HTTPBasicAuth

auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    return username == 'admin' and password == 'secret'

@app.route('/')
@auth.login_required
def index():
    return render_template('index.html')
```

## 📊 Monitoring

### Systemd logs

```bash
# Web UI logs
sudo journalctl -u mac-proxy -f

# Gost monitor logs
sudo journalctl -u gost-monitor -f

# WARP monitor logs
sudo journalctl -u gost-7890-monitor -f
```

### Application logs

```bash
# Gost logs
tail -f logs/gost_7891.log
tail -f logs/gost_7892.log

# Web UI logs
tail -f logs/webui.log
```

## 🚀 Production Deployment

### Gunicorn

```bash
pip3 install gunicorn

cd webui
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Systemd service

```ini
[Unit]
Description=Gost Web UI
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/mac_proxy/webui
ExecStart=/usr/bin/python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable gost-webui
sudo systemctl start gost-webui
```

