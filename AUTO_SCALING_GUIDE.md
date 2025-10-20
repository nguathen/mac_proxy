# Auto-Scaling Wireproxy Instances

## ✅ Tính Năng Auto-Detect

Script `manage_wireproxy.sh` đã được refactor để **tự động phát hiện** tất cả wireproxy config files, hỗ trợ số lượng instances không giới hạn.

## 🔧 Cách Hoạt Động

### Auto-Detection

Script tự động:
1. Tìm tất cả file `wg*.conf` trong thư mục
2. Đọc `BindAddress` để lấy port number
3. Tạo mapping: `config_file:port`
4. Quản lý tất cả instances dựa trên mapping này

### Không Còn Hardcode

**Trước** (hardcode):
```bash
WG1_CONF="wg18181.conf"
WG2_CONF="wg18182.conf"
# Phải thêm WG3_CONF, WG4_CONF...
```

**Sau** (auto-detect):
```bash
get_wireproxy_configs() {
    for conf in wg*.conf; do
        # Auto-detect port from config
    done
}
```

## 📦 Thêm Wireproxy Instance Mới

### Bước 1: Tạo Config File

```bash
# Tạo wg18183.conf, wg18184.conf, wg18185.conf...
# Chỉ cần đặt tên theo pattern: wg*.conf
```

**Ví dụ `wg18183.conf`:**
```ini
[Interface]
PrivateKey = YOUR_PRIVATE_KEY
Address = 10.2.0.4/32
DNS = 10.2.0.1

[Peer]
PublicKey = SERVER_PUBLIC_KEY
Endpoint = SERVER_IP:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25

[Socks5]
BindAddress = 127.0.0.1:18183  # Port phải khác các instance khác
```

### Bước 2: Restart

```bash
./manage_wireproxy.sh restart
```

**Xong!** Script tự động:
- Phát hiện config mới
- Khởi động wireproxy instance mới
- Quản lý PID, logs
- Test connection

## 📊 Test với 3 Instances

```bash
# Hiện tại đang chạy 3 instances
./manage_wireproxy.sh status

# Kết quả:
# ✅ Wireproxy 1 (port 18181): Running
# ✅ Wireproxy 2 (port 18182): Running  
# ✅ Wireproxy 3 (port 18183): Running
```

### Test Connection

```bash
# Instance 1 - ProtonVPN US
curl -x socks5h://127.0.0.1:18181 https://api.ipify.org
# → 159.26.103.221

# Instance 2 - ProtonVPN NL
curl -x socks5h://127.0.0.1:18182 https://api.ipify.org
# → 146.70.136.44

# Instance 3 - ProtonVPN JP
curl -x socks5h://127.0.0.1:18183 https://api.ipify.org
# → 45.14.71.11
```

## 🎯 Use Cases

### Scenario 1: Multi-Location Setup

```bash
# wg18181.conf - US server (port 18181)
# wg18182.conf - EU server (port 18182)
# wg18183.conf - Asia server (port 18183)
# wg18184.conf - Australia server (port 18184)
# ...
```

### Scenario 2: Load Balancing

```bash
# 5 instances cùng location, rotate IP
# wg18181.conf - US-1
# wg18182.conf - US-2
# wg18183.conf - US-3
# wg18184.conf - US-4
# wg18185.conf - US-5
```

### Scenario 3: Provider Mix

```bash
# wg18181.conf - ProtonVPN US
# wg18182.conf - ProtonVPN EU
# wg18183.conf - NordVPN Asia (nếu có valid key)
# wg18184.conf - ProtonVPN JP
```

## 📝 Naming Convention

### Config Files

**Pattern:** `wg{PORT}.conf`

Ví dụ:
- `wg18181.conf` → Port 18181
- `wg18182.conf` → Port 18182
- `wg18183.conf` → Port 18183
- `wg20001.conf` → Port 20001 (cũng OK!)

### Ports

**Khuyến nghị:**
- Sequential: 18181, 18182, 18183, ...
- Hoặc custom: 20001, 20002, 20003, ...
- **Quan trọng:** Mỗi port phải unique!

### Address (trong config)

**Phải unique cho mỗi instance:**
```ini
# wg18181.conf
Address = 10.2.0.2/32

# wg18182.conf  
Address = 10.2.0.3/32

# wg18183.conf
Address = 10.2.0.4/32

# wg18184.conf
Address = 10.2.0.5/32
```

## 🔍 Auto-Generated Files

Script tự động tạo:

```
logs/
├── wireproxy1.pid      # PID file cho instance 1
├── wireproxy1.log      # Log file cho instance 1
├── wireproxy2.pid
├── wireproxy2.log
├── wireproxy3.pid
├── wireproxy3.log
└── ...
```

## 🚀 Script Commands

### Start All

```bash
./manage_wireproxy.sh start
```

### Stop All

```bash
./manage_wireproxy.sh stop
```

### Restart All

```bash
./manage_wireproxy.sh restart
```

### Status Check

```bash
./manage_wireproxy.sh status
```

## ⚡ Performance

Script đã được test với:
- ✅ 2 instances (ban đầu)
- ✅ 3 instances (test)
- 🔮 Lý thuyết: Không giới hạn (chỉ giới hạn bởi tài nguyên hệ thống)

## 🛠️ Maintenance

### Xóa Instance

```bash
# Xóa config file
rm wg18183.conf

# Restart
./manage_wireproxy.sh restart
# → Script tự động không start instance đó nữa
```

### Thay Đổi Server

```bash
# Edit config
nano wg18183.conf
# Thay Endpoint và PublicKey

# Restart
./manage_wireproxy.sh restart
```

### View Logs

```bash
# All logs
tail -f logs/wireproxy*.log

# Specific instance
tail -f logs/wireproxy3.log

# Check handshake
grep "Received handshake response" logs/wireproxy3.log
```

## 📋 Checklist Thêm Instance Mới

- [ ] Tạo file config `wg{PORT}.conf`
- [ ] Set unique `BindAddress` port
- [ ] Set unique `Address` IP
- [ ] Set valid `PrivateKey` và `PublicKey`
- [ ] Set `Endpoint` server IP
- [ ] Run `./manage_wireproxy.sh restart`
- [ ] Check `./manage_wireproxy.sh status`
- [ ] Test `curl -x socks5h://127.0.0.1:{PORT} https://api.ipify.org`

## 🎉 Benefits

1. **Zero Code Changes**: Thêm instance chỉ cần tạo config file
2. **Auto-Management**: Script tự động quản lý tất cả
3. **Scalable**: Không giới hạn số lượng instances
4. **Flexible**: Mix nhiều providers, locations
5. **Easy Cleanup**: Xóa config là xóa instance

