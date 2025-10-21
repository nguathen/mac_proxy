#!/usr/bin/env python3
"""
Proxy API Module
Lấy thông tin proxy cho NordVPN và ProtonVPN để sử dụng với gost
"""

import requests
import json
import re
from typing import Optional, Dict, Any
import os

class ProxyAPI:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
    
    def get_nordvpn_proxy(self, country: str = None) -> Optional[str]:
        """
        Lấy thông tin proxy NordVPN
        Format: https://user:pass@country:port
        """
        try:
            # Sử dụng thông tin cố định như trong demo
            # Trong thực tế, có thể lấy từ API hoặc config
            if country:
                proxy_url = f"https://USMbUonbFpF9xEx8xR3MHSau:buKKKPURZNMTW7A6rwm3qtBn@{country}:89"
            else:
                proxy_url = "https://USMbUonbFpF9xEx8xR3MHSau:buKKKPURZNMTW7A6rwm3qtBn@hostname:89"
            return proxy_url
        except Exception as e:
            print(f"Error getting NordVPN proxy: {e}")
            return None
    
    def get_protonvpn_proxy(self, country: str = None) -> Optional[str]:
        """
        Lấy thông tin proxy ProtonVPN
        Gọi API http://localhost:5267/mmo/getpassproxy để lấy user:pass
        Tính port = server_label + 4443
        """
        try:
            # Gọi API để lấy user:pass
            response = requests.get("http://localhost:5267/mmo/getpassproxy", timeout=10)
            if response.status_code == 200:
                user_pass = response.text.strip()
                
                # Tính port từ server label
                server_label = self._extract_server_label(country)
                port = server_label + 4443
                
                # Tạo proxy URL
                proxy_url = f"https://{user_pass}@{country}:{port}"
                return proxy_url
            else:
                print(f"Failed to get ProtonVPN credentials: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error getting ProtonVPN proxy: {e}")
            return None
    
    def _extract_server_label(self, country: str) -> int:
        """
        Trích xuất server label từ country string bằng cách tìm trong cache
        VD: 'node-uk-29.protonvpn.net' -> 6 (từ cache)
        """
        if not country:
            return 8  # Default
        
        try:
            # Tìm server trong cache để lấy label chính xác
            cache_file = os.path.join(self.base_dir, 'protonvpn_servers_cache.json')
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    # Cache file là array, không phải object
                    if isinstance(data, list):
                        # Ưu tiên lấy label "6" nếu có, nếu không thì lấy label đầu tiên
                        # Tìm tất cả server có domain đúng và label "6"
                        for server in data:
                            if server.get('domain') == country and 'servers' in server:
                                for sub_server in server['servers']:
                                    if sub_server.get('domain') == country and sub_server.get('label') == '6':
                                        return int(sub_server.get('label', 8))
                        
                        # Fallback: lấy label đầu tiên
                        for server in data:
                            if server.get('domain') == country and 'servers' in server:
                                for sub_server in server['servers']:
                                    if sub_server.get('domain') == country:
                                        return int(sub_server.get('label', 8))
        except Exception as e:
            print(f"Error reading cache: {e}")
        
        # Fallback: tìm số trong string
        numbers = re.findall(r'\d+', country)
        if numbers:
            return int(numbers[0])
        
        # Fallback: tính từ hash của country
        return hash(country) % 100 + 1
    
    def get_proxy_for_provider(self, provider: str, country: str = None) -> Optional[str]:
        """
        Lấy proxy URL cho provider cụ thể
        """
        if provider.lower() == "nordvpn":
            return self.get_nordvpn_proxy(country)
        elif provider.lower() == "protonvpn":
            return self.get_protonvpn_proxy(country)
        else:
            print(f"Unknown provider: {provider}")
            return None
    
    def test_proxy_connection(self, proxy_url: str, timeout: int = 10) -> bool:
        """
        Test kết nối proxy
        """
        try:
            # Test với curl qua proxy
            import subprocess
            result = subprocess.run([
                'curl', '-s', '--max-time', str(timeout),
                '--proxy', proxy_url,
                'https://api.ipify.org'
            ], capture_output=True, text=True, timeout=timeout)
            
            return result.returncode == 0 and result.stdout.strip()
        except Exception as e:
            print(f"Error testing proxy: {e}")
            return False

# Global instance
proxy_api = ProxyAPI()
