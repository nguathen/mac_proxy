# Gost Configuration System

Hệ thống cấu hình gost thay thế wireproxy với khả năng lưu trữ và khôi phục cấu hình proxy.

## 🚀 Tính năng chính

- **Lưu trữ cấu hình**: Mỗi gost instance có file config riêng
- **Khôi phục tự động**: Khi khởi động lại, hệ thống sẽ khôi phục cấu hình đã lưu
- **Cập nhật credentials**: Tự động gọi API getpassproxy trước khi start
- **Quản lý qua CLI**: Các lệnh để cấu hình và quản lý instances

## 📁 Cấu trúc file

```
logs/
├── gost1.config          # Cấu hình instance 1
├── gost2.config          # Cấu hình instance 2
├── gost3.config          # ...
├── gost1.pid            # PID file instance 1
├── gost1.log            # Log file instance 1
└── ...
```

## 🔧 Các lệnh quản lý

### Cơ bản
```bash
# Khởi động tất cả instances
./manage_gost.sh start

# Dừng tất cả instances  
./manage_gost.sh stop

# Khởi động lại
./manage_gost.sh restart

# Kiểm tra trạng thái
./manage_gost.sh status
```

### Cấu hình
```bash
# Cấu hình instance với provider và country
./manage_gost.sh config <instance> <provider> <country>

# Ví dụ:
./manage_gost.sh config 1 protonvpn "node-uk-29.protonvpn.net"
./manage_gost.sh config 2 nordvpn "us"
./manage_gost.sh config 3 protonvpn "node-de-15.protonvpn.net"
```

### Xem cấu hình
```bash
# Xem tất cả cấu hình
./manage_gost.sh show-config

# Xem cấu hình instance cụ thể
./manage_gost.sh show-config 1
```

## 📋 Format cấu hình

File config JSON:
```json
{
    "instance": 1,
    "provider": "protonvpn",
    "country": "node-uk-29.protonvpn.net", 
    "proxy_url": "https://user:pass@domain:port",
    "created_at": "2025-01-27T10:30:00Z"
}
```

## 🔄 Quy trình khởi động

1. **Cập nhật credentials**: Gọi API `http://localhost:5267/mmo/getpassproxy`
2. **Đọc cấu hình**: Load từ file `logs/gost{instance}.config`
3. **Cập nhật proxy URL**: Nếu là ProtonVPN, cập nhật lại URL với credentials mới
4. **Khởi động gost**: `gost -L socks5://:port -F proxy_url`

## 🌐 Web UI Integration

Web UI sử dụng các API endpoints:
- `GET /api/gost/config/<instance>` - Lấy cấu hình
- `POST /api/gost/config/<instance>` - Lưu cấu hình  
- `POST /api/gost/<action>` - Điều khiển (start/stop/restart)
- `POST /api/gost/<instance>/<action>` - Điều khiển instance riêng lẻ

## 🧪 Testing

```bash
# Test cấu hình cơ bản
./test_gost_config.sh

# Demo khôi phục cấu hình
./demo_restart.sh
```

## 📝 Lưu ý

- **ProtonVPN**: Credentials được cập nhật tự động mỗi lần start
- **NordVPN**: Sử dụng credentials cố định
- **Port mapping**: Instance 1-7 tương ứng với port 18181-18187
- **Fallback**: Nếu không có config, sử dụng default proxy URL
