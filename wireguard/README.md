# Cấu hình WireGuard với SOCKS5 Proxy

Để WireGuard hoạt động như SOCKS5 proxy trên các cổng 18181 và 18182, bạn có thể sử dụng một trong các phương pháp sau:

## Phương pháp 1: Sử dụng wireproxy (Khuyến nghị)

### Cài đặt wireproxy

```bash
brew install wireproxy
```

### Tạo file cấu hình wireproxy1.conf

```toml
[Interface]
PrivateKey = YOUR_PRIVATE_KEY_HERE
Address = 10.0.0.2/32
DNS = 1.1.1.1

[Peer]
PublicKey = SERVER_PUBLIC_KEY_HERE
Endpoint = SERVER_IP:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25

[Socks5]
BindAddress = 127.0.0.1:18181
```

### Tạo file cấu hình wireproxy2.conf

```toml
[Interface]
PrivateKey = YOUR_PRIVATE_KEY_HERE_2
Address = 10.0.0.3/32
DNS = 1.1.1.1

[Peer]
PublicKey = SERVER_PUBLIC_KEY_HERE_2
Endpoint = SERVER_IP_2:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25

[Socks5]
BindAddress = 127.0.0.1:18182
```

### Chạy wireproxy

```bash
# Terminal 1 - WireGuard 1
wireproxy -c wireguard/wireproxy1.conf

# Terminal 2 - WireGuard 2
wireproxy -c wireguard/wireproxy2.conf
```

## Phương pháp 2: Sử dụng wg-socks-proxy

### Cài đặt

```bash
# Tải từ GitHub
git clone https://github.com/octeep/wireproxy.git
cd wireproxy
go build
```

### Sử dụng tương tự wireproxy

## Phương pháp 3: WireGuard + microsocks

### Cài đặt microsocks

```bash
git clone https://github.com/rofl0r/microsocks.git
cd microsocks
make
sudo make install
```

### Khởi động WireGuard interface

```bash
sudo wg-quick up wg1
sudo wg-quick down wg2
```

### Chạy microsocks qua WireGuard interface

```bash
# Bind microsocks vào interface wg1
microsocks -i 127.0.0.1 -p 18181 -b wg1

# Bind microsocks vào interface wg2
microsocks -i 127.0.0.1 -p 18182 -b wg2
```

## Ví dụ cấu hình WireGuard cơ bản

### wg1.conf

```ini
[Interface]
PrivateKey = <YOUR_PRIVATE_KEY>
Address = 10.0.0.2/32
DNS = 1.1.1.1, 1.0.0.1

[Peer]
PublicKey = <SERVER_PUBLIC_KEY>
Endpoint = <SERVER_IP>:51820
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
```

### wg2.conf

```ini
[Interface]
PrivateKey = <YOUR_PRIVATE_KEY_2>
Address = 10.0.0.3/32
DNS = 1.1.1.1, 1.0.0.1

[Peer]
PublicKey = <SERVER_PUBLIC_KEY_2>
Endpoint = <SERVER_IP_2>:51820
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
```

## Kiểm tra kết nối

```bash
# Kiểm tra WireGuard proxy 1
curl --socks5 127.0.0.1:18181 https://ipinfo.io

# Kiểm tra WireGuard proxy 2
curl --socks5 127.0.0.1:18182 https://ipinfo.io
```

## Tự động khởi động với launchd (macOS)

Tạo file `~/Library/LaunchAgents/com.wireproxy1.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.wireproxy1</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/wireproxy</string>
        <string>-c</string>
        <string>/Users/YOUR_USERNAME/mac_proxy/wireguard/wireproxy1.conf</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/wireproxy1.err</string>
    <key>StandardOutPath</key>
    <string>/tmp/wireproxy1.out</string>
</dict>
</plist>
```

Tải và khởi động:

```bash
launchctl load ~/Library/LaunchAgents/com.wireproxy1.plist
launchctl start com.wireproxy1
```

## Lưu ý

1. **Bảo mật:** Không chia sẻ private key của bạn
2. **Quyền truy cập:** Một số phương pháp cần quyền sudo
3. **Firewall:** Đảm bảo firewall cho phép kết nối WireGuard
4. **DNS:** Cấu hình DNS phù hợp để tránh DNS leak

