# HAProxy 7890 Service

HAProxy service chạy trên port 7890 với backend Cloudflare WARP.

## Cấu trúc thư mục

```
services/haproxy_7890/
├── config/
│   └── haproxy_7890.cfg          # Config file HAProxy
├── logs/                         # Log files và PID files
├── start_haproxy_7890.sh         # Script khởi động
├── stop_haproxy_7890.sh          # Script dừng
├── warp_monitor.sh               # Auto-reconnect WARP monitor
├── com.macproxy.haproxy7890.plist # LaunchAgent plist
├── install_haproxy7890_autostart.sh # Cài đặt autostart
└── uninstall_haproxy7890_autostart.sh # Gỡ autostart
```

## Sử dụng

### Khởi động thủ công
```bash
cd services/haproxy_7890
./start_haproxy_7890.sh
```

### Dừng service
```bash
cd services/haproxy_7890
./stop_haproxy_7890.sh
```

### Cài đặt autostart (chạy khi Mac khởi động)
```bash
cd services/haproxy_7890
./install_haproxy7890_autostart.sh
```

### Gỡ autostart
```bash
cd services/haproxy_7890
./uninstall_haproxy7890_autostart.sh
```

## Thông tin

- **SOCKS5 Proxy**: `socks5://0.0.0.0:7890`
- **Backend**: Cloudflare WARP (`127.0.0.1:8111`)
- **Auto-reconnect WARP**: Tự động kiểm tra và reconnect WARP mỗi 30 giây
- **Tối ưu**: Đã bỏ stats dashboard, logging, giảm maxconn để tiết kiệm tài nguyên
- **Tài nguyên**: ~12MB RAM, CPU < 0.1%

## WARP Auto-Reconnect

Service tự động monitor và reconnect WARP nếu cần:

```bash
# Kiểm tra trạng thái WARP monitor
./haproxy_7890.sh warp-status

# Kiểm tra và reconnect WARP ngay lập tức
./haproxy_7890.sh warp-check
```

WARP monitor sẽ:
- Kiểm tra WARP status mỗi 30 giây
- Tự động reconnect nếu WARP không hoạt động
- Ghi log vào `logs/warp_monitor.log`

## Tối ưu hóa

Config đã được tối ưu cho chạy 24/7:
- ✅ Bỏ stats dashboard (tiết kiệm tài nguyên)
- ✅ Bỏ logging (giảm I/O)
- ✅ Giảm maxconn xuống 2048
- ✅ Tối ưu timeout và retry settings
- ✅ Quiet mode để giảm output

## Lưu ý

- Service này được tách riêng để tránh bị ảnh hưởng bởi các script quản lý khác
- Tất cả logs và PID files được lưu trong thư mục `logs/` của service này
- WARP monitor tự động khởi động cùng với HAProxy
- Service tự động reconnect WARP nếu gặp vấn đề
- Service tự động khởi động khi Mac boot (sau khi cài đặt autostart)
- Port 7890 được bảo vệ, không bị auto cleanup dừng

