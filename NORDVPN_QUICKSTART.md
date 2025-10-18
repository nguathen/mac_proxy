# NordVPN Quick Start Guide

## Cài đặt

```bash
# Install dependencies
pip3 install requests

# Hoặc install tất cả dependencies cho Web UI
pip3 install -r webui/requirements.txt
```

## Sử dụng nhanh

### 1. Xem danh sách quốc gia

```bash
bash apply_nordvpn.sh --list-countries
```

### 2. Xem servers theo quốc gia

```bash
# Japan
bash apply_nordvpn.sh --list-servers JP

# Singapore
bash apply_nordvpn.sh --list-servers SG

# United States
bash apply_nordvpn.sh --list-servers US
```

### 3. Áp dụng best server

```bash
# Tự động chọn best server ở Japan và áp dụng vào Wireproxy 1
bash apply_nordvpn.sh --instance 1 --country JP

# Tự động chọn best server ở Singapore và áp dụng vào Wireproxy 2
bash apply_nordvpn.sh --instance 2 --country SG
```

### 4. Áp dụng server cụ thể

```bash
# Áp dụng server cụ thể vào Wireproxy 1
bash apply_nordvpn.sh --instance 1 --server "Japan #720"

# Áp dụng server cụ thể vào Wireproxy 2
bash apply_nordvpn.sh --instance 2 --server "Singapore #528"
```

## Sử dụng Web UI

```bash
# Start Web UI
bash start_webui.sh

# Mở browser
open http://localhost:5000
```

Trong Web UI:
1. Scroll xuống phần "🌍 NordVPN Server Selection"
2. Chọn quốc gia
3. Chọn server (sorted by load)
4. Click "Apply to Wireproxy 1" hoặc "Apply to Wireproxy 2"

## Workflow thực tế

### Scenario 1: Chuyển sang server Japan

```bash
# Xem servers có sẵn
bash apply_nordvpn.sh --list-servers JP

# Áp dụng best server
bash apply_nordvpn.sh --instance 1 --country JP

# Hoặc chọn server cụ thể
bash apply_nordvpn.sh --instance 1 --server "Japan #720"
```

### Scenario 2: Dùng 2 quốc gia khác nhau

```bash
# Instance 1: Japan
bash apply_nordvpn.sh --instance 1 --country JP

# Instance 2: Singapore
bash apply_nordvpn.sh --instance 2 --country SG

# Check status
bash status_all.sh
```

### Scenario 3: Test và switch

```bash
# Test current proxy
curl -x socks5h://127.0.0.1:18181 https://api.ipify.org

# Switch to different server
bash apply_nordvpn.sh --instance 1 --country US

# Test again
curl -x socks5h://127.0.0.1:18181 https://api.ipify.org
```

## Tips

### 1. Cache refresh
Cache tự động refresh sau 1 giờ. Để force refresh:

```bash
python3 nordvpn_cli.py servers --refresh
```

### 2. Tìm server load thấp
Servers luôn được sort theo load từ thấp đến cao.

### 3. Backup tự động
Config cũ được backup tự động với timestamp:
```bash
ls -la wg18181.conf.backup.*
```

### 4. Restore backup
```bash
# Restore từ backup
cp wg18181.conf.backup.1729267890 wg18181.conf

# Restart wireproxy
bash manage_wireproxy.sh restart
```

## Troubleshooting

### Lỗi "Module not found"
```bash
pip3 install requests
```

### Lỗi "No servers found"
```bash
# Force refresh
python3 nordvpn_cli.py servers --refresh
```

### Connection failed
```bash
# Check logs
tail -f logs/wireproxy1.log

# Restart
bash manage_wireproxy.sh restart

# Test
curl -x socks5h://127.0.0.1:18181 https://api.ipify.org
```

## Các quốc gia phổ biến

| Code | Country | Code | Country |
|------|---------|------|---------|
| US | United States | JP | Japan |
| SG | Singapore | GB | United Kingdom |
| DE | Germany | FR | France |
| CA | Canada | AU | Australia |
| NL | Netherlands | SE | Sweden |
| CH | Switzerland | HK | Hong Kong |
| KR | South Korea | TW | Taiwan |

## One-liner examples

```bash
# Quick switch to Japan
bash apply_nordvpn.sh -i 1 -c JP

# Quick switch to US
bash apply_nordvpn.sh -i 2 -c US

# List and pick
bash apply_nordvpn.sh -L SG && bash apply_nordvpn.sh -i 1 -s "Singapore #528"
```

