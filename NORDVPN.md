# NordVPN Integration

Hệ thống tích hợp NordVPN với 5000+ servers trên 46 quốc gia.

## ✨ Tính năng

- ✅ Tự động lấy danh sách servers từ NordVPN API
- ✅ Cache servers (1 giờ)
- ✅ Chọn server theo quốc gia
- ✅ Tự động tìm best server (load thấp nhất)
- ✅ Áp dụng server vào Gost instance
- ✅ Web UI và CLI

## 🚀 Sử dụng qua Web UI

1. Mở Web UI: http://localhost:5000

2. Chọn tab "NordVPN"

3. Chọn quốc gia từ dropdown

4. Chọn server (servers được sắp xếp theo load thấp nhất)

5. Xem thông tin server:
   - Hostname
   - Load (%)
   - Location
   - Status

6. Chọn Gost port (7891, 7892, ...)

7. Click "Apply to Gost"

8. Gost sẽ tự động:
   - Cập nhật cấu hình
   - Restart instance
   - Test connection

## 🔧 API Endpoints

### Lấy danh sách quốc gia

```bash
GET /api/nordvpn/countries

# Response:
{
  "success": true,
  "countries": [
    {"code": "US", "name": "United States"},
    {"code": "JP", "name": "Japan"},
    {"code": "SG", "name": "Singapore"}
  ]
}
```

### Lấy tất cả servers

```bash
GET /api/nordvpn/servers

# Optional: Force refresh
GET /api/nordvpn/servers?refresh=true

# Response:
{
  "success": true,
  "servers": [
    {
      "name": "Japan #720",
      "hostname": "jp720.nordvpn.com",
      "load": 15,
      "country": "JP",
      "location": "Tokyo",
      "status": "online"
    }
  ]
}
```

### Lấy servers theo quốc gia

```bash
GET /api/nordvpn/servers/JP

# Response:
{
  "success": true,
  "country": "JP",
  "servers": [...]
}
```

### Lấy best server

```bash
# Best server globally
GET /api/nordvpn/best

# Best server theo quốc gia
GET /api/nordvpn/best?country=SG

# Response:
{
  "success": true,
  "server": {
    "name": "Singapore #528",
    "hostname": "sg528.nordvpn.com",
    "load": 8,
    "country": "SG"
  }
}
```

### Áp dụng server vào Gost

```bash
POST /api/nordvpn/apply/7891
Content-Type: application/json

{
  "server_name": "Japan #720"
}

# Response:
{
  "success": true,
  "message": "Applied Japan #720 to Gost 7891",
  "port": 7891,
  "server": "Japan #720",
  "hostname": "jp720.nordvpn.com"
}
```

## 📋 Quốc gia phổ biến

| Code | Country | Servers |
|------|---------|---------|
| US | United States | 1000+ |
| JP | Japan | 200+ |
| SG | Singapore | 100+ |
| GB | United Kingdom | 500+ |
| DE | Germany | 300+ |
| FR | France | 200+ |
| CA | Canada | 300+ |
| AU | Australia | 200+ |
| NL | Netherlands | 300+ |
| SE | Sweden | 100+ |
| CH | Switzerland | 100+ |
| HK | Hong Kong | 100+ |
| KR | South Korea | 50+ |
| TW | Taiwan | 50+ |
| IN | India | 50+ |

## 🔄 Cache

Danh sách servers được cache trong `nordvpn_servers_cache.json` với thời gian 1 giờ.

**Force refresh:**
- Web UI: Click "Refresh Servers"
- API: `GET /api/nordvpn/servers?refresh=true`
- CLI: Xóa cache file

```bash
rm nordvpn_servers_cache.json
```

## 🔍 Cách hoạt động

### 1. Lấy danh sách servers

```python
from nordvpn_api import NordVPNAPI

api = NordVPNAPI('nordvpn_servers_cache.json')
servers = api.get_servers()
```

### 2. Lọc theo quốc gia

```python
jp_servers = api.get_servers_by_country('JP')
```

### 3. Tìm best server

```python
best = api.get_best_server('SG')
# Trả về server có load thấp nhất
```

### 4. Áp dụng vào Gost

```bash
# Lấy thông tin server
hostname = "jp720.nordvpn.com"
proxy_host = hostname
proxy_port = "89"  # NordVPN HTTPS proxy port

# Tạo proxy URL
proxy_url = f"https://USMbUonbFpF9xEx8xR3MHSau:buKKKPURZNMTW7A6rwm3qtBn@{proxy_host}:{proxy_port}"

# Cấu hình Gost
./manage_gost.sh config 7891 nordvpn "jp" "$proxy_host" "$proxy_port"

# Restart Gost
./manage_gost.sh restart
```

## 🧪 Testing

### Test server selection

```python
from nordvpn_api import NordVPNAPI

api = NordVPNAPI('nordvpn_servers_cache.json')

# Lấy best server ở Japan
best = api.get_best_server('JP')
print(f"Best server: {best['name']}")
print(f"Load: {best['load']}%")
print(f"Hostname: {best['hostname']}")
```

### Test proxy connection

```bash
# Áp dụng server
curl -X POST http://localhost:5000/api/nordvpn/apply/7891 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "Japan #720"}'

# Test connection
curl -x socks5h://127.0.0.1:7891 https://ipinfo.io/ip

# Kiểm tra IP
curl -x socks5h://127.0.0.1:7891 https://ipinfo.io/json
```

## 🐛 Troubleshooting

### Server list rỗng

```bash
# Xóa cache và force refresh
rm nordvpn_servers_cache.json

# Restart Web UI
./start_webui_daemon.sh

# Hoặc gọi API với refresh=true
curl http://localhost:5000/api/nordvpn/servers?refresh=true
```

### Connection failed

```bash
# Kiểm tra Gost logs
tail -f logs/gost_7891.log

# Kiểm tra cấu hình
./manage_gost.sh show-config

# Test proxy URL trực tiếp
curl -x https://USMbUonbFpF9xEx8xR3MHSau:buKKKPURZNMTW7A6rwm3qtBn@jp720.nordvpn.com:89 \
  https://ipinfo.io/ip

# Restart Gost
./manage_gost.sh restart
```

### Credentials không hoạt động

```bash
# Credentials được hardcode trong manage_gost.sh
# Nếu không hoạt động, cần cập nhật credentials mới

# Kiểm tra trong manage_gost.sh:
grep "USMbUonbFpF9xEx8xR3MHSau" manage_gost.sh
```

## 📊 Server Selection Logic

### Best Server Algorithm

1. Lấy tất cả servers của quốc gia
2. Lọc servers online
3. Sắp xếp theo load (thấp → cao)
4. Trả về server đầu tiên (load thấp nhất)

### Load Balancing

- Load < 20%: Excellent
- Load 20-50%: Good
- Load 50-80%: Fair
- Load > 80%: Poor

Web UI hiển thị màu sắc theo load:
- 🟢 Green: < 20%
- 🟡 Yellow: 20-50%
- 🟠 Orange: 50-80%
- 🔴 Red: > 80%

## 🔐 Credentials

NordVPN sử dụng credentials cố định:
- Username: `USMbUonbFpF9xEx8xR3MHSau`
- Password: `buKKKPURZNMTW7A6rwm3qtBn`

Credentials được hardcode trong `manage_gost.sh`.

**Lưu ý:** Credentials này có thể expire, cần cập nhật định kỳ.

## 📝 Examples

### Example 1: Chọn best server ở US

```bash
# Qua API
curl http://localhost:5000/api/nordvpn/best?country=US

# Áp dụng vào Gost 7891
curl -X POST http://localhost:5000/api/nordvpn/apply/7891 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "United States #1234"}'

# Test
curl -x socks5h://127.0.0.1:7891 https://ipinfo.io/ip
```

### Example 2: List servers ở Japan

```bash
# Lấy danh sách
curl http://localhost:5000/api/nordvpn/servers/JP

# Chọn server cụ thể
curl -X POST http://localhost:5000/api/nordvpn/apply/7892 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "Japan #720"}'
```

### Example 3: Sử dụng nhiều servers

```bash
# Gost 7891 → US server
curl -X POST http://localhost:5000/api/nordvpn/apply/7891 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "United States #1234"}'

# Gost 7892 → JP server
curl -X POST http://localhost:5000/api/nordvpn/apply/7892 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "Japan #720"}'

# Gost 7893 → SG server
curl -X POST http://localhost:5000/api/nordvpn/apply/7893 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "Singapore #528"}'

# Test tất cả
curl -x socks5h://127.0.0.1:7891 https://ipinfo.io/ip  # US IP
curl -x socks5h://127.0.0.1:7892 https://ipinfo.io/ip  # JP IP
curl -x socks5h://127.0.0.1:7893 https://ipinfo.io/ip  # SG IP
```

