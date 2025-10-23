#!/usr/bin/env python3
"""
Test trực tiếp logic chrome_handler không cần WebUI
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Test data
test_data = {
    "proxy_check": "socks5://thenngua.ddns.net:7891:us:1",
    "data": {
        "count": 1,
        "profiles": [
            {
                "id": 652,
                "name": "P-20251020_104629",
                "proxy": "socks5://thenngua.ddns.net:7894"
            }
        ]
    }
}

def test_chrome_logic():
    """Test logic chrome_handler"""
    data = test_data
    proxy_check = data.get('proxy_check', '')
    profiles_data = data.get('data', {})
    profiles = profiles_data.get('profiles', [])
    
    print(f"Proxy check: {proxy_check}")
    print(f"Profiles: {profiles}")
    
    # Parse proxy_check: "socks5://HOST:PORT:SERVER_NAME:PORT"
    if not proxy_check or not proxy_check.startswith('socks5://'):
        print("❌ Invalid proxy_check format")
        return False
    
    # Extract components from proxy_check
    proxy_parts = proxy_check.replace('socks5://', '').rstrip(':').split(':')
    if len(proxy_parts) < 2:
        print("❌ Invalid proxy_check format")
        return False
    
    client_host = proxy_parts[0]  # Extract host from proxy_check
    check_port = proxy_parts[1]
    check_server = proxy_parts[2] if len(proxy_parts) >= 3 else ''
    check_proxy_port = proxy_parts[3] if len(proxy_parts) >= 4 else ''
    
    print(f"Parsed: {client_host}:{check_port}:{check_server}:{check_proxy_port}")
    
    # Parse proxy_check để map với 3 trường hợp apply
    apply_data = {}
    
    if check_proxy_port and check_proxy_port.isdigit() and check_server and '.' in check_server:
        # Trường hợp 2: Có proxy_host và proxy_port (server phải là domain thực tế)
        apply_data = {
            "proxy_host": check_server,
            "proxy_port": int(check_proxy_port)
        }
        print("✅ Case 2: Proxy host and port")
    elif len(check_server) == 2 and check_server.isalpha():
        # Trường hợp 1: Country code (2 ký tự)
        apply_data = {
            "country_code": check_server.upper()
        }
        print("✅ Case 1: Country code")
    else:
        # Trường hợp 3: Random server (empty hoặc không parse được)
        apply_data = {}
        print("✅ Case 3: Random server")
    
    print(f"Apply data: {apply_data}")
    
    # Determine VPN provider from server name
    if 'nordvpn' in check_server.lower():
        vpn_provider = 'nordvpn'
    elif 'protonvpn' in check_server.lower():
        vpn_provider = 'protonvpn'
    elif len(check_server) == 2:
        # For 2-character server names (country codes), random select VPN provider
        import random
        vpn_provider = random.choice(['nordvpn', 'protonvpn'])
    else:
        # Random VPN provider for empty/unknown cases
        import random
        vpn_provider = random.choice(['nordvpn', 'protonvpn'])
    
    print(f"VPN provider: {vpn_provider}")
    
    # Lấy danh sách proxy từ profiles
    existing_proxies = []
    for profile in profiles:
        if profile.get('proxy'):
            proxy_str = profile['proxy']
            # Parse socks5://host:port:server:proxy_port format
            if proxy_str.startswith('socks5://'):
                proxy_str = proxy_str[9:]
            
            parts = proxy_str.split(':')
            if len(parts) >= 2:
                existing_proxies.append({
                    'host': parts[0],
                    'port': parts[1],
                    'server': parts[2] if len(parts) >= 3 else '',
                    'proxy_port': parts[3] if len(parts) >= 4 else ''
                })
    
    print(f"Existing proxies: {existing_proxies}")
    
    # So sánh proxy_check với các proxy của profiles
    exact_match = None
    same_gost_port_different_server = None
    different_gost_port_same_server = None
    
    for existing_proxy in existing_proxies:
        # 1. Nếu proxy_check = proxy thì return lại proxy
        if (existing_proxy['port'] == check_port and 
            existing_proxy['server'] == check_server and 
            existing_proxy['proxy_port'] == check_proxy_port):
            exact_match = existing_proxy
            print("✅ Exact match found")
            break
        
        # 2. Khác port HA, proxy_host và proxy_port giống nhau thì return lại proxy
        if (existing_proxy['port'] != check_port and 
            existing_proxy['server'] == check_server and 
            existing_proxy['proxy_port'] == check_proxy_port and
            check_server != '' and check_proxy_port != '' and
            existing_proxy['server'] != '' and existing_proxy['proxy_port'] != '' and
            len(check_server) > 2 and check_proxy_port.isdigit() and
            '.' in check_server):
            different_gost_port_same_server = existing_proxy
            print("✅ Different port, same server found")
            break
        
        # 3. Trùng port gost, proxy_host và proxy_port khác nhau
        if (existing_proxy['port'] == check_port and 
            (existing_proxy['server'] != check_server or existing_proxy['proxy_port'] != check_proxy_port)):
            same_gost_port_different_server = existing_proxy
            print("✅ Same port, different server found")
            break
    
    if exact_match:
        print(f"✅ Return existing proxy: {exact_match}")
        return True
    elif different_gost_port_same_server:
        print(f"✅ Return existing proxy: {different_gost_port_same_server}")
        return True
    elif same_gost_port_different_server:
        print("✅ Need to create new HAProxy")
        return True
    else:
        print("✅ Need to create new HAProxy")
        return True

if __name__ == '__main__':
    print("="*80)
    print("Test Chrome Handler Logic - Direct")
    print("="*80)
    
    success = test_chrome_logic()
    
    if success:
        print("\n✅ Test completed successfully")
    else:
        print("\n❌ Test failed")
