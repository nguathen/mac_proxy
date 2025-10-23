#!/usr/bin/env python3
"""
Test NordVPN Random Server Logic
Test logic random-server cho NordVPN đã cập nhật
"""

import requests
import json
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_nordvpn_random_api():
    """Test NordVPN random server API"""
    print("🧪 Testing NordVPN random server API...")
    
    try:
        # Test random NordVPN server
        response = requests.post("http://localhost:5000/api/nordvpn/apply/18183", 
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
            
            # Extract server info
            server = data.get('server', {})
            proxy_url = data.get('proxy_url', '')
            
            print(f"\n📋 Selected server:")
            print(f"  Name: {server.get('name', 'N/A')}")
            print(f"  Hostname: {server.get('hostname', 'N/A')}")
            print(f"  Country: {server.get('country', 'N/A')}")
            print(f"  Load: {server.get('load', 'N/A')}%")
            print(f"  Proxy URL: {proxy_url}")
            
            return True
        else:
            print(f"❌ API call failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error calling API: {e}")
        return False

def test_proxy_exclusion():
    """Test proxy exclusion logic"""
    print("\n🧪 Testing proxy exclusion logic...")
    
    # Get current used proxies
    try:
        response = requests.get("http://localhost:18112/api/profiles/list-proxy", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and 'data' in data:
                proxy_list = data.get('data', [])
                print(f"📋 Currently used proxies: {len(proxy_list)}")
                for proxy in proxy_list:
                    print(f"  - {proxy}")
                return proxy_list
        else:
            print(f"❌ Failed to get used proxies: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error getting used proxies: {e}")
        return []

def test_multiple_random_calls():
    """Test multiple random calls to see if they avoid duplicates"""
    print("\n🧪 Testing multiple random calls...")
    
    results = []
    for i in range(3):
        print(f"\n📋 Test {i+1}:")
        try:
            response = requests.post(f"http://localhost:5000/api/nordvpn/apply/1818{i+4}", 
                                   json={
                                       "country_code": "",
                                       "proxy_host": "",
                                       "proxy_port": ""
                                   },
                                   timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                server = data.get('server', {})
                hostname = server.get('hostname', '')
                port = 89  # NordVPN standard port
                proxy_key = f"{hostname}:{port}"
                
                results.append(proxy_key)
                print(f"  ✅ Selected: {server.get('name', 'N/A')} ({proxy_key})")
            else:
                print(f"  ❌ Failed: {response.status_code}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    # Check for duplicates
    unique_results = set(results)
    print(f"\n📊 Results:")
    print(f"  Total calls: {len(results)}")
    print(f"  Unique servers: {len(unique_results)}")
    print(f"  Duplicates: {len(results) - len(unique_results)}")
    
    if len(unique_results) == len(results):
        print("  ✅ No duplicates found!")
    else:
        print("  ⚠️  Some duplicates found")
        print(f"  Duplicate servers: {[r for r in results if results.count(r) > 1]}")

def test_nordvpn_vs_protonvpn():
    """Test NordVPN vs ProtonVPN to ensure different logic"""
    print("\n🧪 Testing NordVPN vs ProtonVPN...")
    
    # Test NordVPN
    print("📋 Testing NordVPN random server:")
    try:
        response = requests.post("http://localhost:5000/api/nordvpn/apply/18185", 
                               json={
                                   "country_code": "",
                                   "proxy_host": "",
                                   "proxy_port": ""
                               },
                               timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            server = data.get('server', {})
            print(f"  ✅ NordVPN: {server.get('name', 'N/A')} ({server.get('hostname', 'N/A')})")
        else:
            print(f"  ❌ NordVPN failed: {response.status_code}")
    except Exception as e:
        print(f"  ❌ NordVPN error: {e}")
    
    # Test ProtonVPN
    print("📋 Testing ProtonVPN random server:")
    try:
        response = requests.post("http://localhost:5000/api/protonvpn/apply/18186", 
                               json={
                                   "country_code": "",
                                   "proxy_host": "",
                                   "proxy_port": ""
                               },
                               timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            server = data.get('server', {})
            print(f"  ✅ ProtonVPN: {server.get('name', 'N/A')} ({server.get('domain', 'N/A')})")
        else:
            print(f"  ❌ ProtonVPN failed: {response.status_code}")
    except Exception as e:
        print(f"  ❌ ProtonVPN error: {e}")

if __name__ == "__main__":
    test_proxy_exclusion()
    test_nordvpn_random_api()
    test_multiple_random_calls()
    test_nordvpn_vs_protonvpn()
    print("\n✅ Test completed!")
