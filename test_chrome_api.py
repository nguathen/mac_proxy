#!/usr/bin/env python3
"""
Test script cho Chrome Proxy Check API
"""

import requests
import json

API_URL = "http://localhost:5000/api/chrome/proxy-check"

# Test cases
test_cases = [
    {
        "name": "Case 1: Exact match - proxy already in use",
        "data": {
            "proxy_check": "socks5://server:7891:vn42.nordvpn.com:89",
            "data": {
                "count": 2,
                "profiles": [
                    {"id": 1, "name": "Profile 1", "proxy": "socks5://127.0.0.1:7891:vn42.nordvpn.com:89"},
                    {"id": 2, "name": "Profile 2", "proxy": "socks5://127.0.0.1:7892:us10.nordvpn.com:89"}
                ]
            }
        }
    },
    {
        "name": "Case 2: Port in use with different server - create new Gost",
        "data": {
            "proxy_check": "socks5://server:7891:us-ca112.nordvpn.com:89",
            "data": {
                "count": 2,
                "profiles": [
                    {"id": 1, "name": "Profile 1", "proxy": "socks5://127.0.0.1:7891:vn42.nordvpn.com:89"},
                    {"id": 2, "name": "Profile 2", "proxy": "socks5://127.0.0.1:7892:jp10.nordvpn.com:89"}
                ]
            }
        }
    },
    {
        "name": "Case 3: Gost exists but different server - reconfigure",
        "data": {
            "proxy_check": "socks5://server:7891:de507.nordvpn.com:89",
            "data": {
                "count": 1,
                "profiles": [
                    {"id": 1, "name": "Profile 1", "proxy": "socks5://127.0.0.1:7892:us-ca112.nordvpn.com:89"}
                ]
            }
        }
    },
    {
        "name": "Case 4: Gost doesn't exist - create new",
        "data": {
            "proxy_check": "socks5://server:7893:uk-fr18.nordvpn.com:89",
            "data": {
                "count": 1,
                "profiles": [
                    {"id": 1, "name": "Profile 1", "proxy": "socks5://127.0.0.1:7891:vn42.nordvpn.com:89"}
                ]
            }
        }
    },
    {
        "name": "Case 5: ProtonVPN server",
        "data": {
            "proxy_check": "socks5://server:7894:af-03.protonvpn.net:443",
            "data": {
                "count": 1,
                "profiles": [
                    {"id": 1, "name": "Profile 1", "proxy": "socks5://127.0.0.1:7891:vn42.nordvpn.com:89"}
                ]
            }
        }
    },
    {
        "name": "Case 6: Reuse available Gost (not in profiles list)",
        "data": {
            "proxy_check": "socks5://server:7891:fr921.nordvpn.com:89",
            "data": {
                "count": 2,
                "profiles": [
                    {"id": 1, "name": "Profile 1", "proxy": "socks5://127.0.0.1:7892:us-ca112.nordvpn.com:89"},
                    {"id": 2, "name": "Profile 2", "proxy": "socks5://127.0.0.1:7893:de507.nordvpn.com:89"}
                ]
            }
        }
    },
    {
        "name": "Case 7: Custom test with thenngua.ddns.net",
        "data": {
            "proxy_check": "socks5://thenngua.ddns.net:7891:us:1",
            "data": {
                "count": 1,
                "profiles": [
                    {"id": 652, "name": "P-20251020_104629", "proxy": "socks5://thenngua.ddns.net:7894"}
                ]
            }
        }
    }
]

def test_api(test_case):
    """Test một test case"""
    print(f"\n{'='*80}")
    print(f"Test: {test_case['name']}")
    print(f"{'='*80}")
    print(f"Request data:")
    print(json.dumps(test_case['data'], indent=2))
    
    try:
        response = requests.post(API_URL, json=test_case['data'], timeout=30)
        print(f"\nStatus code: {response.status_code}")
        print(f"\nResponse:")
        
        # Handle both JSON and string responses
        try:
            json_response = response.json()
            print(json.dumps(json_response, indent=2))
        except:
            # If not JSON, print as string
            print(response.text)
        
        return response.status_code == 200
    except Exception as e:
        print(f"\nError: {e}")
        return False

if __name__ == '__main__':
    print("Chrome Proxy Check API Test")
    print("="*80)
    print(f"API URL: {API_URL}")
    print("="*80)
    
    # Test connectivity
    try:
        response = requests.get("http://localhost:5000/api/status", timeout=5)
        if response.status_code == 200:
            print("✅ WebUI is running")
        else:
            print("❌ WebUI not responding properly")
            exit(1)
    except Exception as e:
        print(f"❌ Cannot connect to WebUI: {e}")
        print("\nPlease start WebUI first:")
        print("  cd webui && python3 app.py")
        exit(1)
    
    # Run tests
    results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n\n{'#'*80}")
        print(f"# Test {i}/{len(test_cases)}")
        print(f"{'#'*80}")
        
        success = test_api(test_case)
        results.append((test_case['name'], success))
        
        # Wait a moment before next test
        if i < len(test_cases):
            import time
            time.sleep(1)
    
    # Summary
    print(f"\n\n{'='*80}")
    print("Test Summary")
    print(f"{'='*80}")
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
    
    passed = sum(1 for _, success in results if success)
    print(f"\nTotal: {passed}/{len(results)} tests passed")
