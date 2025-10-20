# Fix Apply Server - Provider-Specific Private Keys

## ⚠️ Vấn Đề Trước Đây

Backend **không phân biệt NordVPN hay ProtonVPN**, luôn giữ lại private key cũ từ config file khi apply server mới.

### Kịch Bản Lỗi:

```
1. Config ban đầu: ProtonVPN với private key ProtonVPN
2. User chọn NordVPN server và click "Apply"
3. Backend giữ lại ProtonVPN private key
4. Tạo config NordVPN server + ProtonVPN private key ❌
5. Kết quả: Handshake failed!
```

### Code Cũ (Sai):

```python
# Giữ lại private key cũ từ config
current_config = parse_wireproxy_config(config_path)
if current_config and 'PrivateKey' in current_config.get('interface', {}):
    private_key = current_config['interface']['PrivateKey']  # ❌ Có thể sai provider!

# Apply lên server mới
new_config = nordvpn_api.generate_wireguard_config(
    server=server,
    private_key=private_key,  # ❌ Dùng key của provider cũ
    bind_address=bind_address
)
```

## ✅ Giải Pháp

Mỗi provider API **luôn dùng private key riêng** của nó, không phụ thuộc vào config cũ.

### Code Mới (Đúng):

**NordVPN Apply:**
```python
# ALWAYS use NordVPN private key
from nordvpn_api import DEFAULT_PRIVATE_KEY as NORDVPN_PRIVATE_KEY
private_key = NORDVPN_PRIVATE_KEY  # ✓ Luôn dùng NordVPN key

new_config = nordvpn_api.generate_wireguard_config(
    server=server,
    private_key=private_key,  # ✓ Đúng provider key
    bind_address=bind_address
)
```

**ProtonVPN Apply:**
```python
# ALWAYS use ProtonVPN private key
from protonvpn_api import DEFAULT_PRIVATE_KEY as PROTONVPN_PRIVATE_KEY
private_key = PROTONVPN_PRIVATE_KEY  # ✓ Luôn dùng ProtonVPN key

new_config = protonvpn_api.generate_wireguard_config(
    server=server,
    private_key=private_key,  # ✓ Đúng provider key
    bind_address=bind_address
)
```

## 🔄 Workflow Mới

### Scenario 1: ProtonVPN → NordVPN

```
1. Instance đang chạy ProtonVPN JP
2. User chọn NordVPN US server
3. Click "Apply to Wireproxy 1"
4. Backend:
   - Detect đang apply NordVPN
   - Dùng NORDVPN_PRIVATE_KEY ✓
   - Generate config NordVPN + NordVPN key ✓
5. Restart wireproxy
6. Kết quả: Config đúng provider!
```

### Scenario 2: NordVPN → ProtonVPN

```
1. Instance đang chạy NordVPN US
2. User chọn ProtonVPN EU server
3. Click "Apply to Wireproxy 1"
4. Backend:
   - Detect đang apply ProtonVPN
   - Dùng PROTONVPN_PRIVATE_KEY ✓
   - Generate config ProtonVPN + ProtonVPN key ✓
5. Restart wireproxy
6. Kết quả: Config đúng provider!
```

### Scenario 3: ProtonVPN → ProtonVPN (Same Provider)

```
1. Instance đang chạy ProtonVPN US
2. User chọn ProtonVPN JP server
3. Click "Apply to Wireproxy 1"
4. Backend:
   - Dùng PROTONVPN_PRIVATE_KEY ✓
   - Thay đổi server: US → JP ✓
   - Giữ nguyên private key (cùng provider) ✓
5. Restart wireproxy
6. Kết quả: Switch server OK!
```

## 🎯 Lợi Ích

### 1. Đảm Bảo Tính Nhất Quán

Mỗi provider API luôn dùng đúng private key của nó:
- `api_nordvpn_apply_server()` → `NORDVPN_PRIVATE_KEY`
- `api_protonvpn_apply_server()` → `PROTONVPN_PRIVATE_KEY`

### 2. Không Phụ Thuộc Config Cũ

Không cần parse và kiểm tra config hiện tại để lấy private key. Luôn dùng key từ API module.

### 3. Provider Mix Linh Hoạt

User có thể tự do switch giữa các providers:
```
Wireproxy 1: ProtonVPN US
Wireproxy 2: NordVPN EU
Wireproxy 3: ProtonVPN JP

→ Switch Wireproxy 1 → NordVPN SG
→ Config tự động dùng đúng NordVPN key ✓
```

## 📝 Private Keys Configuration

### Trong Code:

**`nordvpn_api.py`:**
```python
DEFAULT_PRIVATE_KEY = "kOv29TQ+T0iRgzbQI1wjgFovQQPCKqtj7DrnArxdvlg="
```

**`protonvpn_api.py`:**
```python
DEFAULT_PRIVATE_KEY = "mHp/fZJpapyDKr4QT1SVZGg5xgNkpJUKNCXVk7P7yk4="
```

### Import trong WebUI:

```python
from nordvpn_api import DEFAULT_PRIVATE_KEY as NORDVPN_PRIVATE_KEY
from protonvpn_api import DEFAULT_PRIVATE_KEY as PROTONVPN_PRIVATE_KEY
```

## 🔍 Testing

### Test Case 1: Apply NordVPN

```bash
# Hiện tại: ProtonVPN
curl -x socks5h://127.0.0.1:18181 https://api.ipify.org
# → ProtonVPN IP

# Apply NordVPN qua WebUI
# POST /api/nordvpn/apply/1
# { "server_name": "United States #2920" }

# Check config
cat wg18181.conf
# → PrivateKey = kOv29TQ+T0iRgzbQI1wjgFovQQPCKqtj7DrnArxdvlg= ✓
# → Endpoint = NordVPN server IP ✓
```

### Test Case 2: Apply ProtonVPN

```bash
# Hiện tại: NordVPN (hoặc bất kỳ)
# Apply ProtonVPN qua WebUI
# POST /api/protonvpn/apply/1
# { "server_name": "US-FREE#85" }

# Check config
cat wg18181.conf
# → PrivateKey = mHp/fZJpapyDKr4QT1SVZGg5xgNkpJUKNCXVk7P7yk4= ✓
# → Endpoint = ProtonVPN server IP ✓
```

## 📌 Files Updated

- ✅ `webui/app.py` - `api_nordvpn_apply_server()` function
- ✅ `webui/app.py` - `api_protonvpn_apply_server()` function

## 🎉 Kết Quả

Giờ backend **luôn dùng đúng private key** cho từng provider, đảm bảo:
- NordVPN servers → NordVPN private key
- ProtonVPN servers → ProtonVPN private key
- Không còn lỗi handshake do sai private key
- User có thể tự do switch giữa các providers

