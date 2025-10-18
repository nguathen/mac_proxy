# 🌐 Web UI - HAProxy & Wireproxy Manager

Web interface để quản lý hệ thống HAProxy và Wireproxy.

## ✨ Tính năng

- ✅ **Dashboard trực quan**: Xem trạng thái tất cả services real-time
- ✅ **Quản lý services**: Start/Stop/Restart HAProxy và Wireproxy
- ✅ **Edit config**: Thay đổi Wireproxy config (Endpoint, Keys, etc.)
- ✅ **View logs**: Xem logs của từng service
- ✅ **Test proxy**: Test kết nối proxy và xem IP
- ✅ **Auto-refresh**: Tự động cập nhật trạng thái mỗi 5 giây

## 🚀 Khởi động Web UI

### Cách 1: Sử dụng script

```bash
chmod +x start_webui.sh
./start_webui.sh
```

### Cách 2: Chạy thủ công

```bash
# Cài đặt dependencies
pip3 install -r webui/requirements.txt

# Khởi động Flask app
cd webui
python3 app.py
```

## 📱 Truy cập Web UI

Sau khi khởi động, mở trình duyệt:

- **Local**: http://127.0.0.1:5000
- **Network**: http://YOUR_IP:5000

## 🎯 Hướng dẫn sử dụng

### 1. Xem trạng thái services

Dashboard hiển thị:
- Wireproxy 1 & 2 (ports 18181, 18182)
- HAProxy 1 & 2 (ports 7891, 7892)
- Trạng thái: Running/Stopped
- PID của process
- Connection status

### 2. Quản lý services

**Wireproxy:**
- `Start All`: Khởi động cả 2 wireproxy instances
- `Stop All`: Dừng cả 2 wireproxy instances
- `Restart All`: Khởi động lại cả 2 instances

**HAProxy:**
- `Start All`: Khởi động cả 2 HAProxy instances
- `Stop All`: Dừng cả 2 HAProxy instances
- `Restart All`: Khởi động lại cả 2 instances

### 3. Edit Wireproxy Config

Click `Edit Wireproxy 1/2 Config` để:

1. **Thay đổi Interface:**
   - Private Key
   - Address
   - DNS

2. **Thay đổi Peer:**
   - Public Key
   - **Endpoint** (IP:Port của WireGuard server)
   - Allowed IPs
   - Persistent Keepalive

3. **Thay đổi SOCKS5:**
   - Bind Address (port)

4. Click `Save & Restart` để:
   - Lưu config mới
   - Backup config cũ
   - Tự động restart wireproxy

### 4. View Logs

Click `Logs` button trên mỗi service để xem:
- Wireproxy logs
- HAProxy health monitor logs
- 100 dòng logs gần nhất

### 5. Test Proxy

Click `Test` button để:
- Test kết nối proxy
- Xem IP public của proxy
- Kiểm tra proxy có hoạt động không

## 🔧 API Endpoints

Web UI cung cấp REST API:

### Status
```
GET /api/status
```
Trả về trạng thái tất cả services

### Wireproxy Control
```
POST /api/wireproxy/start
POST /api/wireproxy/stop
POST /api/wireproxy/restart
```

### HAProxy Control
```
POST /api/haproxy/start
POST /api/haproxy/stop
POST /api/haproxy/restart
```

### Config Management
```
GET  /api/wireproxy/config/1    # Get config
POST /api/wireproxy/config/1    # Save config
GET  /api/wireproxy/config/2
POST /api/wireproxy/config/2
```

### Logs
```
GET /api/logs/wireproxy1
GET /api/logs/wireproxy2
GET /api/logs/haproxy1
GET /api/logs/haproxy2
```

### Test Proxy
```
GET /api/test/proxy/18181
GET /api/test/proxy/18182
GET /api/test/proxy/7891
GET /api/test/proxy/7892
```

## 📁 Cấu trúc files

```
mac_proxy/
├── webui/
│   ├── app.py              # Flask application
│   ├── requirements.txt    # Python dependencies
│   └── templates/
│       └── index.html      # Web UI frontend
├── start_webui.sh          # Script khởi động Web UI
├── manage_wireproxy.sh     # Script quản lý wireproxy
├── wg18181.conf            # Wireproxy 1 config
└── wg18182.conf            # Wireproxy 2 config
```

## 🔒 Bảo mật

⚠️ **Lưu ý quan trọng:**

1. Web UI bind vào `0.0.0.0:5000` - có thể truy cập từ mạng ngoài
2. Không có authentication mặc định
3. Có thể xem và sửa Private Keys trong config

**Khuyến nghị:**

```python
# Trong webui/app.py, thay đổi:
app.run(host='127.0.0.1', port=5000)  # Chỉ local access
```

Hoặc sử dụng reverse proxy với authentication:

```nginx
# Nginx config
location / {
    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://127.0.0.1:5000;
}
```

## 🐛 Troubleshooting

### Web UI không khởi động

```bash
# Kiểm tra Python
python3 --version

# Cài đặt Flask
pip3 install Flask

# Kiểm tra port 5000 có bị dùng không
lsof -i :5000
```

### Không thể control services

```bash
# Kiểm tra quyền thực thi
chmod +x manage_wireproxy.sh
chmod +x start_all.sh
chmod +x stop_all.sh

# Kiểm tra scripts có chạy được không
./manage_wireproxy.sh status
```

### Config không save được

```bash
# Kiểm tra quyền ghi file
ls -la wg18181.conf wg18182.conf

# Kiểm tra backup folder
ls -la *.backup.*
```

## 📸 Screenshots

### Dashboard
- Hiển thị trạng thái tất cả services
- Nút Start/Stop/Restart
- Real-time status updates

### Config Editor
- Form nhập liệu thân thiện
- Validation
- Auto-restart sau khi save

### Logs Viewer
- Terminal-style logs
- Auto-scroll
- Color coding

## 🎨 Customization

### Thay đổi port Web UI

```python
# webui/app.py
app.run(host='0.0.0.0', port=8080)  # Đổi sang port 8080
```

### Thay đổi refresh interval

```javascript
// webui/templates/index.html
setInterval(loadStatus, 10000);  // Refresh mỗi 10 giây
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

## 🚀 Production Deployment

### Sử dụng Gunicorn

```bash
pip3 install gunicorn

# Chạy với Gunicorn
cd webui
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Systemd Service

```ini
# /etc/systemd/system/haproxy-webui.service
[Unit]
Description=HAProxy WebUI
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
sudo systemctl enable haproxy-webui
sudo systemctl start haproxy-webui
```

## 📝 Changelog

### Version 1.0.0 (2025-10-18)
- ✅ Initial release
- ✅ Service management
- ✅ Config editor
- ✅ Logs viewer
- ✅ Proxy testing
- ✅ Real-time status updates

