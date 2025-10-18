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

## Bước 3: Khởi động Wiresock

Bạn cần có 2 WireGuard config files và chạy wiresock-client:

```bash
# Wiresock 1 - Port 18181
wiresock-client run -config wg1.conf -socks-bind 127.0.0.1:18181 &

# Wiresock 2 - Port 18182
wiresock-client run -config wg2.conf -socks-bind 127.0.0.1:18182 &
```

**Hoặc nếu dùng wireproxy:**

```bash
brew install wireproxy

# Tạo file wireproxy1.conf
cat > wireguard/wireproxy1.conf <<'EOF'
[Interface]
PrivateKey = YOUR_PRIVATE_KEY_1
Address = 10.0.0.2/32

[Peer]
PublicKey = SERVER_PUBLIC_KEY_1
Endpoint = SERVER_IP_1:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25

[Socks5]
BindAddress = 127.0.0.1:18181
EOF

# Tạo file wireproxy2.conf
cat > wireguard/wireproxy2.conf <<'EOF'
[Interface]
PrivateKey = YOUR_PRIVATE_KEY_2
Address = 10.0.0.3/32

[Peer]
PublicKey = SERVER_PUBLIC_KEY_2
Endpoint = SERVER_IP_2:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25

[Socks5]
BindAddress = 127.0.0.1:18182
EOF

# Chạy wireproxy
wireproxy -c wireguard/wireproxy1.conf &
wireproxy -c wireguard/wireproxy2.conf &
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

