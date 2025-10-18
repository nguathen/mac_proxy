# ProtonVPN Integration

Hệ thống hỗ trợ 2 modes để sử dụng ProtonVPN:

## Mode 1: API Mode (Recommended)

Fetch servers trực tiếp từ ProtonVPN API - giống NordVPN.

### Setup

1. **Get credentials từ ProtonVPN web**:
   - Login vào https://account.protonvpn.com/
   - Open Browser DevTools (F12) → Network tab
   - Reload page hoặc navigate
   - Tìm API request (ví dụ: `/vpn/logicals`)
   - Copy headers:
     - `Authorization: Bearer <token>` → Lấy token
     - `x-pm-uid: <uid>` → Lấy UID

2. **Create credentials file**:
```bash
cp protonvpn_credentials.json.example protonvpn_credentials.json
```

3. **Edit file với credentials**:
```json
{
  "bearer_token": "wqs7vr3zn5oaoquqgcg5i3mp6momlnk7",
  "uid": "m46kiazjmmiun2lzuxafbdavegwvsyhm"
}
```

4. **Restart Web UI**:
```bash
bash stop_webui.sh && bash start_webui.sh
```

### Sử dụng

Giống NordVPN:
- Mở Web UI: http://localhost:5000
- Scroll xuống "🔐 ProtonVPN Config Selection"
- Chọn country → Chọn server → Apply
- Servers được fetch tự động từ API

## Mode 2: Config Mode (Fallback)

Scan local WireGuard config files - không cần credentials.

### Setup

1. **Download configs từ ProtonVPN**:
   - Login vào https://account.protonvpn.com/
   - Vào **Downloads** → **WireGuard configuration**
   - Chọn platform: **Linux** hoặc **Router**
   - Download `.conf` files

2. **Place configs**:
```bash
cp ~/Downloads/US-FREE#1.conf protonvpn_configs/
cp ~/Downloads/JP#10.conf protonvpn_configs/
```

3. **Scan configs**:
- Mở Web UI
- Click "Scan Configs" button

### Sử dụng

- Chọn country → Chọn config → Apply
- Configs được scan từ local directory

## So sánh 2 modes

| Feature | API Mode | Config Mode |
|---------|----------|-------------|
| Setup | Cần credentials | Cần download configs |
| Server count | Tất cả servers | Chỉ configs đã download |
| Auto update | Cache 1 giờ | Manual scan |
| Best server | ✅ Có | ❌ Không |
| Filter by tier | ✅ Có | ❌ Không |
| Load info | ✅ Có | ❌ Không |

## API Endpoints

### API Mode

```bash
# Get all servers
GET /api/protonvpn/servers

# Get servers by country
GET /api/protonvpn/servers/US

# Get best server
GET /api/protonvpn/best?country=JP&tier=2

# Apply server
POST /api/protonvpn/apply/1
Body: {"server_name": "US-FREE#1"}
```

### Config Mode

```bash
# Get all configs
GET /api/protonvpn/configs

# Get configs by country
GET /api/protonvpn/configs/US

# Apply config
POST /api/protonvpn/apply/1
Body: {"config_name": "US-FREE#1"}
```

### Hybrid (Auto-detect)

```bash
# Get countries (API mode if available, fallback to configs)
GET /api/protonvpn/countries
```

## CLI Usage

### API Mode

```bash
# Test API với credentials
python3 protonvpn_api.py <bearer_token> <uid>
```

### Config Mode

```bash
# Scan configs
python3 protonvpn_manager.py
```

## Troubleshooting

### API Mode không hoạt động

1. Check credentials file exists:
```bash
ls -la protonvpn_credentials.json
```

2. Check credentials valid:
```bash
cat protonvpn_credentials.json
```

3. Test API:
```bash
python3 protonvpn_api.py <bearer_token> <uid>
```

4. Credentials có thể expire - cần lấy lại từ browser

### Config Mode không có configs

1. Check directory:
```bash
ls -la protonvpn_configs/
```

2. Download configs từ ProtonVPN account

3. Place vào `protonvpn_configs/` directory

## Security Notes

- **API credentials**: Không commit vào git (đã có trong .gitignore)
- **Config files**: Chứa private keys, không share
- **Bearer token**: Có thể expire, cần refresh định kỳ
- **UID**: Unique per account

## Tiers

ProtonVPN có 3 tiers:

- **Tier 0 (Free)**: Limited servers, slower
- **Tier 1 (Basic)**: More servers
- **Tier 2 (Plus/Visionary)**: All servers, fastest

API mode cho phép filter by tier:
```bash
# Get best free server
GET /api/protonvpn/best?tier=0

# Get best plus server in US
GET /api/protonvpn/best?country=US&tier=2
```

## Examples

### API Mode - Best server

```bash
# Get best server globally
curl http://localhost:5000/api/protonvpn/best

# Get best Plus server in Japan
curl "http://localhost:5000/api/protonvpn/best?country=JP&tier=2"

# Apply to wireproxy 1
curl -X POST http://localhost:5000/api/protonvpn/apply/1 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "JP#10"}'
```

### Config Mode - Local configs

```bash
# Scan configs
curl http://localhost:5000/api/protonvpn/configs

# Get US configs
curl http://localhost:5000/api/protonvpn/configs/US

# Apply config
curl -X POST http://localhost:5000/api/protonvpn/apply/1 \
  -H "Content-Type: application/json" \
  -d '{"config_name": "US-FREE#1"}'
```

