#!/usr/bin/env python3
"""
Test tạo HAProxy trực tiếp không cần WebUI
"""

import requests
import json

def test_haproxy_create():
    """Test tạo HAProxy"""
    print("="*80)
    print("Test HAProxy Creation")
    print("="*80)
    
    # Test data
    haproxy_data = {
        'sock_port': 7891,
        'stats_port': 8091,
        'wg_ports': [18181],
        'host_proxy': '127.0.0.1:8111',
        'stats_auth': 'admin:admin123',
        'health_interval': 10
    }
    
    print("Request data:")
    print(json.dumps(haproxy_data, indent=2))
    
    try:
        response = requests.post('http://127.0.0.1:5000/api/haproxy/create', json=haproxy_data, timeout=60)
        print(f"\nStatus code: {response.status_code}")
        print(f"\nResponse:")
        
        try:
            json_response = response.json()
            print(json.dumps(json_response, indent=2))
        except:
            print(response.text)
        
        return response.status_code == 200
    except Exception as e:
        print(f"\nError: {e}")
        return False

if __name__ == '__main__':
    print("HAProxy Creation Test")
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
    
    # Run test
    success = test_haproxy_create()
    
    if success:
        print("\n✅ Test completed successfully")
    else:
        print("\n❌ Test failed")
