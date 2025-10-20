# Tóm Tắt Cấu Hình Wireproxy

## ✅ Cấu Hình Hiện Tại (Đã Hoạt Động)

### Wireproxy 1 (Port 18181)
- **Provider**: ProtonVPN
- **Location**: US - Seattle
- **Private Key**: `mHp/fZJpapyDKr4QT1SVZGg5xgNkpJUKNCXVk7P7yk4=`
- **Server IP**: 149.40.51.230:51820
- **Public Key**: `gDmb0KtRVAd2UYnKs0UkXqS0tgcqk7UNw6yTb+loQ1c=`
- **Status**: ✅ Hoạt động
- **Test**: `curl -x socks5h://127.0.0.1:18181 https://api.ipify.org` → `159.26.103.221`

### Wireproxy 2 (Port 18182)
- **Provider**: ProtonVPN
- **Location**: Netherlands
- **Private Key**: `mHp/fZJpapyDKr4QT1SVZGg5xgNkpJUKNCXVk7P7yk4=`
- **Server IP**: 146.70.136.35:51820
- **Public Key**: `8d4nU7Z/xzX9cK3wM77mf3Ge+DbQA2tnLaQzhk3+dFI=`
- **Status**: ✅ Hoạt động
- **Test**: `curl -x socks5h://127.0.0.1:18182 https://api.ipify.org` → `146.70.136.44`

## 🔑 Private Keys

### NordVPN
```
kOv29TQ+T0iRgzbQI1wjgFovQQPCKqtj7DrnArxdvlg=
```
⚠️ **KHÔNG HOẠT ĐỘNG** - Key này không được NordVPN servers chấp nhận

### ProtonVPN
```
mHp/fZJpapyDKr4QT1SVZGg5xgNkpJUKNCXVk7P7yk4=
```
✅ **HOẠT ĐỘNG** - Đã đăng ký với ProtonVPN account

## 📊 Nguyên Nhân Vấn Đề

### Tại sao NordVPN không hoạt động với wireproxy?

1. **Yêu cầu Private Key chính thức**
   - NordVPN chỉ chấp nhận private key được generate từ account
   - Private key tự tạo bằng `wg genkey` bị từ chối
   - Log: `Handshake did not complete after 5 seconds, retrying`

2. **Ứng dụng NordVPN chính thức hoạt động tốt vì:**
   - Có private key + credentials khi đăng nhập
   - Được authenticate đầy đủ với NordVPN servers

3. **ProtonVPN cho phép private key tự tạo**
   - Miễn là private key được đăng ký vào account
   - Wireproxy hoạt động ổn định
   - Log: `Received handshake response` thành công

## 🎯 Giải Pháp Đã Áp Dụng

**Dùng ProtonVPN cho cả 2 instances** với cùng private key nhưng khác server:
- Instance 1: US server (Seattle)
- Instance 2: NL server (Netherlands)

## 🔧 Các Lệnh Hữu Ích

### Kiểm tra status
```bash
./manage_wireproxy.sh status
```

### Restart
```bash
./manage_wireproxy.sh restart
```

### Test connection
```bash
# Wireproxy 1
curl -x socks5h://127.0.0.1:18181 https://api.ipify.org

# Wireproxy 2
curl -x socks5h://127.0.0.1:18182 https://api.ipify.org
```

### Xem logs
```bash
tail -f logs/wireproxy1.log
tail -f logs/wireproxy2.log

# Kiểm tra handshake
grep "Received handshake response" logs/wireproxy1.log
```

### Thay đổi server
```bash
# Edit config
nano wg18181.conf
nano wg18182.conf

# Restart
./manage_wireproxy.sh restart
```

## 📝 Lưu Ý Quan Trọng

1. **ProtonVPN FREE servers hoạt động tốt** với wireproxy
2. **Cùng private key có thể dùng nhiều servers** khác nhau
3. **Address phải khác nhau** giữa các instances:
   - wg18181.conf: `Address = 10.2.0.3/32`
   - wg18182.conf: `Address = 10.2.0.2/32`
4. **DNS nên dùng VPN DNS**: `DNS = 10.2.0.1`
5. **Handshake cần 5-10 giây** để thiết lập kết nối đầu tiên

## 🚀 Để Dùng NordVPN

Nếu muốn dùng NordVPN, cần:

1. Đăng nhập https://my.nordaccount.com/
2. Services → NordVPN → Manual Setup → WireGuard
3. Generate private key mới
4. Cập nhật vào `wg18181.conf` và `nordvpn_api.py`
5. Restart wireproxy

Chi tiết xem: `NORDVPN_PRIVATE_KEY_GUIDE.md`

