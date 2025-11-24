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
from typing import Dict, List, Optional, Set, Tuple
import threading
import signal
import sys

# Import protonvpn_service để lấy credentials
try:
    from protonvpn_service import Instance as ProtonVpnServiceInstance
except ImportError:
    ProtonVpnServiceInstance = None

# Constants
PROTECTED_PORT_WARP = 7890
GOST_PORT_MIN = 7891
GOST_PORT_MAX = 7999
MIN_SERVICE_AGE_MINUTES = 5
MIN_SERVICE_AGE_SECONDS = MIN_SERVICE_AGE_MINUTES * 60
ERROR_CHECK_INTERVAL_SECONDS = 30
CLEANUP_INTERVAL_SECONDS = 300  # 5 minutes
RECENT_ERROR_THRESHOLD_SECONDS = 300  # 5 minutes
API_TIMEOUT_SECONDS = 10
PROFILES_API_URL = "https://g.proxyit.online/api/profiles/count-open"

class AutoCredentialUpdater:
    def __init__(self, base_dir: Optional[str] = None):
        """Initialize AutoCredentialUpdater with base directory"""
        self.base_dir = base_dir or self._detect_base_dir()
        self.log_dir = os.path.join(self.base_dir, "logs")
        self.config_dir = os.path.join(self.base_dir, "config")
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
    
    @staticmethod
    def _detect_base_dir() -> str:
        """Auto-detect base directory"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Check if script is in mac_proxy directory
        if os.path.basename(script_dir) == 'mac_proxy' or os.path.exists(os.path.join(script_dir, 'manage_gost.sh')):
            return script_dir
        
        # Try to find mac_proxy directory by traversing up
        current = script_dir
        while current != os.path.dirname(current):
            if os.path.exists(os.path.join(current, 'manage_gost.sh')):
                return current
            current = os.path.dirname(current)
        
        # Fallback
        return script_dir if os.path.exists(os.path.join(script_dir, 'manage_gost.sh')) else os.path.expanduser("~/mac_proxy")
        
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
                self._ensure_gost_7890_config()
                self._check_and_update_credentials()
                
                # Check for unused services every CLEANUP_INTERVAL_SECONDS
                current_time = time.time()
                if current_time - last_cleanup >= CLEANUP_INTERVAL_SECONDS:
                    self._cleanup_unused_services()
                    last_cleanup = current_time
                
                time.sleep(ERROR_CHECK_INTERVAL_SECONDS)
            except Exception as e:
                print(f"❌ Error in monitor loop: {e}")
                time.sleep(60)  # Wait longer on error
                
    def _ensure_gost_7890_config(self):
        """Đảm bảo config cho port WARP luôn tồn tại (tự động tạo lại nếu bị mất)"""
        try:
            gost_config = os.path.join(self.config_dir, f"gost_{PROTECTED_PORT_WARP}.config")
            if not os.path.exists(gost_config):
                print(f"🛡️  Port {PROTECTED_PORT_WARP} config missing, recreating...")
                config_data = {
                    "port": str(PROTECTED_PORT_WARP),
                    "provider": "warp",
                    "country": "cloudflare",
                    "proxy_url": "socks5://127.0.0.1:8111",
                    "proxy_host": "127.0.0.1",
                    "proxy_port": "8111",
                    "created_at": datetime.now().isoformat() + 'Z'
                }
                with open(gost_config, 'w') as f:
                    json.dump(config_data, f, indent=2)
                print(f"✅ Port {PROTECTED_PORT_WARP} config recreated")
        except Exception as e:
            print(f"⚠️  Error ensuring gost {PROTECTED_PORT_WARP} config: {e}")
    
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
        try:
            for filename in os.listdir(self.config_dir):
                if filename.startswith("gost_") and filename.endswith(".config"):
                    config_path = os.path.join(self.config_dir, filename)
                    try:
                        with open(config_path, 'r') as f:
                            config = json.load(f)
                            if config.get('provider') == 'protonvpn':
                                configs.append(config_path)
                    except (json.JSONDecodeError, IOError):
                        continue
        except OSError:
            pass
        return configs
        
    def _has_authentication_errors(self, config_file: str) -> bool:
        """Kiểm tra xem có lỗi authentication trong log không"""
        port = self._extract_port_from_config_file(config_file)
        if not port:
            return False
            
        log_file = os.path.join(self.log_dir, f"gost_{port}.log")
        if not os.path.exists(log_file):
            return False
            
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                recent_lines = lines[-100:] if len(lines) > 100 else lines
                
                auth_error_count = 0
                timeout_error_count = 0
                
                for line in recent_lines:
                    if '407 Proxy Authentication Required' in line:
                        if self._is_recent_error(line):
                            auth_error_count += 1
                    elif 'i/o timeout' in line:
                        if self._is_recent_error(line):
                            timeout_error_count += 1
                
                if auth_error_count > 0:
                    print(f"🔍 Found {auth_error_count} authentication errors (407) for port {port}")
                    return True
                
                if timeout_error_count >= 5:
                    print(f"⚠️  Found {timeout_error_count} timeout errors for port {port} (server may be down)")
                    
        except Exception as e:
            print(f"❌ Error reading log file {log_file}: {e}")
            
        return False
    
    def _is_recent_error(self, log_line: str) -> bool:
        """Kiểm tra lỗi gần đây cho gost log format: 2025/11/17 18:25:55"""
        try:
            if log_line.startswith('20'):
                parts = log_line.split(' ', 1)
                if len(parts) >= 2:
                    date_str = parts[0]  # 2025/11/17
                    time_str = parts[1].split()[0] if parts[1] else ''  # 18:25:55 (first part)
                    if time_str:
                        datetime_str = f"{date_str} {time_str}"
                        log_time = datetime.strptime(datetime_str, '%Y/%m/%d %H:%M:%S')
                        time_diff = (datetime.now() - log_time).total_seconds()
                        return time_diff < RECENT_ERROR_THRESHOLD_SECONDS
        except (ValueError, IndexError):
            pass
        return True  # Nếu không parse được timestamp, coi như recent để trigger update
        
    def _extract_port_from_config_file(self, config_file: str) -> Optional[str]:
        """Trích xuất port từ tên config file"""
        filename = os.path.basename(config_file)
        if filename.startswith("gost_") and filename.endswith(".config"):
            return filename[5:-7]  # Remove "gost_" and ".config"
        return None
        
    def _update_credentials_for_config(self, config_file: str) -> bool:
        """Cập nhật credentials cho một config file"""
        try:
            auth_token = self._get_fresh_auth_token()
            if not auth_token:
                print("❌ Failed to get fresh auth token")
                return False
                
            with open(config_file, 'r') as f:
                config = json.load(f)
                
            current_proxy_url = config.get('proxy_url', '')
            if not current_proxy_url:
                print(f"❌ No proxy_url found in config {config_file}")
                return False
            
            # Parse và cập nhật proxy URL
            proxy_host, proxy_port = self._parse_proxy_url(current_proxy_url)
            if not proxy_host or not proxy_port:
                print(f"❌ Failed to parse proxy_url from config {config_file}")
                return False
            
            # Tạo proxy_url mới với auth token mới
            config['proxy_url'] = f"https://{auth_token}@{proxy_host}:{proxy_port}"
            config['updated_at'] = datetime.now().isoformat()
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
                
            port = self._extract_port_from_config_file(config_file)
            if port:
                self._restart_gost_service(port)
                print(f"✅ Updated credentials for port {port}")
                return True
                    
        except Exception as e:
            print(f"❌ Error updating credentials for {config_file}: {e}")
            
        return False
    
    @staticmethod
    def _parse_proxy_url(proxy_url: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse proxy URL để lấy host và port"""
        if '@' not in proxy_url:
            return None, None
        
        try:
            parts = proxy_url.split('@', 1)
            if len(parts) == 2:
                host_port = parts[1]
                if ':' in host_port:
                    proxy_host, proxy_port = host_port.split(':', 1)
                    return proxy_host, proxy_port
        except (ValueError, IndexError):
            pass
        return None, None
        
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
        """Dọn dẹp các service không sử dụng dựa trên profile count API"""
        try:
            used_ports = self._fetch_used_ports_from_api()
            print(f"🔍 Total unique used ports: {len(used_ports)} - {sorted(used_ports)}")
            self._cleanup_unused_gost_services(used_ports)
        except Exception as e:
            print(f"❌ Error in cleanup unused services: {e}")
    
    def _fetch_used_ports_from_api(self) -> Set[int]:
        """Lấy danh sách ports đang được sử dụng từ API"""
        used_ports: Set[int] = set()
        
        try:
            response = requests.get(PROFILES_API_URL, timeout=API_TIMEOUT_SECONDS)
            if response.status_code == 200:
                data = response.json()
                print(f"🔍 API response: {data}")
                if isinstance(data, list):
                    ports = self._extract_ports_from_profiles(data)
                    used_ports.update(ports)
                    print(f"🔍 API: Found {len(ports)} used ports: {sorted(ports)}")
                else:
                    print(f"❌ API unexpected format: {type(data)}, data: {data}")
            else:
                print(f"❌ API failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Error calling API: {e}")
        
        return used_ports
            
    def _extract_ports_from_profiles(self, profiles: List[Dict]) -> Set[int]:
        """Trích xuất ports từ danh sách profiles"""
        ports: Set[int] = set()
        for profile in profiles:
            proxy = profile.get('proxy', '')
            if not proxy or ':' not in proxy:
                continue
            
            port = self._parse_port_from_proxy(proxy)
            if port:
                ports.add(port)
                profile_id = profile.get('id', 'unknown')
                profile_name = profile.get('name', 'unknown')
                print(f"✅ Profile {profile_id} ({profile_name}): extracted port {port} from proxy '{proxy}'")
        return ports
    
    @staticmethod
    def _parse_port_from_proxy(proxy: str) -> Optional[int]:
        """Parse port từ proxy string: socks5://host:PORT:server:proxy_port"""
        try:
            # Remove socks5:// prefix
            proxy_str = proxy[9:] if proxy.startswith('socks5://') else proxy
            parts = proxy_str.split(':')
            
            if len(parts) >= 2:
                port_str = parts[1].strip()
                if port_str.isdigit():
                    port = int(port_str)
                    if GOST_PORT_MIN <= port <= GOST_PORT_MAX:
                        return port
        except (ValueError, IndexError):
            pass
        return None
            
    def _cleanup_unused_gost_services(self, used_ports: Set[int]):
        """Dọn dẹp Gost services không sử dụng"""
        try:
            print(f"🔍 Checking Gost services against used_ports: {sorted(used_ports)}")
            for filename in os.listdir(self.config_dir):
                if not (filename.startswith("gost_") and filename.endswith(".config")):
                    continue
                
                port_str = filename[5:-7]  # Remove "gost_" and ".config"
                try:
                    gost_port = int(port_str)
                    if self._should_protect_service(gost_port, used_ports):
                        continue
                    
                    if self._should_cleanup_service(gost_port, "gost"):
                        print(f"🧹 Cleaning up unused Gost service on port {gost_port}")
                        self._stop_and_remove_gost_service(gost_port)
                except ValueError:
                    continue
        except Exception as e:
            print(f"❌ Error cleaning up Gost services: {e}")
    
    def _should_protect_service(self, port: int, used_ports: Set[int]) -> bool:
        """Kiểm tra xem service có nên được bảo vệ không"""
        if port == PROTECTED_PORT_WARP:
            print(f"🛡️  Protecting Gost {port} (Cloudflare WARP service)")
            return True
        
        if port in used_ports:
            print(f"🛡️  Protecting Gost {port} (directly used in used_ports)")
            return True
        
        if self._is_gost_process_running(port):
            print(f"🛡️  Protecting Gost {port} (process is running, may be in use)")
            return True
        
        return False
    
    def _is_gost_process_running(self, port: int) -> bool:
        """Kiểm tra xem Gost process có đang chạy không"""
        try:
            pid_file = os.path.join(self.log_dir, f"gost_{port}.pid")
            if not os.path.exists(pid_file):
                return False
            
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)  # Signal 0 chỉ kiểm tra process có tồn tại không
            return True
        except (OSError, ValueError, ProcessLookupError):
            return False
            
    def _stop_and_remove_gost_service(self, port: int):
        """Dừng và xóa Gost service"""
        if port == PROTECTED_PORT_WARP:
            print(f"🛡️  Cannot remove protected Gost service on port {port} (WARP service)")
            return
        
        try:
            self._stop_gost_process(port)
            self._kill_process_on_port(port)
            self._remove_service_files(port)
            print(f"✅ Cleaned up Gost service on port {port}")
        except Exception as e:
            print(f"❌ Error stopping Gost service on port {port}: {e}")
    
    def _stop_gost_process(self, port: int):
        """Dừng Gost process"""
        pid_file = os.path.join(self.log_dir, f"gost_{port}.pid")
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                os.kill(pid, 15)  # SIGTERM
                print(f"✅ Stopped Gost process {pid} on port {port}")
            except (OSError, ValueError, ProcessLookupError):
                pass
    
    @staticmethod
    def _kill_process_on_port(port: int):
        """Kill bất kỳ process nào đang chạy trên port"""
        try:
            cmd = f"lsof -ti:{port} | xargs kill -9 2>/dev/null || true"
            subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
        except Exception:
            pass
    
    def _remove_service_files(self, port: int):
        """Xóa các file liên quan đến service"""
        # Remove config file
        config_file = os.path.join(self.config_dir, f"gost_{port}.config")
        if os.path.exists(config_file):
            os.remove(config_file)
            print(f"✅ Removed Gost config for port {port}")
        
        # Remove PID file
        pid_file = os.path.join(self.log_dir, f"gost_{port}.pid")
        if os.path.exists(pid_file):
            os.remove(pid_file)
        
        # Remove log file
        log_file = os.path.join(self.log_dir, f"gost_{port}.log")
        if os.path.exists(log_file):
            os.remove(log_file)
            
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
            
    def _should_cleanup_service(self, port: int, service_type: str) -> bool:
        """Kiểm tra xem có nên cleanup service này không dựa trên thời gian tạo"""
        if port == PROTECTED_PORT_WARP:
            print(f"🛡️  Cannot cleanup protected service on port {port} (WARP service)")
            return False
        
        if service_type != "gost":
            return True  # Nếu không xác định được type, cho phép cleanup
        
        config_file = os.path.join(self.config_dir, f"gost_{port}.config")
        if not os.path.exists(config_file):
            return True  # Nếu config file không tồn tại, cho phép cleanup
        
        try:
            age_seconds = self._get_service_age(config_file)
            
            if age_seconds < 0:
                print(f"⚠️  {service_type} {port} has invalid timestamp (negative age), allowing cleanup")
                return True
            
            if age_seconds < MIN_SERVICE_AGE_SECONDS:
                print(f"⏰ Protecting {service_type} {port} (created {int(age_seconds/60)} minutes ago, too recent)")
                return False
            
            print(f"⏰ {service_type} {port} is {int(age_seconds/60)} minutes old, safe to cleanup")
            return True
        except Exception as e:
            print(f"❌ Error checking service age for {service_type} {port}: {e}")
            return True  # Nếu có lỗi, cho phép cleanup để tránh tích lũy
    
    def _get_service_age(self, config_file: str) -> float:
        """Lấy tuổi của service (tính bằng giây)"""
        # Lấy thời gian tạo file
        file_creation_time = os.path.getctime(config_file)
        current_time = time.time()
        age_seconds = current_time - file_creation_time
        
        # Kiểm tra thời gian tạo trong config file (nếu có)
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                created_at = config.get('created_at', '')
                if created_at:
                    created_at_str = created_at.replace('Z', '+00:00')
                    config_time = datetime.fromisoformat(created_at_str)
                    config_age_seconds = current_time - config_time.timestamp()
                    # Chỉ sử dụng config time nếu hợp lệ (không âm và không quá lớn)
                    if 0 <= config_age_seconds < 86400 * 365:  # Không quá 1 năm
                        age_seconds = config_age_seconds
        except (json.JSONDecodeError, ValueError, IOError):
            pass
        
        return age_seconds

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
            
        elif command == "test-extract":
            # Test extract ports from profiles
            test_profiles = [{"id":530,"name":"6","proxy":"socks5://proxyy.zapto.org:7891:lk-02.protonvpn.net:4445"}]
            print(f"Testing with profiles: {test_profiles}")
            ports = updater._extract_ports_from_profiles(test_profiles)
            print(f"Extracted ports: {ports}")
            
        elif command == "test-cleanup":
            # Test cleanup với dữ liệu thực tế từ API
            print("Testing cleanup with real API data...")
            updater._cleanup_unused_services()
            
        elif command == "test-protection":
            # Test bảo vệ profiles đang mở với dữ liệu thực tế từ API
            print("🧪 Testing protection logic for open profiles...")
            print("=" * 60)
            
            # Lấy dữ liệu thực tế từ API
            print("\n1️⃣  Fetching real data from API...")
            used_ports = updater._fetch_used_ports_from_api()
            print(f"   ✅ Found {len(used_ports)} used ports: {sorted(used_ports)}")
            
            # Kiểm tra các config files hiện có
            print("\n2️⃣  Checking existing config files...")
            existing_configs = []
            for filename in os.listdir(updater.config_dir):
                if filename.startswith("gost_") and filename.endswith(".config"):
                    port_str = filename[5:-7]
                    try:
                        port = int(port_str)
                        existing_configs.append(port)
                    except ValueError:
                        continue
            print(f"   📁 Found {len(existing_configs)} config files: {sorted(existing_configs)}")
            
            # Test protection logic cho từng port
            print("\n3️⃣  Testing protection logic:")
            print("   " + "-" * 56)
            will_be_deleted = []
            will_be_protected = []
            
            for port in sorted(existing_configs):
                is_protected = updater._should_protect_service(port, used_ports)
                in_used_ports = port in used_ports
                
                if is_protected:
                    will_be_protected.append(port)
                    reason = []
                    if port == PROTECTED_PORT_WARP:
                        reason.append("WARP service")
                    if in_used_ports:
                        reason.append("in used_ports")
                    if updater._is_gost_process_running(port):
                        reason.append("process running")
                    print(f"   ✅ Port {port:4d}: PROTECTED ({', '.join(reason)})")
                else:
                    should_cleanup = updater._should_cleanup_service(port, "gost")
                    if should_cleanup:
                        will_be_deleted.append(port)
                        print(f"   ⚠️  Port {port:4d}: WILL BE DELETED (not protected, old enough)")
                    else:
                        print(f"   ⏰ Port {port:4d}: Protected by age check (too recent)")
            
            # Summary
            print("\n4️⃣  Summary:")
            print("   " + "-" * 56)
            print(f"   📊 Total used ports from API: {len(used_ports)}")
            print(f"   📁 Total config files: {len(existing_configs)}")
            print(f"   🛡️  Protected ports: {len(will_be_protected)}")
            print(f"   🧹 Ports that will be deleted: {len(will_be_deleted)}")
            
            if will_be_deleted:
                print(f"\n   ⚠️  WARNING: {len(will_be_deleted)} port(s) will be deleted:")
                for port in will_be_deleted:
                    if port in used_ports:
                        print(f"      ❌ Port {port} is in used_ports but will be deleted! BUG!")
                    else:
                        print(f"      ✅ Port {port} is not in used_ports, safe to delete")
            else:
                print(f"\n   ✅ SUCCESS: No ports with open profiles will be deleted!")
            
            print("=" * 60)
            
        else:
            print("Usage: python auto_credential_updater.py {start|update|test|cleanup|test-extract|test-cleanup}")
    else:
        print("Usage: python auto_credential_updater.py {start|update|test|cleanup}")
        print("  start   - Start auto monitoring")
        print("  update  - Manual update all credentials")
        print("  test    - Test check once")
        print("  cleanup - Manual cleanup unused services")

if __name__ == "__main__":
    main()

