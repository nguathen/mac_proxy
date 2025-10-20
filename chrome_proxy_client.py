#!/usr/bin/env python3
"""
Chrome Proxy Client
Client library để tương tác với Chrome Proxy Check API
"""

import requests
from typing import List, Dict, Optional

class ChromeProxyClient:
    def __init__(self, api_url: str = "http://localhost:5000"):
        self.api_url = api_url.rstrip('/')
        self.endpoint = f"{self.api_url}/api/chrome/proxy-check"
    
    def check_proxy(self, proxy_check: str, opened_profiles: List[Dict]) -> Dict:
        """
        Kiểm tra và tạo proxy cho Chrome profile
        
        Args:
            proxy_check: Proxy string format "socks5://server:PORT:SERVER_NAME:"
            opened_profiles: List of opened profiles with proxy info
                [{"id": 1, "name": "Profile 1", "proxy": "127.0.0.1:7891:vn42.nordvpn.com"}]
        
        Returns:
            Dict with keys: success, message, proxy_check, action, etc.
        """
        payload = {
            "proxy_check": proxy_check,
            "data": {
                "count": len(opened_profiles),
                "profiles": opened_profiles
            }
        }
        
        try:
            response = requests.post(self.endpoint, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_proxy_for_new_profile(self, server_name: str, opened_profiles: List[Dict]) -> Optional[str]:
        """
        Lấy proxy string cho Chrome profile mới
        
        Args:
            server_name: VPN server name (vn42.nordvpn.com, us-ca-10.protonvpn.com)
            opened_profiles: List of opened profiles
        
        Returns:
            Proxy string format "socks5://127.0.0.1:PORT:SERVER_NAME:" or None if error
        """
        # Find available port
        used_ports = set()
        for profile in opened_profiles:
            if profile.get('proxy'):
                parts = profile['proxy'].split(':')
                if len(parts) >= 2:
                    used_ports.add(int(parts[1]))
        
        # Start from 7891
        port = 7891
        while port in used_ports:
            port += 1
            if port > 7999:
                return None
        
        # Build proxy_check string
        proxy_check = f"socks5://server:{port}:{server_name}:"
        
        # Call API
        result = self.check_proxy(proxy_check, opened_profiles)
        
        if result.get('success'):
            return result.get('proxy_check')
        else:
            return None


# Example usage
if __name__ == '__main__':
    import sys
    
    client = ChromeProxyClient()
    
    # Example: Get proxy for new Chrome profile
    print("Chrome Proxy Client Example")
    print("="*80)
    
    # Simulate opened profiles
    opened_profiles = [
        {"id": 1, "name": "Profile 1", "proxy": "127.0.0.1:7891:vn42.nordvpn.com"},
        {"id": 2, "name": "Profile 2", "proxy": "127.0.0.1:7892:us10.nordvpn.com"},
    ]
    
    print("\nOpened profiles:")
    for p in opened_profiles:
        print(f"  - {p['name']}: {p['proxy']}")
    
    # Request new server
    if len(sys.argv) > 1:
        server_name = sys.argv[1]
    else:
        server_name = "de42.nordvpn.com"
    
    print(f"\nRequesting proxy for new profile with server: {server_name}")
    
    proxy = client.get_proxy_for_new_profile(server_name, opened_profiles)
    
    if proxy:
        print(f"\n✅ Success!")
        print(f"Proxy for new Chrome profile: {proxy}")
        
        # Extract port for display
        parts = proxy.replace('socks5://', '').split(':')
        if len(parts) >= 2:
            port = parts[1]
            print(f"\nConfigure Chrome profile with:")
            print(f"  Proxy: socks5://127.0.0.1:{port}")
    else:
        print(f"\n❌ Failed to get proxy")
    
    print("\n" + "="*80)
    print("Usage:")
    print(f"  python3 {sys.argv[0]} [server_name]")
    print("\nExamples:")
    print(f"  python3 {sys.argv[0]} vn42.nordvpn.com")
    print(f"  python3 {sys.argv[0]} us-ca-10.protonvpn.com")

