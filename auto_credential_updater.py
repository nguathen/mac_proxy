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

class AutoCredentialUpdater:
    def __init__(self, base_dir: str = "/Volumes/Ssd/Projects/mac_proxy"):
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
        while self.running:
            try:
                self._check_and_update_credentials()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                print(f"❌ Error in monitor loop: {e}")
                time.sleep(60)  # Wait longer on error
                
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
            
        # Đọc 50 dòng cuối của log file
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                recent_lines = lines[-50:] if len(lines) > 50 else lines
                
                # Kiểm tra lỗi 407 trong 5 phút gần nhất
                for line in recent_lines:
                    if '"407 Proxy Authentication Required"' in line:
                        # Kiểm tra timestamp (trong 5 phút gần nhất)
                        if self._is_recent_error(line):
                            return True
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
                # Parse URL: https://token@host:port
                if '@' in current_proxy_url:
                    parts = current_proxy_url.split('@', 1)
                    if len(parts) == 2:
                        host_port = parts[1]
                        if ':' in host_port:
                            proxy_host, proxy_port = host_port.split(':', 1)
                            
                            # Tạo proxy_url mới với auth token mới
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
        """Lấy auth token mới từ API"""
        try:
            response = requests.get("http://localhost:5267/mmo/getpassproxy", timeout=10)
            if response.status_code == 200:
                return response.text.strip()
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

def signal_handler(signum, frame):
    """Xử lý signal để dừng gracefully"""
    print("\n🛑 Received signal, stopping auto updater...")
    if 'updater' in globals():
        updater.stop_monitoring()
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
            
        else:
            print("Usage: python auto_credential_updater.py {start|update|test}")
    else:
        print("Usage: python auto_credential_updater.py {start|update|test}")
        print("  start  - Start auto monitoring")
        print("  update - Manual update all credentials")
        print("  test   - Test check once")

if __name__ == "__main__":
    main()
