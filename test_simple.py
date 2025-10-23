#!/usr/bin/env python3
"""
Test đơn giản để kiểm tra logic chrome_handler
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

def test_parse_proxy_check():
    """Test parse proxy_check"""
    proxy_check = test_data.get('proxy_check', '')
    print(f"Proxy check: {proxy_check}")
    
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
    
    print(f"Client host: {client_host}")
    print(f"Check port: {check_port}")
    print(f"Check server: {check_server}")
    print(f"Check proxy port: {check_proxy_port}")
    
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
    
    return True

def test_parse_profiles():
    """Test parse profiles"""
    profiles_data = test_data.get('data', {})
    profiles = profiles_data.get('profiles', [])
    
    print(f"Profiles count: {len(profiles)}")
    
    # Lấy danh sách proxy từ profiles
    existing_proxies = []
    for profile in profiles:
        if profile.get('proxy'):
            proxy_str = profile['proxy']
            print(f"Profile proxy: {proxy_str}")
            
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
                print(f"Parsed proxy: {existing_proxies[-1]}")
    
    print(f"Existing proxies: {existing_proxies}")
    return existing_proxies

if __name__ == '__main__':
    print("="*80)
    print("Test Chrome Handler Logic")
    print("="*80)
    
    print("\n1. Test parse proxy_check:")
    test_parse_proxy_check()
    
    print("\n2. Test parse profiles:")
    existing_proxies = test_parse_profiles()
    
    print("\n3. Test logic comparison:")
    proxy_check = test_data.get('proxy_check', '')
    proxy_parts = proxy_check.replace('socks5://', '').rstrip(':').split(':')
    client_host = proxy_parts[0]
    check_port = proxy_parts[1]
    check_server = proxy_parts[2] if len(proxy_parts) >= 3 else ''
    check_proxy_port = proxy_parts[3] if len(proxy_parts) >= 4 else ''
    
    print(f"Check: {client_host}:{check_port}:{check_server}:{check_proxy_port}")
    
    for existing_proxy in existing_proxies:
        print(f"Existing: {existing_proxy['host']}:{existing_proxy['port']}:{existing_proxy['server']}:{existing_proxy['proxy_port']}")
        
        # 1. Nếu proxy_check = proxy thì return lại proxy
        if (existing_proxy['port'] == check_port and 
            existing_proxy['server'] == check_server and 
            existing_proxy['proxy_port'] == check_proxy_port):
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
            print("✅ Different port, same server found")
            break
        
        # 3. Trùng port gost, proxy_host và proxy_port khác nhau
        if (existing_proxy['port'] == check_port and 
            (existing_proxy['server'] != check_server or existing_proxy['proxy_port'] != check_proxy_port)):
            print("✅ Same port, different server found")
            break
    else:
        print("✅ No match found, need to create new")
    
    print("\n✅ Test completed successfully")
