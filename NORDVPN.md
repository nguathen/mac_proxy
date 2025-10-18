# NordVPN Integration

Hệ thống proxy đã được tích hợp với NordVPN, cho phép bạn dễ dàng chọn và áp dụng server NordVPN vào wireproxy.

## Tính năng

- ✅ Tự động lấy danh sách server NordVPN từ API
- ✅ Cache danh sách server (1 giờ)
- ✅ Chọn server theo quốc gia
- ✅ Tự động tìm server tốt nhất (load thấp nhất)
- ✅ Áp dụng server vào wireproxy instance
- ✅ Giao diện Web UI
- ✅ Command line interface (CLI)

## Yêu cầu

PrivateKey của NordVPN phải có sẵn trong file config (`wg18181.conf`, `wg18182.conf`).

## Sử dụng qua Web UI

1. Mở Web UI: http://localhost:5000

2. Tìm phần "🌍 NordVPN Server Selection"

3. Chọn quốc gia từ dropdown

4. Chọn server (servers được sắp xếp theo load thấp nhất)

5. Xem thông tin server

6. Click "Apply to Wireproxy 1" hoặc "Apply to Wireproxy 2"

7. Server sẽ được áp dụng và wireproxy sẽ tự động restart

## Sử dụng qua CLI

### 1. List tất cả quốc gia

```bash
python3 nordvpn_cli.py countries
```

### 2. List servers theo quốc gia

```bash
# List 20 servers đầu tiên ở US
python3 nordvpn_cli.py servers --country US

# List 50 servers đầu tiên ở JP
python3 nordvpn_cli.py servers --country JP --limit 50

# Force refresh từ API
python3 nordvpn_cli.py servers --refresh
```

### 3. Tìm server tốt nhất

```bash
# Best server globally
python3 nordvpn_cli.py best

# Best server ở Singapore
python3 nordvpn_cli.py best --country SG
```

### 4. Áp dụng server vào wireproxy

```bash
# Áp dụng server cụ thể vào instance 1
python3 nordvpn_cli.py apply 1 --server "Japan #720"

# Áp dụng server cụ thể vào instance 2
python3 nordvpn_cli.py apply 2 --server "Singapore #528"
```

## Sử dụng qua Shell Script

Script `apply_nordvpn.sh` cung cấp cách dễ dàng hơn để áp dụng server:

### List countries

```bash
bash apply_nordvpn.sh --list-countries
```

### List servers theo quốc gia

```bash
bash apply_nordvpn.sh --list-servers JP
bash apply_nordvpn.sh --list-servers US
bash apply_nordvpn.sh --list-servers SG
```

### Áp dụng server cụ thể

```bash
# Áp dụng server cụ thể vào instance 1
bash apply_nordvpn.sh --instance 1 --server "Japan #720"

# Áp dụng server cụ thể vào instance 2
bash apply_nordvpn.sh --instance 2 --server "Singapore #528"
```

### Áp dụng best server theo quốc gia

```bash
# Tự động chọn và áp dụng best server ở US vào instance 1
bash apply_nordvpn.sh --instance 1 --country US

# Tự động chọn và áp dụng best server ở JP vào instance 2
bash apply_nordvpn.sh --instance 2 --country JP
```

Script sẽ:
1. Tìm best server
2. Cập nhật config file
3. Hỏi có muốn restart wireproxy không
4. Nếu có, sẽ restart và test connection

## Workflow ví dụ

### Scenario 1: Chọn server Japan cho instance 1

```bash
# 1. List servers ở Japan
bash apply_nordvpn.sh --list-servers JP

# 2. Chọn server có load thấp nhất
bash apply_nordvpn.sh --instance 1 --server "Japan #720"

# 3. Script sẽ tự động restart và test
```

### Scenario 2: Quick apply best server

```bash
# Tự động chọn và áp dụng best server ở Singapore
bash apply_nordvpn.sh --instance 2 --country SG

# Script sẽ tự động:
# - Tìm server tốt nhất
# - Cập nhật config
# - Restart wireproxy
# - Test connection
```

### Scenario 3: Sử dụng Web UI

1. Mở http://localhost:5000
2. Scroll xuống phần "NordVPN Server Selection"
3. Chọn country "Japan"
4. Chọn server từ dropdown (đã sort theo load)
5. Xem thông tin server
6. Click "Apply to Wireproxy 1"
7. Đợi restart và test

## API Endpoints

Web UI cung cấp các API endpoints:

### GET /api/nordvpn/countries
Lấy danh sách quốc gia

```bash
curl http://localhost:5000/api/nordvpn/countries
```

### GET /api/nordvpn/servers
Lấy tất cả servers

```bash
curl http://localhost:5000/api/nordvpn/servers

# Force refresh
curl http://localhost:5000/api/nordvpn/servers?refresh=true
```

### GET /api/nordvpn/servers/:country_code
Lấy servers theo quốc gia

```bash
curl http://localhost:5000/api/nordvpn/servers/JP
curl http://localhost:5000/api/nordvpn/servers/US
```

### GET /api/nordvpn/best
Lấy best server

```bash
# Best server globally
curl http://localhost:5000/api/nordvpn/best

# Best server theo quốc gia
curl http://localhost:5000/api/nordvpn/best?country=SG
```

### POST /api/nordvpn/apply/:instance
Áp dụng server vào wireproxy instance

```bash
curl -X POST http://localhost:5000/api/nordvpn/apply/1 \
  -H "Content-Type: application/json" \
  -d '{"server_name": "Japan #720"}'
```

## Cache

Danh sách server được cache trong file `nordvpn_servers_cache.json` với thời gian 1 giờ.

Để force refresh:
- Web UI: Click nút "Refresh Servers"
- CLI: `python3 nordvpn_cli.py servers --refresh`
- API: `curl http://localhost:5000/api/nordvpn/servers?refresh=true`

## Backup

Mỗi khi áp dụng server mới, config cũ sẽ được backup với timestamp:
- `wg18181.conf.backup.1729267890`
- `wg18182.conf.backup.1729267891`

## Troubleshooting

### Server list rỗng
```bash
# Force refresh từ API
python3 nordvpn_cli.py servers --refresh
```

### Connection failed sau khi apply
```bash
# Check logs
tail -f logs/wireproxy1.log
tail -f logs/wireproxy2.log

# Restart wireproxy
bash manage_wireproxy.sh restart

# Test connection
curl -x socks5h://127.0.0.1:18181 https://api.ipify.org
```

### Private key not found
Đảm bảo file config có PrivateKey:
```bash
grep PrivateKey wg18181.conf
```

## Quốc gia phổ biến

- US: United States
- JP: Japan
- SG: Singapore
- GB: United Kingdom
- DE: Germany
- FR: France
- CA: Canada
- AU: Australia
- NL: Netherlands
- SE: Sweden
- CH: Switzerland
- HK: Hong Kong
- KR: South Korea
- TW: Taiwan
- IN: India
- BR: Brazil
- AR: Argentina
- MX: Mexico
- IT: Italy
- ES: Spain
- PL: Poland
- NO: Norway
- DK: Denmark
- FI: Finland
- AT: Austria
- BE: Belgium
- CZ: Czech Republic
- RO: Romania
- BG: Bulgaria
- GR: Greece
- PT: Portugal
- IE: Ireland
- NZ: New Zealand
- ZA: South Africa
- IL: Israel
- AE: United Arab Emirates
- TR: Turkey
- TH: Thailand
- MY: Malaysia
- ID: Indonesia
- VN: Vietnam
- PH: Philippines
- CL: Chile
- CO: Colombia
- CR: Costa Rica
- GE: Georgia
- CY: Cyprus

