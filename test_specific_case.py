#!/usr/bin/env python3
"""
Test script cho specific case: thenngua.ddns.net
"""

import requests
import json
import time

API_URL = "http://localhost:5000/api/chrome/proxy-check"

# Your specific test case - original request
test_data = {
    "proxy_check": "socks5://thenngua.ddns.net:7891:us:1",
    "data": {
        "count": 1,
        "profiles": [
            {"id": 652, "name": "P-20251020_104629", "proxy": "socks5://thenngua.ddns.net:7894"}
        ]
    }
}

def test_specific_case():
    """Test specific case với debugging"""
    print("="*80)
    print("Testing specific case: thenngua.ddns.net")
    print("="*80)
    print("Request data:")
    print(json.dumps(test_data, indent=2))
    
    try:
        print("\nSending request...")
        start_time = time.time()
        
        response = requests.post(API_URL, json=test_data, timeout=60)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\nResponse time: {duration:.2f} seconds")
        print(f"Status code: {response.status_code}")
        print(f"\nResponse:")
        
        # Handle both JSON and string responses
        try:
            json_response = response.json()
            print(json.dumps(json_response, indent=2))
        except:
            # If not JSON, print as string
            print(response.text)
        
        return response.status_code == 200
        
    except requests.exceptions.Timeout:
        print(f"\n❌ Request timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == '__main__':
    print("Specific Case Test: thenngua.ddns.net")
    print("="*80)
    
    # Test connectivity first
    try:
        print("Testing WebUI connectivity...")
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
    
    # Run the specific test
    success = test_specific_case()
    
    if success:
        print("\n✅ Test PASSED")
    else:
        print("\n❌ Test FAILED")