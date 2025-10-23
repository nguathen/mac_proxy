#!/usr/bin/env python3
"""
Test Fallback Logic
Test logic fallback khi provider không có country
"""

import requests
import json
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_fallback_logic():
    """Test logic fallback với các trường hợp khác nhau"""
    print("🧪 Testing fallback logic...")
    
    # Test case 1: Country code không có trong NordVPN
    print("\n📋 Test 1: Country code không có trong NordVPN")
    try:
        response = requests.post("http://localhost:5000/api/chrome/proxy-check", 
                               json={
                                   "proxy_check": "socks5://127.0.0.1:7891:XX:443",
                                   "data": {"profiles": []}
                               },
                               timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.text
            print(f"✅ Success: {result}")
        else:
            print(f"❌ Failed: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test case 2: Country code không có trong ProtonVPN
    print("\n📋 Test 2: Country code không có trong ProtonVPN")
    try:
        response = requests.post("http://localhost:5000/api/chrome/proxy-check", 
                               json={
                                   "proxy_check": "socks5://127.0.0.1:7892:YY:443",
                                   "data": {"profiles": []}
                               },
                               timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.text
            print(f"✅ Success: {result}")
        else:
            print(f"❌ Failed: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test case 3: Server name không tồn tại
    print("\n📋 Test 3: Server name không tồn tại")
    try:
        response = requests.post("http://localhost:5000/api/chrome/proxy-check", 
                               json={
                                   "proxy_check": "socks5://127.0.0.1:7893:nonexistent-server.com:443",
                                   "data": {"profiles": []}
                               },
                               timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.text
            print(f"✅ Success: {result}")
        else:
            print(f"❌ Failed: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_provider_fallback():
    """Test fallback giữa các provider"""
    print("\n🧪 Testing provider fallback...")
    
    # Test với country code thông thường
    test_cases = [
        ("US", "United States"),
        ("UK", "United Kingdom"), 
        ("DE", "Germany"),
        ("SG", "Singapore"),
        ("CA", "Canada")
    ]
    
    for country, name in test_cases:
        print(f"\n📋 Testing country {country} ({name})")
        try:
            response = requests.post("http://localhost:5000/api/chrome/proxy-check", 
                                   json={
                                       "proxy_check": f"socks5://127.0.0.1:7891:{country}:443",
                                       "data": {"profiles": []}
                                   },
                                   timeout=10)
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                result = response.text
                print(f"  ✅ Success: {result}")
            else:
                print(f"  ❌ Failed: {response.text}")
        except Exception as e:
            print(f"  ❌ Error: {e}")

def test_random_server_fallback():
    """Test fallback với random server"""
    print("\n🧪 Testing random server fallback...")
    
    # Test với empty server (random)
    try:
        response = requests.post("http://localhost:5000/api/chrome/proxy-check", 
                               json={
                                   "proxy_check": "socks5://127.0.0.1:7891::443",
                                   "data": {"profiles": []}
                               },
                               timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.text
            print(f"✅ Success: {result}")
        else:
            print(f"❌ Failed: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_fallback_logic()
    test_provider_fallback()
    test_random_server_fallback()
    print("\n✅ Test completed!")
