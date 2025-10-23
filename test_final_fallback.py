#!/usr/bin/env python3
"""
Test Final Fallback Logic
Test logic fallback cuối cùng với random server bất kỳ
"""

import requests
import json
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_extreme_country_codes():
    """Test với các country code cực kỳ hiếm hoặc không tồn tại"""
    print("🧪 Testing extreme country codes...")
    
    # Test với các country code cực kỳ hiếm
    extreme_codes = [
        ("ZZ", "Non-existent country"),
        ("AA", "Invalid country"),
        ("BB", "Fake country"),
        ("CC", "Test country"),
        ("DD", "Unknown country")
    ]
    
    for code, description in extreme_codes:
        print(f"\n📋 Testing {code} ({description})")
        try:
            response = requests.post("http://localhost:5000/api/chrome/proxy-check", 
                                   json={
                                       "proxy_check": f"socks5://127.0.0.1:7891:{code}:443",
                                       "data": {"profiles": []}
                                   },
                                   timeout=15)
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                result = response.text
                print(f"  ✅ Success: {result}")
                # Kiểm tra xem có phải random server không
                if "node-" in result or "uk" in result or "sg" in result:
                    print(f"  🎯 Random server from any country selected")
                else:
                    print(f"  ⚠️  Unexpected server format")
            else:
                print(f"  ❌ Failed: {response.text}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

def test_nonexistent_servers():
    """Test với server names không tồn tại"""
    print("\n🧪 Testing nonexistent servers...")
    
    # Test với các server names không tồn tại
    fake_servers = [
        "fake-server-1.com",
        "nonexistent-server.net", 
        "invalid-server.org",
        "test-server.io",
        "dummy-server.co"
    ]
    
    for server in fake_servers:
        print(f"\n📋 Testing server: {server}")
        try:
            response = requests.post("http://localhost:5000/api/chrome/proxy-check", 
                                   json={
                                       "proxy_check": f"socks5://127.0.0.1:7891:{server}:443",
                                       "data": {"profiles": []}
                                   },
                                   timeout=15)
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                result = response.text
                print(f"  ✅ Success: {result}")
                # Kiểm tra xem có phải random server không
                if "node-" in result or "uk" in result or "sg" in result:
                    print(f"  🎯 Random server from any country selected")
                else:
                    print(f"  ⚠️  Unexpected server format")
            else:
                print(f"  ❌ Failed: {response.text}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

def test_mixed_scenarios():
    """Test với các scenario hỗn hợp"""
    print("\n🧪 Testing mixed scenarios...")
    
    # Test với empty server (should always work)
    print("\n📋 Testing empty server (random)")
    try:
        response = requests.post("http://localhost:5000/api/chrome/proxy-check", 
                               json={
                                   "proxy_check": "socks5://127.0.0.1:7891::443",
                                   "data": {"profiles": []}
                               },
                               timeout=15)
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            result = response.text
            print(f"  ✅ Success: {result}")
        else:
            print(f"  ❌ Failed: {response.text}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Test với country code có thể có hoặc không có
    print("\n📋 Testing potentially rare country codes")
    rare_codes = ["AD", "LI", "MC", "SM", "VA"]  # Các nước nhỏ
    
    for code in rare_codes:
        print(f"\n  Testing {code}")
        try:
            response = requests.post("http://localhost:5000/api/chrome/proxy-check", 
                                   json={
                                       "proxy_check": f"socks5://127.0.0.1:7891:{code}:443",
                                       "data": {"profiles": []}
                                   },
                                   timeout=15)
            print(f"    Status: {response.status_code}")
            if response.status_code == 200:
                result = response.text
                print(f"    ✅ Success: {result}")
            else:
                print(f"    ❌ Failed: {response.text}")
        except Exception as e:
            print(f"    ❌ Error: {e}")

def test_fallback_chain():
    """Test toàn bộ chain fallback"""
    print("\n🧪 Testing complete fallback chain...")
    
    # Test với country code hoàn toàn không tồn tại
    print("\n📋 Testing complete fallback chain with ZZ")
    try:
        response = requests.post("http://localhost:5000/api/chrome/proxy-check", 
                               json={
                                   "proxy_check": "socks5://127.0.0.1:7891:ZZ:443",
                                   "data": {"profiles": []}
                               },
                               timeout=20)  # Tăng timeout cho fallback chain
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            result = response.text
            print(f"  ✅ Success: {result}")
            print(f"  🎯 Final fallback worked - got random server from any country")
        else:
            print(f"  ❌ Failed: {response.text}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

if __name__ == "__main__":
    test_extreme_country_codes()
    test_nonexistent_servers()
    test_mixed_scenarios()
    test_fallback_chain()
    print("\n✅ Test completed!")
