# Lấy NordVPN Private Key Chính Thức

## ⚠️ VẤN ĐỀ

Private key hiện tại (`lOv29TQ+T0iRgzbQI1wjgFovQQPCKqtj7DrnArxdvlg=`) **KHÔNG HỢP LỆ** với NordVPN servers.

Kết quả:
- Wireproxy liên tục lỗi: `Handshake did not complete after 5 seconds, retrying`
- Không thể kết nối được

## NGUYÊN NHÂN

**NordVPN yêu cầu private key phải được generate từ account của bạn**, không cho phép dùng private key tự tạo bằng `wg genkey`.

Khác với:
- **ProtonVPN**: Cho phép dùng bất kỳ private key nào → wireproxy hoạt động ổn định
- **NordVPN**: Chỉ chấp nhận private key được cấp chính thức → wireproxy bị từ chối handshake

## GIẢI PHÁP

### Cách 1: Lấy Private Key từ NordVPN Dashboard

1. Đăng nhập: https://my.nordaccount.com/
2. Vào **Services** → **NordVPN**
3. Chọn **Manual Setup** hoặc **Advanced Configuration**
4. Tìm mục **WireGuard**
5. Click **Generate new private key** (hoặc copy nếu đã có)
6. Copy Private Key

### Cách 2: Qua NordVPN Desktop App

1. Mở NordVPN app
2. Settings → Advanced
3. Tìm "WireGuard Private Key"
4. Generate hoặc copy

### Cách 3: Dùng ProtonVPN thay NordVPN

Vì ProtonVPN hoạt động ổn định với private key tự tạo, bạn có thể:

```bash
# Dùng ProtonVPN cho cả 2 wireproxy instances
# wg18181.conf - ProtonVPN US
# wg18182.conf - ProtonVPN JP/UK/khác
```

## CẬP NHẬT PRIVATE KEY

Sau khi có NordVPN private key hợp lệ:

```bash
# 1. Cập nhật vào config
nano wg18181.conf
# Thay dòng: PrivateKey = NEW_NORDVPN_PRIVATE_KEY

# 2. Cập nhật vào code
nano nordvpn_api.py
# Thay DEFAULT_PRIVATE_KEY = "NEW_NORDVPN_PRIVATE_KEY"

# 3. Restart wireproxy
./manage_wireproxy.sh restart

# 4. Test
curl -x socks5h://127.0.0.1:18181 https://api.ipify.org
```

## KIỂM TRA LOG

```bash
# Log thành công sẽ thấy:
tail -f logs/wireproxy1.log | grep "Received handshake response"

# Log thất bại sẽ thấy:
tail -f logs/wireproxy1.log | grep "Handshake did not complete"
```

## HIỆN TRẠNG

- ✅ **Wireproxy 2 (ProtonVPN)**: Hoạt động hoàn hảo
  - Private Key: `mHp/fZJpapyDKr4QT1SVZGg5xgNkpJUKNCXVk7P7yk4=` ✓
  - Handshake: Thành công ✓
  - Connection: OK ✓

- ❌ **Wireproxy 1 (NordVPN)**: Không hoạt động
  - Private Key: `lOv29TQ+T0iRgzbQI1wjgFovQQPCKqtj7DrnArxdvlg=` ✗
  - Handshake: Thất bại liên tục ✗
  - Connection: Failed ✗

## KHUYẾN NGHỊ

**Tạm thời dùng ProtonVPN cho cả 2 instances** cho đến khi có NordVPN private key hợp lệ.
