#!/usr/bin/env python3
"""
Test Random Server Logic
Test logic random-server đã cải thiện để tránh trùng lặp proxy
"""

import requests
import json
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_proxy_list_api():
    """Test API list-proxy"""
    print("🧪 Testing proxy list API...")
    
    try:
        response = requests.get("http://localhost:18112/api/profiles/list-proxy", timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response type: {type(data)}")
            print(f"Response data: {json.dumps(data, indent=2)}")
            
            # Parse used proxies
            used_proxies = set()
            if isinstance(data, dict) and 'data' in data:
                # API returns {"success": true, "data": ["host:port", ...]}
                proxy_list = data.get('data', [])
                for proxy_string in proxy_list:
                    if ':' in proxy_string:
                        used_proxies.add(proxy_string)
                        print(f"Added to used proxies: {proxy_string}")
            elif isinstance(data, list):
                # Fallback: API returns list of profiles
                for profile in data:
                    proxy = profile.get('proxy', '')
                    print(f"Profile proxy: {proxy}")
                    if proxy and ':' in proxy:
                        parts = proxy.split(':')
                        if len(parts) >= 2:
                            try:
                                host = parts[0].replace('socks5://', '').replace('https://', '')
                                port = int(parts[1])
                                proxy_key = f"{host}:{port}"
                                used_proxies.add(proxy_key)
                                print(f"Added to used proxies: {proxy_key}")
                            except (ValueError, IndexError):
                                pass
            
            print(f"Used proxies: {sorted(used_proxies)}")
            return used_proxies
        else:
            print(f"❌ API failed: {response.status_code}")
            return set()
    except Exception as e:
        print(f"❌ Error: {e}")
        return set()

def test_random_server_logic():
    """Test logic random server với proxy exclusion"""
    print("\n🧪 Testing random server logic...")
    
    # Mock server data
    mock_servers = [
        {
            "domain": "node-vn-01.protonvpn.net",
            "name": "Vietnam #1",
            "servers": [{"label": "0"}]
        },
        {
            "domain": "node-vn-02.protonvpn.net", 
            "name": "Vietnam #2",
            "servers": [{"label": "1"}]
        },
        {
            "domain": "node-de-15.protonvpn.net",
            "name": "Germany #15", 
            "servers": [{"label": "2"}]
        },
        {
            "domain": "node-us-10.protonvpn.net",
            "name": "US #10",
            "servers": [{"label": "3"}]
        }
    ]
    
    # Get currently used proxies
    used_proxies = test_proxy_list_api()
    
    print(f"\n📋 Mock servers: {len(mock_servers)}")
    for server in mock_servers:
        domain = server.get('domain', '')
        port = 4443
        if 'servers' in server and len(server['servers']) > 0:
            try:
                label = int(server['servers'][0].get('label', '0'))
                port = 4443 + label
            except (ValueError, TypeError):
                pass
        proxy_key = f"{domain}:{port}"
        print(f"  - {server.get('name', '')}: {proxy_key}")
    
    # Filter available servers
    available_servers = []
    for server in mock_servers:
        domain = server.get('domain', '')
        port = 4443
        if 'servers' in server and len(server['servers']) > 0:
            try:
                label = int(server['servers'][0].get('label', '0'))
                port = 4443 + label
            except (ValueError, TypeError):
                pass
        
        proxy_key = f"{domain}:{port}"
        if proxy_key not in used_proxies:
            available_servers.append(server)
            print(f"✅ Available: {server.get('name', '')} ({proxy_key})")
        else:
            print(f"❌ In use: {server.get('name', '')} ({proxy_key})")
    
    print(f"\n📊 Results:")
    print(f"  Total servers: {len(mock_servers)}")
    print(f"  Used proxies: {len(used_proxies)}")
    print(f"  Available servers: {len(available_servers)}")
    
    if available_servers:
        print(f"  ✅ Can select from {len(available_servers)} available servers")
    else:
        print(f"  ⚠️  All servers are in use, will select from all servers")

def test_protonvpn_api():
    """Test ProtonVPN API integration"""
    print("\n🧪 Testing ProtonVPN API integration...")
    
    try:
        # Test if we can call the API endpoint
        response = requests.post("http://localhost:5000/api/protonvpn/apply/18181", 
                               json={
                                   "country_code": "",
                                   "proxy_host": "",
                                   "proxy_port": ""
                               },
                               timeout=10)
        print(f"API Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API call successful")
            print(f"Response: {json.dumps(data, indent=2)}")
        else:
            print(f"❌ API call failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error calling API: {e}")

if __name__ == "__main__":
    test_proxy_list_api()
    test_random_server_logic()
    test_protonvpn_api()
    print("\n✅ Test completed!")
