#!/usr/bin/env python3
"""
ProtonVPN Service
Tương đương với C# ProtonVpnService, load/ghi từ file config_token.txt
"""

import os
import json
import requests
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import threading
import time

class ProtonVpnService:
    """Singleton service để quản lý ProtonVPN authentication và credentials"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ProtonVpnService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.list_servers: List[str] = []
        self.user_name: Optional[str] = None
        self.password: Optional[str] = None
        
        # Auto-load timer
        self._auto_load_timer: Optional[threading.Timer] = None
        self._auto_load_running = False
        self._auto_load_lock = threading.Lock()
        
        # Config file path
        self.config_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "proton_data",
            "config_token.txt"
        )
        
        # Load model từ file
        self.model = self._load_model()
        
        # Headers dictionaries (tương đương dic và dic2 trong C#)
        self.dic = {
            "x-pm-single-group": "vpn-paid",
            "x-pm-max-tier": "2",
            "x-pm-appversion": "browser-vpn@1.2.9",
        }
        
        self.dic2 = {
            "x-pm-single-group": "vpn-paid",
            "x-pm-apiversion": "3",
            "x-pm-appversion": "windows-vpn@4.3.1-dev+X64",
            "x-pm-locale": "en-US",
            "User-Agent": "ProtonVPN/4.3.1],[(Microsoft Windows NT 10.0.26100.0; X64)",
            "x-pm-timezone": "Asia/Bangkok",
        }
        
        # Set authorization headers nếu có token
        if self.model and self.model.get('token'):
            self.dic["Authorization"] = f"Bearer {self.model['token']}"
            self.dic["x-pm-uid"] = self.model['uid']
            self.dic2["Authorization"] = f"Bearer {self.model['token']}"
            self.dic2["x-pm-uid"] = self.model['uid']
        
        # Gọi load() khi khởi động
        self.load()
        
        # Bắt đầu auto-load mỗi 2 phút
        self.start_auto_load(interval_minutes=2)
    
    def _load_model(self) -> Optional[Dict]:
        """Load model từ file config_token.txt"""
        if not os.path.exists(self.config_file):
            return None
        
        try:
            model = {}
            with open(self.config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        if key == 'UID':
                            model['uid'] = value
                        elif key == 'AccessToken':
                            model['token'] = value
                        elif key == 'RefreshToken':
                            model['refresh_token'] = value
            
            return model if model else None
        except Exception as e:
            print(f"Error loading config: {e}")
            return None
    
    def _save_model(self) -> bool:
        """Lưu model vào file config_token.txt"""
        if not self.model:
            return False
        
        try:
            # Đảm bảo thư mục tồn tại
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            with open(self.config_file, 'w') as f:
                if 'uid' in self.model:
                    f.write(f"UID={self.model['uid']}\n")
                if 'token' in self.model:
                    f.write(f"AccessToken={self.model['token']}\n")
                if 'refresh_token' in self.model:
                    f.write(f"RefreshToken={self.model['refresh_token']}\n")
            
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def load(self) -> None:
        """Load VPN credentials từ API"""
        max_retries = 2
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                url = "https://account.proton.me/api/vpn/v1/browser/token?Duration=120000"
                response = requests.get(url, headers=self.dic, timeout=30)
                
                json_data = response.text
                
                if "Invalid access token" in json_data:
                    if retry_count < max_retries - 1:
                        if self.refresh():
                            retry_count += 1
                            continue
                        else:
                            return
                    else:
                        return
                
                # Parse JSON response
                try:
                    data = json.loads(json_data)
                    self.user_name = data.get("Username")
                    self.password = data.get("Password")
                
                    
                    return
                except json.JSONDecodeError:
                    print(f"Error parsing JSON response: {json_data}")
                    return
                    
            except Exception as e:
                print(f"Error in load: {e}")
                return
    
    
    def start_auto_load(self, interval_minutes: int = 5) -> None:
        """Bắt đầu auto-load credentials mỗi N phút"""
        with self._auto_load_lock:
            if self._auto_load_running:
                return
            
            self._auto_load_running = True
        
        def _auto_load_loop():
            while self._auto_load_running:
                try:
                    time.sleep(interval_minutes * 60)  # Chuyển phút thành giây
                    if self._auto_load_running:
                        self.load()
                except Exception as e:
                    print(f"Error in auto-load loop: {e}")
        
        # Chạy trong background thread
        auto_load_thread = threading.Thread(target=_auto_load_loop, daemon=True)
        auto_load_thread.start()
    
    def stop_auto_load(self) -> None:
        """Dừng auto-load"""
        with self._auto_load_lock:
            self._auto_load_running = False
    
    def refresh(self) -> bool:
        """Refresh access token"""
        if not self.model:
            return False
        
        try:
            refresh_dic = {
                "x-pm-uid": self.model.get('uid', ''),
                "x-pm-appversion": "browser-vpn@1.2.9",
            }
            
            url = "https://account.proton.me/api/auth/refresh"
            data_post = {
                "UID": self.model.get('uid', ''),
                "ResponseType": "token",
                "GrantType": "refresh_token",
                "RefreshToken": self.model.get('refresh_token', ''),
                "RedirectURI": "https://protonvpn.com"
            }
            
            response = requests.post(
                url,
                json=data_post,
                headers=refresh_dic,
                timeout=30
            )
            
            json_data = response.text
            
            if "AccessToken" in json_data:
                try:
                    result = json.loads(json_data)
                    access_token = result.get("AccessToken")
                    uid = result.get("Uid")
                    refresh_token = result.get("RefreshToken")
                    expires_in = result.get("ExpiresIn")
                    
                    if access_token and uid:
                        # Update model
                        self.model['token'] = access_token
                        self.model['uid'] = uid
                        if refresh_token:
                            self.model['refresh_token'] = refresh_token
                        if expires_in:
                            try:
                                expires_seconds = int(expires_in)
                                self.model['expired_time'] = (datetime.now() + timedelta(seconds=expires_seconds)).isoformat()
                            except (ValueError, TypeError):
                                pass
                        
                        # Update headers
                        self.dic["Authorization"] = f"Bearer {access_token}"
                        self.dic["x-pm-uid"] = uid
                        self.dic2["Authorization"] = f"Bearer {access_token}"
                        self.dic2["x-pm-uid"] = uid
                        
                        # Save to file
                        self._save_model()
                        
                        return True
                except json.JSONDecodeError:
                    print(f"Error parsing refresh response: {json_data}")
                    return False
            
            return False
            
        except Exception as e:
            print(f"Error in refresh: {e}")
            return False
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance"""
        return cls()


# Singleton instance (tương đương với Instance property trong C#)
Instance = ProtonVpnService()


if __name__ == "__main__":
    # Test the service
    service = Instance
    
    print("Service initialized. Auto-load started.")
    print(f"Username: {service.user_name}")
    print(f"Password: {service.password}")
    
    # Giữ chương trình chạy để test auto-load
    try:
        print("\nAuto-load is running every 5 minutes. Press Ctrl+C to stop.")
        while True:
            time.sleep(60)
            if service.user_name and service.password:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Credentials available: {service.user_name}")
    except KeyboardInterrupt:
        print("\nStopping auto-load...")
        service.stop_auto_load()
        print("Stopped.")

