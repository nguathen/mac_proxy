#!/usr/bin/env python3
"""
Auto Credential Updater
Tự động nhận biết lỗi 407 Proxy Authentication Required và cập nhật credentials
"""

import os
import time
import json
import subprocess
import requests
from datetime import datetime
from typing import Dict, List, Optional
import threading
import signal
import sys

# Import protonvpn_service để lấy credentials
try:
    from protonvpn_service import Instance as ProtonVpnServiceInstance
except ImportError:
    ProtonVpnServiceInstance = None

class AutoCredentialUpdater:
    def __init__(self, base_dir: str = None):
        # Auto-detect base directory if not provided
        if base_dir is None:
            # Get directory of this script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            # If script is in root, use script_dir; otherwise use parent
            if os.path.basename(script_dir) == 'mac_proxy' or os.path.exists(os.path.join(script_dir, 'manage_gost.sh')):
                base_dir = script_dir
            else:
                # Try to find mac_proxy directory
                current = script_dir
                while current != os.path.dirname(current):
                    if os.path.exists(os.path.join(current, 'manage_gost.sh')):
                        base_dir = current
                        break
                    current = os.path.dirname(current)
                if base_dir is None:
                    # Fallback: use script directory or home directory
                    base_dir = script_dir if os.path.exists(os.path.join(script_dir, 'manage_gost.sh')) else os.path.expanduser("~/mac_proxy")
        self.base_dir = base_dir
        self.log_dir = os.path.join(base_dir, "logs")
        self.config_dir = os.path.join(base_dir, "config")
        self.running = False
        self.monitor_thread = None
        
    def start_monitoring(self):
        """Bắt đầu monitoring tự động"""
        if self.running:
            print("⚠️  Auto updater already running")
            return
            
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("✅ Auto credential updater started")
        
    def stop_monitoring(self):
        """Dừng monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("🛑 Auto credential updater stopped")
        
    def _monitor_loop(self):
        """Vòng lặp monitoring chính"""
        last_cleanup = 0
        while self.running:
            try:
                # Đảm bảo config cho port 7890 luôn tồn tại (tự động tạo lại nếu bị mất)
                self._ensure_gost_7890_config()
                
                # Check credentials every 30 seconds
                self._check_and_update_credentials()
                
                # Check for unused services every 5 minutes
                current_time = time.time()
                if current_time - last_cleanup >= 300:  # 5 minutes
                    self._cleanup_unused_services()
                    last_cleanup = current_time
                
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                print(f"❌ Error in monitor loop: {e}")
                time.sleep(60)  # Wait longer on error
                
    def _ensure_gost_7890_config(self):
        """Đảm bảo config cho port 7890 luôn tồn tại (tự động tạo lại nếu bị mất)"""
        try:
            gost_7890_config = os.path.join(self.config_dir, "gost_7890.config")
            if not os.path.exists(gost_7890_config):
                print(f"🛡️  Port 7890 config missing, recreating...")
                config_data = {
                    "port": "7890",
                    "provider": "warp",
                    "country": "cloudflare",
                    "proxy_url": "socks5://127.0.0.1:8111",
                    "proxy_host": "127.0.0.1",
                    "proxy_port": "8111",
                    "created_at": datetime.now().isoformat() + 'Z'
                }
                with open(gost_7890_config, 'w') as f:
                    json.dump(config_data, f, indent=2)
                print(f"✅ Port 7890 config recreated")
        except Exception as e:
            print(f"⚠️  Error ensuring gost 7890 config: {e}")
    
    def _check_and_update_credentials(self):
        """Kiểm tra và cập nhật credentials nếu cần"""
        # Tìm tất cả ProtonVPN config files
        protonvpn_configs = self._find_protonvpn_configs()
        
        for config_file in protonvpn_configs:
            if self._has_authentication_errors(config_file):
                print(f"🔄 Detected auth errors for {config_file}, updating credentials...")
                self._update_credentials_for_config(config_file)
                
    def _find_protonvpn_configs(self) -> List[str]:
        """Tìm tất cả ProtonVPN config files"""
        configs = []
        for filename in os.listdir(self.config_dir):
            if filename.startswith("gost_") and filename.endswith(".config"):
                config_path = os.path.join(self.config_dir, filename)
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                        if config.get('provider') == 'protonvpn':
                            configs.append(config_path)
                except Exception:
                    continue
        return configs
        
    def _has_authentication_errors(self, config_file: str) -> bool:
        """Kiểm tra xem có lỗi authentication trong log không"""
        port = self._extract_port_from_config_file(config_file)
        if not port:
            return False
            
        log_file = os.path.join(self.log_dir, f"gost_{port}.log")
        if not os.path.exists(log_file):
            return False
            
        # Đọc 100 dòng cuối của log file để phát hiện lỗi tốt hơn
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                recent_lines = lines[-100:] if len(lines) > 100 else lines
                
                # Đếm số lỗi 407 và i/o timeout gần đây
                auth_error_count = 0
                timeout_error_count = 0
                
                for line in recent_lines:
                    if '407 Proxy Authentication Required' in line:
                        # Kiểm tra timestamp (trong 5 phút gần nhất)
                        if self._is_recent_error_simple(line):
                            auth_error_count += 1
                    elif 'i/o timeout' in line:
                        # Kiểm tra timestamp (trong 5 phút gần nhất)
                        if self._is_recent_error_simple(line):
                            timeout_error_count += 1
                
                # Nếu có lỗi 407 (authentication), cần cập nhật credentials
                if auth_error_count > 0:
                    print(f"🔍 Found {auth_error_count} authentication errors (407) for port {port}")
                    return True
                
                # Nếu có quá nhiều timeout (>= 5), có thể là server không hoạt động
                # Nhưng không phải là lỗi authentication, nên không cập nhật credentials
                if timeout_error_count >= 5:
                    print(f"⚠️  Found {timeout_error_count} timeout errors for port {port} (server may be down)")
                    
        except Exception as e:
            print(f"❌ Error reading log file {log_file}: {e}")
            
        return False
        
    def _is_recent_error(self, log_line: str) -> bool:
        """Kiểm tra xem lỗi có gần đây không (trong 5 phút)"""
        try:
            # Parse timestamp từ log line
            if '"time":"' in log_line:
                time_start = log_line.find('"time":"') + 8
                time_end = log_line.find('"', time_start)
                if time_end > time_start:
                    time_str = log_line[time_start:time_end]
                    # Parse ISO format: 2025-10-23T15:09:32.840+07:00
                    log_time = datetime.fromisoformat(time_str.replace('+07:00', ''))
                    now = datetime.now()
                    time_diff = (now - log_time).total_seconds()
                    return time_diff < 300  # 5 minutes
        except Exception:
            pass
        return False
    
    def _is_recent_error_simple(self, log_line: str) -> bool:
        """Kiểm tra lỗi gần đây cho gost log format: 2025/11/17 18:25:55"""
        try:
            # Parse timestamp từ gost log format: 2025/11/17 18:25:55
            if log_line.startswith('20'):
                parts = log_line.split(' ')
                if len(parts) >= 2:
                    date_str = parts[0]  # 2025/11/17
                    time_str = parts[1]  # 18:25:55
                    datetime_str = f"{date_str} {time_str}"
                    log_time = datetime.strptime(datetime_str, '%Y/%m/%d %H:%M:%S')
                    now = datetime.now()
                    time_diff = (now - log_time).total_seconds()
                    return time_diff < 300  # 5 minutes
        except Exception:
            pass
        return True  # Nếu không parse được timestamp, coi như recent để trigger update
        
    def _extract_port_from_config_file(self, config_file: str) -> Optional[str]:
        """Trích xuất port từ tên config file"""
        filename = os.path.basename(config_file)
        if filename.startswith("gost_") and filename.endswith(".config"):
            return filename[5:-7]  # Remove "gost_" and ".config"
        return None
        
    def _update_credentials_for_config(self, config_file: str):
        """Cập nhật credentials cho một config file"""
        try:
            # Lấy auth token mới
            auth_token = self._get_fresh_auth_token()
            if not auth_token:
                print("❌ Failed to get fresh auth token")
                return False
                
            # Đọc config hiện tại
            with open(config_file, 'r') as f:
                config = json.load(f)
                
            # Trích xuất host và port từ proxy_url hiện tại
            current_proxy_url = config.get('proxy_url', '')
            if current_proxy_url:
                # Parse URL: https://username:password@host:port hoặc https://token@host:port
                if '@' in current_proxy_url:
                    parts = current_proxy_url.split('@', 1)
                    if len(parts) == 2:
                        host_port = parts[1]
                        if ':' in host_port:
                            proxy_host, proxy_port = host_port.split(':', 1)
                            
                            # Tạo proxy_url mới với auth token mới (username:password format)
                            new_proxy_url = f"https://{auth_token}@{proxy_host}:{proxy_port}"
                            config['proxy_url'] = new_proxy_url
                            config['updated_at'] = datetime.now().isoformat()
                            
                            # Lưu config mới
                            with open(config_file, 'w') as f:
                                json.dump(config, f, indent=2)
                                
                            # Restart gost service
                            port = self._extract_port_from_config_file(config_file)
                            if port:
                                self._restart_gost_service(port)
                                print(f"✅ Updated credentials for port {port}")
                                return True
            else:
                print(f"❌ No proxy_url found in config {config_file}")
                    
        except Exception as e:
            print(f"❌ Error updating credentials for {config_file}: {e}")
            
        return False
        
    def _get_fresh_auth_token(self) -> Optional[str]:
        """Lấy auth token mới từ protonvpn_service (config_token.txt)"""
        try:
            # Sử dụng protonvpn_service để lấy username:password
            if ProtonVpnServiceInstance and ProtonVpnServiceInstance.user_name and ProtonVpnServiceInstance.password:
                return f"{ProtonVpnServiceInstance.user_name}:{ProtonVpnServiceInstance.password}"
            else:
                print("❌ Failed to get ProtonVPN credentials from protonvpn_service")
                return None
        except Exception as e:
            print(f"❌ Error getting fresh auth token: {e}")
        return None
        
    def _restart_gost_service(self, port: str):
        """Restart gost service cho port cụ thể"""
        try:
            cmd = f"cd {self.base_dir} && ./manage_gost.sh restart-port {port}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print(f"✅ Restarted gost service on port {port}")
            else:
                print(f"❌ Failed to restart gost service on port {port}: {result.stderr}")
        except Exception as e:
            print(f"❌ Error restarting gost service on port {port}: {e}")
            
    def _cleanup_unused_services(self):
        """Dọn dẹp các service không sử dụng dựa trên profile count API từ cả 2 nguồn"""
        try:
            used_ports = set()
            
            # API 1: localhost
            try:
                response1 = requests.get("https://g.proxyit.online/api/profiles/count-open", timeout=10)
                if response1.status_code == 200:
                    data1 = response1.json()
                    if isinstance(data1, list):
                        ports1 = self._extract_ports_from_profiles(data1)
                        used_ports.update(ports1)
                        print(f"🔍 Localhost API: Found {len(ports1)} used ports: {sorted(ports1)}")
                    else:
                        print(f"❌ Localhost API unexpected format: {type(data1)}")
                else:
                    print(f"❌ Localhost API failed: {response1.status_code}")
            except Exception as e:
                print(f"❌ Error calling localhost API: {e}")
            
            # API 2: btm2025.ddns.net
            try:
                response2 = requests.get("https://g.proxyit.online/api/profiles/count-open", timeout=10)
                if response2.status_code == 200:
                    data2 = response2.json()
                    if isinstance(data2, list):
                        ports2 = self._extract_ports_from_profiles(data2)
                        used_ports.update(ports2)
                        print(f"🔍 BTM2025 API: Found {len(ports2)} used ports: {sorted(ports2)}")
                    else:
                        print(f"❌ BTM2025 API unexpected format: {type(data2)}")
                else:
                    print(f"❌ BTM2025 API failed: {response2.status_code}")
            except Exception as e:
                print(f"❌ Error calling BTM2025 API: {e}")
            
            print(f"🔍 Total unique used ports: {len(used_ports)} - {sorted(used_ports)}")
            
            # Tìm và dọn dẹp các service không sử dụng
            self._cleanup_unused_gost_services(used_ports)
            
        except Exception as e:
            print(f"❌ Error in cleanup unused services: {e}")
            
    def _extract_ports_from_profiles(self, profiles):
        """Trích xuất ports từ danh sách profiles"""
        ports = set()
        for profile in profiles:
            proxy = profile.get('proxy', '')
            if proxy and ':' in proxy:
                # Parse proxy format: "socks5://host:PORT:server:proxy_port" hoặc "127.0.0.1:PORT:server:proxy_port"
                # Format: socks5://proxyy.zapto.org:7891:lk-01.protonvpn.net:4465
                # Port gost là port thứ 2 (sau host)
                
                # Remove socks5:// prefix nếu có
                proxy_str = proxy
                if proxy_str.startswith('socks5://'):
                    proxy_str = proxy_str[9:]  # Remove "socks5://"
                
                parts = proxy_str.split(':')
                if len(parts) >= 2:
                    try:
                        # Port gost là phần thứ 2 (index 1) sau host
                        port_str = parts[1].strip()
                        if port_str.isdigit():
                            port = int(port_str)
                            # Chỉ lấy port trong khoảng hợp lệ cho gost (7891-7999)
                            if 7891 <= port <= 7999:
                                ports.add(port)
                    except (ValueError, IndexError):
                        pass
        return ports
            
    def _cleanup_unused_gost_services(self, used_ports):
        """Dọn dẹp Gost services không sử dụng"""
        try:
            # Tìm tất cả Gost config files
            for filename in os.listdir(self.config_dir):
                if filename.startswith("gost_") and filename.endswith(".config"):
                    port_str = filename[5:-7]  # Remove "gost_" and ".config"
                    try:
                        gost_port = int(port_str)
                        
                        # Bỏ qua port 7890 vì đây là Gost độc lập cho Cloudflare WARP
                        if gost_port == 7890:
                            print(f"🛡️  Protecting Gost 7890 (Cloudflare WARP service)")
                            continue
                        
                        # Nếu Gost port trực tiếp được sử dụng, không xóa
                        if gost_port in used_ports:
                            print(f"🛡️  Protecting Gost {gost_port} (directly used)")
                            continue
                        
                        # Kiểm tra thời gian tạo trước khi xóa
                        if not self._should_cleanup_service(gost_port, "gost"):
                            continue
                            
                        # Nếu không được sử dụng, xóa Gost service
                        print(f"🧹 Cleaning up unused Gost service on port {gost_port}")
                        self._stop_and_remove_gost_service(gost_port)
                        
                    except ValueError:
                        continue
        except Exception as e:
            print(f"❌ Error cleaning up Gost services: {e}")
            
    def _stop_and_remove_gost_service(self, port):
        """Dừng và xóa Gost service"""
        try:
            # Bảo vệ tuyệt đối: không bao giờ xóa port 7890 (WARP service)
            if port == 7890:
                print(f"🛡️  Cannot remove protected Gost service on port {port} (WARP service)")
                return
            
            # Stop gost process
            pid_file = os.path.join(self.log_dir, f"gost_{port}.pid")
            if os.path.exists(pid_file):
                try:
                    with open(pid_file, 'r') as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 15)  # SIGTERM
                    print(f"✅ Stopped Gost process {pid} on port {port}")
                except (OSError, ValueError, ProcessLookupError):
                    pass
            
            # Kill any process on this port
            try:
                cmd = f"lsof -ti:{port} | xargs kill -9 2>/dev/null || true"
                subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
            except:
                pass
            
            # Remove config file (double check: không bao giờ xóa port 7890)
            config_file = os.path.join(self.config_dir, f"gost_{port}.config")
            if port == 7890:
                print(f"🛡️  Cannot remove protected config file for port {port}")
                return
            if os.path.exists(config_file):
                os.remove(config_file)
                print(f"✅ Removed Gost config for port {port}")
                
            # Remove PID file
            if os.path.exists(pid_file):
                os.remove(pid_file)
                
            # Remove log file
            log_file = os.path.join(self.log_dir, f"gost_{port}.log")
            if os.path.exists(log_file):
                os.remove(log_file)
                
            print(f"✅ Cleaned up Gost service on port {port}")
            
        except Exception as e:
            print(f"❌ Error stopping Gost service on port {port}: {e}")
            
    def manual_update_all(self):
        """Cập nhật thủ công tất cả ProtonVPN credentials"""
        print("🔄 Manual update all ProtonVPN credentials...")
        try:
            cmd = f"cd {self.base_dir} && ./manage_gost.sh update-protonvpn-auth"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                print("✅ Manual update completed")
                print(result.stdout)
            else:
                print(f"❌ Manual update failed: {result.stderr}")
        except Exception as e:
            print(f"❌ Error in manual update: {e}")
            
    def _should_cleanup_service(self, port, service_type):
        """Kiểm tra xem có nên cleanup service này không dựa trên thời gian tạo"""
        try:
            # Bảo vệ tuyệt đối: không bao giờ cleanup port 7890 (WARP service)
            if port == 7890:
                print(f"🛡️  Cannot cleanup protected service on port {port} (WARP service)")
                return False
            
            # Thời gian tối thiểu để service được coi là "cũ" (5 phút)
            MIN_AGE_MINUTES = 5
            min_age_seconds = MIN_AGE_MINUTES * 60
            
            # Lấy thời gian tạo của config file
            if service_type == "gost":
                config_file = os.path.join(self.config_dir, f"gost_{port}.config")
            else:
                return True  # Nếu không xác định được type, cho phép cleanup
            
            if not os.path.exists(config_file):
                return True  # Nếu config file không tồn tại, cho phép cleanup
            
            # Lấy thời gian tạo file
            file_creation_time = os.path.getctime(config_file)
            current_time = time.time()
            age_seconds = current_time - file_creation_time
            
            # Kiểm tra thời gian tạo trong config file (nếu có)
            try:
                with open(config_file, 'r') as f:
                    if service_type == "gost":
                        config = json.load(f)
                        created_at = config.get('created_at', '')
                        if created_at:
                            # Parse ISO format: 2025-10-23T15:00:00Z hoặc 2025-10-23T15:00:00+07:00
                            from datetime import datetime
                            try:
                                # Xử lý timezone: thay Z bằng +00:00, giữ nguyên timezone khác
                                created_at_str = created_at.replace('Z', '+00:00')
                                config_time = datetime.fromisoformat(created_at_str)
                                config_age_seconds = current_time - config_time.timestamp()
                                # Chỉ sử dụng config time nếu hợp lệ (không âm và không quá lớn)
                                if config_age_seconds >= 0 and config_age_seconds < 86400 * 365:  # Không quá 1 năm
                                    age_seconds = config_age_seconds
                            except:
                                pass
            except:
                pass
            
            # Nếu age_seconds âm (lỗi timezone hoặc thời gian trong tương lai), cho phép cleanup
            if age_seconds < 0:
                print(f"⚠️  {service_type} {port} has invalid timestamp (negative age), allowing cleanup")
                return True
            
            # Nếu service được tạo gần đây (dưới 5 phút), không cleanup
            if age_seconds < min_age_seconds:
                print(f"⏰ Protecting {service_type} {port} (created {int(age_seconds/60)} minutes ago, too recent)")
                return False
            
            print(f"⏰ {service_type} {port} is {int(age_seconds/60)} minutes old, safe to cleanup")
            return True
            
        except Exception as e:
            print(f"❌ Error checking service age for {service_type} {port}: {e}")
            return True  # Nếu có lỗi, cho phép cleanup để tránh tích lũy

    def manual_cleanup(self):
        """Dọn dẹp thủ công tất cả services không sử dụng"""
        print("🧹 Manual cleanup unused services...")
        self._cleanup_unused_services()

def signal_handler(signum, frame):
    """Xử lý signal để dừng gracefully"""
    print("\n🛑 Received signal, stopping auto updater...")
    sys.exit(0)

def main():
    """Main function"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        updater = AutoCredentialUpdater()
        
        if command == "start":
            # Setup signal handlers
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            updater.start_monitoring()
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                updater.stop_monitoring()
                
        elif command == "update":
            updater.manual_update_all()
            
        elif command == "test":
            # Test mode - check once and exit
            updater._check_and_update_credentials()
            
        elif command == "cleanup":
            # Manual cleanup mode
            updater.manual_cleanup()
            
        else:
            print("Usage: python auto_credential_updater.py {start|update|test|cleanup}")
    else:
        print("Usage: python auto_credential_updater.py {start|update|test|cleanup}")
        print("  start   - Start auto monitoring")
        print("  update  - Manual update all credentials")
        print("  test    - Test check once")
        print("  cleanup - Manual cleanup unused services")

if __name__ == "__main__":
    main()

