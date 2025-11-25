# ProtonVPN Integration

Hệ thống hỗ trợ ProtonVPN với 2 modes: API mode và Config mode.

## 🚀 API Mode (Khuyến nghị)

Fetch servers trực tiếp từ ProtonVPN API.

### Setup

**1. Lấy credentials từ ProtonVPN web:**

- Login vào https://account.protonvpn.com/
- Mở Browser DevTools (F12) → Network tab
- Reload page hoặc navigate
- Tìm API request (ví dụ: `/vpn/logicals`)
- Copy headers:
  - `Authorization: Bearer <token>` → Lấy token
  - `x-pm-uid: <uid>` → Lấy UID

**2. Tạo credentials file:**

```bash
cat > protonvpn_credentials.json <<EOF
{
  "bearer_token": "wqs7vr3zn5oaoquqgcg5i3mp6momlnk7",
  "uid": "m46kiazjmmiun2lzuxafbdavegwvsyhm"
}
EOF
```

**3. Restart Web UI:**

```bash
./start_webui_daemon.sh
```

### Sử dụng

**Qua Web UI:**
1. Mở http://localhost:5000
2. Chọn tab "ProtonVPN"
3. Chọn country → Chọn server
4. Chọn Gost port
5. Click "Apply to Gost"

**Qua API:**

```bash
# Lấy danh sách servers
curl http://localhost:5000/api/protonvpn/servers

# Lấy servers theo quốc gia
curl http://localhost:5000/api/protonvpn/servers/JP

# Lấy best server
curl http://localhost:5000/api/protonvpn/best?country=JP&tier=2

# Áp dụng server
curl -X POST http://localhost:5000/api/protonvpn/apply/7891 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "JP#10"}'
```

## 📁 Config Mode (Fallback)

Scan local WireGuard config files.

### Setup

**1. Download configs từ ProtonVPN:**

- Login vào https://account.protonvpn.com/
- Vào **Downloads** → **WireGuard configuration**
- Chọn platform: **Linux** hoặc **Router**
- Download `.conf` files

**2. Place configs:**

```bash
mkdir -p protonvpn_configs
cp ~/Downloads/US-FREE#1.conf protonvpn_configs/
cp ~/Downloads/JP#10.conf protonvpn_configs/
```

**3. Scan configs:**

- Mở Web UI
- Click "Scan Configs" button

### Sử dụng

- Chọn country → Chọn config → Apply
- Configs được scan từ `protonvpn_configs/` directory

## 📊 So sánh 2 modes

| Feature | API Mode | Config Mode |
|---------|----------|-------------|
| Setup | Cần credentials | Cần download configs |
| Server count | Tất cả servers | Chỉ configs đã download |
| Auto update | Cache 1 giờ | Manual scan |
| Best server | ✅ Có | ❌ Không |
| Filter by tier | ✅ Có | ❌ Không |
| Load info | ✅ Có | ❌ Không |

## 🔧 API Endpoints

### API Mode

```bash
# Lấy tất cả servers
GET /api/protonvpn/servers

# Response:
{
  "success": true,
  "servers": [
    {
      "name": "JP#10",
      "domain": "node-jp-10.protonvpn.net",
      "tier": 2,
      "load": 15,
      "score": 1.5,
      "country": "JP",
      "location": "Tokyo"
    }
  ]
}

# Lấy servers theo quốc gia
GET /api/protonvpn/servers/US

# Lấy best server
GET /api/protonvpn/best?country=JP&tier=2

# Áp dụng server
POST /api/protonvpn/apply/7891
Content-Type: application/json

{
  "server_name": "JP#10"
}
```

### Config Mode

```bash
# Lấy tất cả configs
GET /api/protonvpn/configs

# Lấy configs theo quốc gia
GET /api/protonvpn/configs/US

# Áp dụng config
POST /api/protonvpn/apply/7891
Content-Type: application/json

{
  "config_name": "US-FREE#1"
}
```

### Hybrid (Auto-detect)

```bash
# Lấy countries (API mode nếu có, fallback to configs)
GET /api/protonvpn/countries
```

## 🔐 Credentials

### Lấy credentials tự động

ProtonVPN sử dụng script `get_protonvpn_auth.sh` để lấy credentials:

```bash
# Chạy thủ công
./get_protonvpn_auth.sh

# Output:
username+password:password
```

### Auto-update credentials

```bash
# Khởi động auto updater
./start_auto_updater.sh

# Hoặc cài đặt systemd service
sudo ./install_auto_updater_systemd.sh
sudo systemctl start auto-credential-updater

# Credentials sẽ được cập nhật mỗi 30 phút
```

### Credentials format

ProtonVPN credentials format:
- Username: `username+password`
- Password: `password`
- Proxy URL: `https://username+password:password@domain:port`

Port được tính từ server label:
- Port = `server_label + 4443`
- Ví dụ: Server label 10 → Port 4453

## 🌍 Tiers

ProtonVPN có 3 tiers:

| Tier | Plan | Servers | Speed |
|------|------|---------|-------|
| 0 | Free | Limited | Slower |
| 1 | Basic | More | Good |
| 2 | Plus/Visionary | All | Fastest |

**Filter by tier:**

```bash
# Best free server
curl http://localhost:5000/api/protonvpn/best?tier=0

# Best plus server in US
curl http://localhost:5000/api/protonvpn/best?country=US&tier=2
```

## 🔄 Cache

Danh sách servers được cache trong `protonvpn_servers_cache.json` với thời gian 1 giờ.

**Force refresh:**

```bash
# Xóa cache
rm protonvpn_servers_cache.json

# Restart Web UI
./start_webui_daemon.sh

# Hoặc gọi API với refresh=true
curl http://localhost:5000/api/protonvpn/servers?refresh=true
```

## 🔍 Cách hoạt động

### 1. API Mode

```python
from protonvpn_api import ProtonVPNAPI

# Khởi tạo với credentials
api = ProtonVPNAPI(
    cache_file='protonvpn_servers_cache.json',
    bearer_token='your_token',
    uid='your_uid'
)

# Lấy servers
servers = api.get_servers()

# Lấy best server
best = api.get_best_server('JP', tier=2)
```

### 2. Áp dụng vào Gost

```bash
# Lấy thông tin server
domain = "node-jp-10.protonvpn.net"
label = 10
port = label + 4443  # 4453

# Lấy credentials
auth = $(./get_protonvpn_auth.sh)
# Output: username+password:password

# Tạo proxy URL
proxy_url = "https://${auth}@${domain}:${port}"

# Cấu hình Gost
./manage_gost.sh config 7891 protonvpn "$domain" "$domain" "$port"

# Restart Gost
./manage_gost.sh restart
```

## 🧪 Testing

### Test API credentials

```python
from protonvpn_api import ProtonVPNAPI

api = ProtonVPNAPI(
    cache_file='protonvpn_servers_cache.json',
    bearer_token='your_token',
    uid='your_uid'
)

# Test connection
servers = api.get_servers()
print(f"Found {len(servers)} servers")
```

### Test proxy connection

```bash
# Áp dụng server
curl -X POST http://localhost:5000/api/protonvpn/apply/7891 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "JP#10"}'

# Test connection
curl -x socks5h://127.0.0.1:7891 https://ipinfo.io/ip

# Kiểm tra IP
curl -x socks5h://127.0.0.1:7891 https://ipinfo.io/json
```

## 🐛 Troubleshooting

### API Mode không hoạt động

**1. Check credentials file:**

```bash
ls -la protonvpn_credentials.json
cat protonvpn_credentials.json
```

**2. Test credentials:**

```bash
# Test với curl
bearer_token="your_token"
uid="your_uid"

curl -H "Authorization: Bearer $bearer_token" \
     -H "x-pm-uid: $uid" \
     https://api.protonvpn.ch/vpn/logicals
```

**3. Credentials có thể expire:**

- Lấy lại credentials từ browser
- Cập nhật `protonvpn_credentials.json`
- Restart Web UI

### Config Mode không có configs

**1. Check directory:**

```bash
ls -la protonvpn_configs/
```

**2. Download configs:**

- Vào https://account.protonvpn.com/
- Downloads → WireGuard configuration
- Download và place vào `protonvpn_configs/`

### Connection failed

```bash
# Kiểm tra Gost logs
tail -f logs/gost_7891.log

# Kiểm tra cấu hình
./manage_gost.sh show-config

# Kiểm tra credentials
./get_protonvpn_auth.sh

# Test proxy URL trực tiếp
auth=$(./get_protonvpn_auth.sh)
curl -x "https://${auth}@node-jp-10.protonvpn.net:4453" \
  https://ipinfo.io/ip

# Restart Gost
./manage_gost.sh restart
```

### Credentials không tự động cập nhật

```bash
# Kiểm tra auto updater service
sudo systemctl status auto-credential-updater

# Xem logs
sudo journalctl -u auto-credential-updater -f

# Restart service
sudo systemctl restart auto-credential-updater

# Hoặc chạy thủ công
./start_auto_updater.sh
```

## 📝 Examples

### Example 1: Best server ở Japan (Tier 2)

```bash
# Lấy best server
curl http://localhost:5000/api/protonvpn/best?country=JP&tier=2

# Áp dụng vào Gost 7891
curl -X POST http://localhost:5000/api/protonvpn/apply/7891 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "JP#10"}'

# Test
curl -x socks5h://127.0.0.1:7891 https://ipinfo.io/ip
```

### Example 2: Free servers

```bash
# Lấy best free server
curl http://localhost:5000/api/protonvpn/best?tier=0

# Áp dụng
curl -X POST http://localhost:5000/api/protonvpn/apply/7892 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "US-FREE#1"}'
```

### Example 3: Nhiều servers

```bash
# Gost 7891 → JP Plus server
curl -X POST http://localhost:5000/api/protonvpn/apply/7891 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "JP#10"}'

# Gost 7892 → US Plus server
curl -X POST http://localhost:5000/api/protonvpn/apply/7892 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "US-CA#10"}'

# Gost 7893 → Free server
curl -X POST http://localhost:5000/api/protonvpn/apply/7893 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "US-FREE#1"}'

# Test tất cả
curl -x socks5h://127.0.0.1:7891 https://ipinfo.io/ip  # JP IP
curl -x socks5h://127.0.0.1:7892 https://ipinfo.io/ip  # US IP
curl -x socks5h://127.0.0.1:7893 https://ipinfo.io/ip  # US IP (Free)
```

## 🔐 Security Notes

- **API credentials**: Không commit vào git (đã có trong .gitignore)
- **Config files**: Chứa private keys, không share
- **Bearer token**: Có thể expire, cần refresh định kỳ
- **UID**: Unique per account
- **Credentials**: Được mã hóa trong config_token.txt

## 📊 Server Selection Logic

### Best Server Algorithm

1. Lấy tất cả servers của quốc gia và tier
2. Lọc servers online
3. Sắp xếp theo:
   - Load (thấp → cao)
   - Score (cao → thấp)
4. Trả về server đầu tiên

### Load & Score

- **Load**: % CPU/bandwidth usage (0-100)
- **Score**: Server performance score (0-10)

Web UI hiển thị:
- 🟢 Load < 20%: Excellent
- 🟡 Load 20-50%: Good
- 🟠 Load 50-80%: Fair
- 🔴 Load > 80%: Poor

