# Chrome Proxy Check API

API endpoint để kiểm tra và tự động tạo HAProxy cho Chrome profiles.

## Endpoint

```
POST /api/chrome/proxy-check
```

## Request Format

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

- `proxy_check`: Proxy string format `socks5://server:PORT:SERVER_NAME:`
  - PORT: HAProxy port (7891, 7892, etc.)
  - SERVER_NAME: VPN server identifier (vn42.nordvpn.com, us-ca-10.protonvpn.com)

- `data.profiles`: Array of opened Chrome profiles
  - `proxy`: Format `127.0.0.1:PORT:SERVER_NAME` or `null`

## Response Format

```json
{
  "success": true,
  "message": "Created new HAProxy on port 7891 with server vn42.nordvpn.com",
  "proxy_check": "socks5://127.0.0.1:7891:vn42.nordvpn.com:",
  "data": {
    "count": 3,
    "profiles": [...]
  },
  "action": "created_new",
  "port": 7891,
  "server": "vn42.nordvpn.com"
}
```

### Action Types

1. **`use_existing`**: Proxy already in use by another profile
2. **`created_new`**: Created new HAProxy instance
3. **`reconfigured`**: Reconfigured existing HAProxy with new server
4. **`already_configured`**: HAProxy already configured correctly

## Logic Flow

### Case 1: Exact Match
- `proxy_check` matches existing profile proxy
- **Action**: Return `use_existing`
- **Result**: No changes

### Case 2: Port Conflict
- Port in use but different server
- **Action**: Create new HAProxy on next available port
- **Result**: New HAProxy + Wireproxy instance

### Case 3: Reconfigure
- HAProxy exists on port but different server
- Port not in use by profiles
- **Action**: Reconfigure HAProxy with new server
- **Result**: Update Wireproxy config and restart

### Case 4: New Instance
- HAProxy doesn't exist on port
- **Action**: Create new HAProxy instance
- **Result**: New HAProxy + Wireproxy instance

## VPN Provider Detection

Server name determines VPN provider:
- Contains `nordvpn` → NordVPN
- Contains `protonvpn` → ProtonVPN

## Examples

### Example 1: Create New HAProxy

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
  "message": "Created new HAProxy on port 7891 with server vn42.nordvpn.com",
  "proxy_check": "socks5://127.0.0.1:7891:vn42.nordvpn.com:",
  "action": "created_new",
  "port": 7891,
  "server": "vn42.nordvpn.com",
  "wireproxy_port": 18183
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
  "message": "Created new HAProxy on port 7892 with server us10.nordvpn.com",
  "proxy_check": "socks5://127.0.0.1:7892:us10.nordvpn.com:",
  "action": "created_new",
  "port": 7892,
  "server": "us10.nordvpn.com"
}
```

## Testing

Test script available: `test_chrome_proxy_api.py`

```bash
# Start WebUI
cd webui && python3 app.py

# In another terminal, run tests
python3 test_chrome_proxy_api.py
```

## Architecture

```
Chrome Profile
    ↓ (request proxy)
API /api/chrome/proxy-check
    ↓ (check & create)
HAProxy (port 7891-7999)
    ↓ (forward to)
Wireproxy (port 18181-18999)
    ↓ (connect via)
VPN Server (NordVPN/ProtonVPN)
```

## Port Ranges

- **HAProxy**: 7891-7999 (SOCKS5 proxy for Chrome)
- **HAProxy Stats**: 8091-8199 (Web UI for monitoring)
- **Wireproxy**: 18181-18999 (WireGuard SOCKS5 backend)

## Notes

- Each HAProxy instance has dedicated Wireproxy instance
- Automatic server detection from endpoint IP
- Health monitoring with automatic failover to Cloudflare WARP
- Dynamic creation up to 109 HAProxy instances (7891-7999)

