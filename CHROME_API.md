# Chrome Proxy API

API tự động tạo Gost proxy cho Chrome profiles.

## 📋 Endpoint

```
POST /api/chrome/proxy-check
```

## 🔧 Request Format

```json
{
  "proxy_check": "socks5://server:7891:vn42.nordvpn.com:",
  "data": {
    "count": 3,
    "profiles": [
      {
        "id": 1,
        "name": "Profile 1",
        "proxy": "127.0.0.1:7891:vn42.nordvpn.com"
      },
      {
        "id": 2,
        "name": "Profile 2",
        "proxy": null
      }
    ]
  }
}
```

### Fields

**`proxy_check`**: Proxy string format `socks5://server:PORT:SERVER_NAME:`
- `PORT`: Gost port (7891, 7892, etc.)
- `SERVER_NAME`: VPN server identifier
  - NordVPN: `vn42.nordvpn.com`, `us1234.nordvpn.com`
  - ProtonVPN: `node-us-ca-10.protonvpn.net`, `node-jp-10.protonvpn.net`

**`data.profiles`**: Array of opened Chrome profiles
- `proxy`: Format `127.0.0.1:PORT:SERVER_NAME` or `null`

## 📤 Response Format

```json
{
  "success": true,
  "message": "Created new Gost on port 7891 with server vn42.nordvpn.com",
  "proxy_check": "socks5://127.0.0.1:7891:vn42.nordvpn.com:",
  "data": {
    "count": 3,
    "profiles": [...]
  },
  "action": "created_new",
  "port": 7891,
  "server": "vn42.nordvpn.com",
  "provider": "nordvpn"
}
```

### Action Types

| Action | Description |
|--------|-------------|
| `use_existing` | Proxy đã được sử dụng bởi profile khác |
| `created_new` | Tạo Gost instance mới |
| `reconfigured` | Cấu hình lại Gost với server mới |
| `already_configured` | Gost đã được cấu hình đúng |

## 🔄 Logic Flow

### Case 1: Exact Match
- `proxy_check` khớp với proxy đang được sử dụng
- **Action**: `use_existing`
- **Result**: Không thay đổi gì

### Case 2: Port Conflict
- Port đang được sử dụng nhưng server khác
- **Action**: Tạo Gost mới trên port tiếp theo
- **Result**: Gost instance mới

### Case 3: Reconfigure
- Gost tồn tại trên port nhưng server khác
- Port không được sử dụng bởi profiles
- **Action**: Cấu hình lại Gost với server mới
- **Result**: Cập nhật config và restart

### Case 4: New Instance
- Gost chưa tồn tại trên port
- **Action**: Tạo Gost instance mới
- **Result**: Gost instance mới

## 🌐 VPN Provider Detection

Server name xác định VPN provider:
- Chứa `nordvpn` → NordVPN
- Chứa `protonvpn` → ProtonVPN

## 📝 Examples

### Example 1: Tạo Gost mới

**Request:**
```bash
curl -X POST http://localhost:5000/api/chrome/proxy-check \
  -H "Content-Type: application/json" \
  -d '{
    "proxy_check": "socks5://server:7891:vn42.nordvpn.com:",
    "data": {
      "count": 0,
      "profiles": []
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Created new Gost on port 7891 with server vn42.nordvpn.com",
  "proxy_check": "socks5://127.0.0.1:7891:vn42.nordvpn.com:",
  "action": "created_new",
  "port": 7891,
  "server": "vn42.nordvpn.com",
  "provider": "nordvpn"
}
```

### Example 2: Port Conflict

**Request:**
```bash
curl -X POST http://localhost:5000/api/chrome/proxy-check \
  -H "Content-Type: application/json" \
  -d '{
    "proxy_check": "socks5://server:7891:us10.nordvpn.com:",
    "data": {
      "count": 1,
      "profiles": [
        {"id": 1, "name": "Profile 1", "proxy": "127.0.0.1:7891:vn42.nordvpn.com"}
      ]
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Created new Gost on port 7892 with server us10.nordvpn.com",
  "proxy_check": "socks5://127.0.0.1:7892:us10.nordvpn.com:",
  "action": "created_new",
  "port": 7892,
  "server": "us10.nordvpn.com",
  "provider": "nordvpn"
}
```

### Example 3: ProtonVPN

**Request:**
```bash
curl -X POST http://localhost:5000/api/chrome/proxy-check \
  -H "Content-Type: application/json" \
  -d '{
    "proxy_check": "socks5://server:7891:node-jp-10.protonvpn.net:",
    "data": {
      "count": 0,
      "profiles": []
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Created new Gost on port 7891 with server node-jp-10.protonvpn.net",
  "proxy_check": "socks5://127.0.0.1:7891:node-jp-10.protonvpn.net:",
  "action": "created_new",
  "port": 7891,
  "server": "node-jp-10.protonvpn.net",
  "provider": "protonvpn"
}
```

## 🏗️ Architecture

```
Chrome Profile
    ↓ (request proxy)
API /api/chrome/proxy-check
    ↓ (check & create)
Gost (port 7891-7999)
    ↓ (forward to)
VPN Proxy (NordVPN/ProtonVPN)
    ↓ (connect to)
Internet
```

## 📊 Port Ranges

- **Gost**: 7891-7999 (SOCKS5 proxy for Chrome)
- **Web UI**: 5000
- **WARP**: 7890 (fallback)

## 🔍 Cách hoạt động

### 1. Parse Request

```python
proxy_check = "socks5://server:7891:vn42.nordvpn.com:"
# Extract:
# - port: 7891
# - server: vn42.nordvpn.com
# - provider: nordvpn (từ server name)
```

### 2. Check Existing Profiles

```python
profiles = [
    {"proxy": "127.0.0.1:7891:vn42.nordvpn.com"},
    {"proxy": "127.0.0.1:7892:us10.nordvpn.com"}
]
# Kiểm tra nếu proxy_check đã được sử dụng
```

### 3. Find Available Port

```python
# Nếu port conflict, tìm port tiếp theo
used_ports = [7891, 7892]
available_port = 7893
```

### 4. Create/Update Gost

```python
# Tạo config
config = {
    "port": 7891,
    "provider": "nordvpn",
    "country": "vn",
    "proxy_host": "vn42.nordvpn.com",
    "proxy_port": "89"
}

# Lưu config
save_config(config)

# Restart Gost
restart_gost(7891)
```

## 🧪 Testing

### Test Script

```bash
# Test với script có sẵn
python3 test_chrome_api.py
```

### Test thủ công

```bash
# 1. Tạo Gost mới
curl -X POST http://localhost:5000/api/chrome/proxy-check \
  -H "Content-Type: application/json" \
  -d '{
    "proxy_check": "socks5://server:7891:vn42.nordvpn.com:",
    "data": {"count": 0, "profiles": []}
  }'

# 2. Kiểm tra Gost đã được tạo
./manage_gost.sh status

# 3. Test connection
curl -x socks5h://127.0.0.1:7891 https://api.ipify.org

# 4. Kiểm tra config
./manage_gost.sh show-config
```

## 🔧 Integration với Chrome Extension

### Chrome Extension Code

```javascript
// Background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'checkProxy') {
    const proxyCheck = `socks5://server:7891:${request.server}:`;
    
    // Lấy danh sách profiles đang mở
    chrome.windows.getAll({populate: true}, (windows) => {
      const profiles = windows.map(w => ({
        id: w.id,
        name: w.title,
        proxy: w.proxy || null
      }));
      
      // Gọi API
      fetch('http://localhost:5000/api/chrome/proxy-check', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          proxy_check: proxyCheck,
          data: {count: profiles.length, profiles: profiles}
        })
      })
      .then(res => res.json())
      .then(data => {
        // Áp dụng proxy cho Chrome
        chrome.proxy.settings.set({
          value: {
            mode: 'fixed_servers',
            rules: {
              singleProxy: {
                scheme: 'socks5',
                host: '127.0.0.1',
                port: data.port
              }
            }
          }
        });
        sendResponse(data);
      });
    });
    
    return true;
  }
});
```

## 🐛 Troubleshooting

### API không response

```bash
# Kiểm tra Web UI
curl http://localhost:5000/api/status

# Kiểm tra logs
tail -f logs/webui.log

# Restart Web UI
./start_webui_daemon.sh
```

### Gost không được tạo

```bash
# Kiểm tra Gost binary
which gost

# Kiểm tra quyền thực thi
chmod +x manage_gost.sh

# Test thủ công
./manage_gost.sh config 7891 nordvpn "vn" "vn42.nordvpn.com" "89"
./manage_gost.sh start
```

### Connection failed

```bash
# Kiểm tra Gost logs
tail -f logs/gost_7891.log

# Kiểm tra config
./manage_gost.sh show-config

# Test proxy
curl -x socks5h://127.0.0.1:7891 https://api.ipify.org

# Restart Gost
./manage_gost.sh restart
```

### Port conflict

```bash
# Kiểm tra port đang được sử dụng
lsof -i :7891

# Kill process cũ
lsof -ti :7891 | xargs kill -9

# Restart Gost
./manage_gost.sh restart
```

## 📊 Response Codes

| Code | Message | Description |
|------|---------|-------------|
| 200 | Success | Request thành công |
| 400 | Bad Request | Request format không đúng |
| 500 | Internal Error | Lỗi server |

## 🔐 Security

**Lưu ý:**
- API không có authentication
- Có thể truy cập từ localhost
- Không nên expose ra internet

**Khuyến nghị:**
- Chỉ bind localhost: `app.run(host='127.0.0.1')`
- Sử dụng firewall để block port 5000 từ bên ngoài
- Thêm authentication nếu cần

## 📝 Notes

- API tự động detect VPN provider từ server name
- Hỗ trợ tối đa 109 Gost instances (7891-7999)
- Mỗi Gost instance có config riêng
- Config được lưu trong `config/gost_<port>.config`
- Gost tự động restart khi config thay đổi
- Test connection tự động sau khi tạo/update Gost

