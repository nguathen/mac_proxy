#!/usr/bin/env python3
"""
Test VPN Provider Ratio
Test tỉ lệ VPN provider 7:3 (ProtonVPN:NordVPN)
"""

import requests
import json
import sys
import os
from collections import Counter

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from webui.chrome_handler import _determine_smart_vpn_provider

def test_provider_ratio():
    """Test tỉ lệ provider với nhiều lần gọi"""
    print("🧪 Testing VPN provider ratio 7:3...")
    
    # Test với country codes
    country_codes = ["US", "UK", "DE", "SG", "CA", "FR", "JP", "AU", "IT", "ES"]
    results = []
    
    print(f"\n📋 Testing with {len(country_codes)} country codes...")
    for country in country_codes:
        # Test 10 lần cho mỗi country
        for i in range(10):
            provider = _determine_smart_vpn_provider(country, [])
            results.append(provider)
    
    # Thống kê kết quả
    provider_counts = Counter(results)
    total = len(results)
    protonvpn_count = provider_counts.get('protonvpn', 0)
    nordvpn_count = provider_counts.get('nordvpn', 0)
    
    print(f"\n📊 Results ({total} tests):")
    print(f"  ProtonVPN: {protonvpn_count} ({protonvpn_count/total*100:.1f}%)")
    print(f"  NordVPN: {nordvpn_count} ({nordvpn_count/total*100:.1f}%)")
    
    # Kiểm tra tỉ lệ
    expected_protonvpn = 0.7
    expected_nordvpn = 0.3
    actual_protonvpn = protonvpn_count / total
    actual_nordvpn = nordvpn_count / total
    
    print(f"\n🎯 Ratio Analysis:")
    print(f"  Expected: ProtonVPN {expected_protonvpn*100:.0f}%, NordVPN {expected_nordvpn*100:.0f}%")
    print(f"  Actual: ProtonVPN {actual_protonvpn*100:.1f}%, NordVPN {actual_nordvpn*100:.1f}%")
    
    # Kiểm tra xem có gần với tỉ lệ mong muốn không (tolerance ±5%)
    tolerance = 0.05
    protonvpn_ok = abs(actual_protonvpn - expected_protonvpn) <= tolerance
    nordvpn_ok = abs(actual_nordvpn - expected_nordvpn) <= tolerance
    
    if protonvpn_ok and nordvpn_ok:
        print(f"  ✅ Ratio is within acceptable range (±{tolerance*100:.0f}%)")
    else:
        print(f"  ⚠️  Ratio is outside acceptable range (±{tolerance*100:.0f}%)")
    
    return results

def test_random_server_ratio():
    """Test tỉ lệ với random server"""
    print("\n🧪 Testing random server ratio...")
    
    results = []
    for i in range(50):  # Test 50 lần
        provider = _determine_smart_vpn_provider("", [])  # Empty server = random
        results.append(provider)
    
    # Thống kê kết quả
    provider_counts = Counter(results)
    total = len(results)
    protonvpn_count = provider_counts.get('protonvpn', 0)
    nordvpn_count = provider_counts.get('nordvpn', 0)
    
    print(f"\n📊 Random Server Results ({total} tests):")
    print(f"  ProtonVPN: {protonvpn_count} ({protonvpn_count/total*100:.1f}%)")
    print(f"  NordVPN: {nordvpn_count} ({nordvpn_count/total*100:.1f}%)")
    
    return results

def test_connection_limits():
    """Test với connection limits"""
    print("\n🧪 Testing with connection limits...")
    
    # Test case 1: NordVPN đạt giới hạn
    print("\n📋 Test 1: NordVPN at limit (10 connections)")
    profiles = []
    for i in range(10):
        profiles.append({"proxy": f"socks5://127.0.0.1:789{i+1}:uk{i+1}.nordvpn.com:89"})
    
    results = []
    for i in range(20):
        provider = _determine_smart_vpn_provider("US", profiles)
        results.append(provider)
    
    provider_counts = Counter(results)
    print(f"  Results: {dict(provider_counts)}")
    if provider_counts.get('protonvpn', 0) == 20:
        print("  ✅ Correctly forced to ProtonVPN when NordVPN at limit")
    else:
        print("  ❌ Failed to force ProtonVPN when NordVPN at limit")
    
    # Test case 2: ProtonVPN có quá nhiều kết nối
    print("\n📋 Test 2: ProtonVPN overloaded (15 connections)")
    profiles = []
    for i in range(15):
        profiles.append({"proxy": f"socks5://127.0.0.1:789{i+1}:node-us-{i+1}.protonvpn.net:4443"})
    
    results = []
    for i in range(20):
        provider = _determine_smart_vpn_provider("US", profiles)
        results.append(provider)
    
    provider_counts = Counter(results)
    print(f"  Results: {dict(provider_counts)}")
    if provider_counts.get('nordvpn', 0) == 20:
        print("  ✅ Correctly forced to NordVPN when ProtonVPN overloaded")
    else:
        print("  ❌ Failed to force NordVPN when ProtonVPN overloaded")

def test_server_patterns():
    """Test với server patterns"""
    print("\n🧪 Testing server patterns...")
    
    # Test NordVPN pattern
    provider = _determine_smart_vpn_provider("uk2466.nordvpn.com", [])
    print(f"  NordVPN server pattern: {provider}")
    if provider == 'nordvpn':
        print("  ✅ Correctly identified NordVPN pattern")
    else:
        print("  ❌ Failed to identify NordVPN pattern")
    
    # Test ProtonVPN pattern
    provider = _determine_smart_vpn_provider("node-us-240.protonvpn.net", [])
    print(f"  ProtonVPN server pattern: {provider}")
    if provider == 'protonvpn':
        print("  ✅ Correctly identified ProtonVPN pattern")
    else:
        print("  ❌ Failed to identify ProtonVPN pattern")

if __name__ == "__main__":
    test_provider_ratio()
    test_random_server_ratio()
    test_connection_limits()
    test_server_patterns()
    print("\n✅ Test completed!")
