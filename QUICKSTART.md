# 🚀 Quick Start Guide

## Bước 1: Cài đặt HAProxy

```bash
brew install haproxy
```

## Bước 2: Cấu hình Cloudflare WARP

```bash
# Tải từ: https://1.1.1.1/
warp-cli register
warp-cli set-mode proxy
warp-cli set-proxy-port 8111
warp-cli connect
```

## Bước 3: Chuẩn bị Wireproxy Config

**Lưu ý:** Nếu bạn đang chạy wireproxy ở dự án khác trên port 18181/18182, hệ thống sẽ tự động kill và restart.

```bash
# Kiểm tra port có đang được dùng không
./check_ports.sh

# Kill nếu cần
./kill_ports.sh
```

Bạn đã có 2 config files: `wg18181.conf` và `wg18182.conf`. Chỉnh sửa Endpoint nếu cần:

```bash
# Edit wg18181.conf
nano wg18181.conf
# Thay đổi dòng: Endpoint = 81.17.123.100:51820

# Edit wg18182.conf  
nano wg18182.conf
# Thay đổi dòng: Endpoint = 193.9.33.3:51820
```

## Bước 4: Khởi động HAProxy

```bash
chmod +x *.sh
./start_all.sh
```

## Bước 5: Kiểm tra

```bash
# Xem trạng thái
./status_all.sh

# Test proxy
curl -x socks5h://127.0.0.1:7891 https://api.ipify.org
curl -x socks5h://127.0.0.1:7892 https://api.ipify.org

# Xem stats dashboard
open http://127.0.0.1:8091/haproxy?stats
open http://127.0.0.1:8092/haproxy?stats
# Username: admin, Password: admin123
```

## 🎉 Hoàn thành!

Bây giờ bạn có:
- **HAProxy 1** trên `socks5://0.0.0.0:7891` (backend: wiresock 18181 → WARP 8111)
- **HAProxy 2** trên `socks5://0.0.0.0:7892` (backend: wiresock 18182 → WARP 8111)

## 📊 Monitoring

```bash
# Xem logs real-time
tail -f logs/haproxy_health_*.log

# Test liên tục
./test_proxy.sh
```

## 🛑 Dừng hệ thống

```bash
./stop_all.sh
```

## ⚙️ Tùy chỉnh

Sửa file `start_all.sh` để thay đổi:
- Cổng SOCKS
- Cổng Stats
- Health check interval
- Stats authentication
- Wiresock backends

