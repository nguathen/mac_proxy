#!/usr/bin/env python3
"""
Test Smart VPN Selection
Test logic chọn VPN provider thông minh
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from webui.chrome_handler import _determine_smart_vpn_provider

def test_vpn_provider_logic():
    """Test logic chọn VPN provider"""
    print("🧪 Testing smart VPN provider selection...")
    
    # Test case 1: Server name có pattern rõ ràng
    print("\n📋 Test 1: Server name có pattern rõ ràng")
    test_cases = [
        ("uk2466.nordvpn.com", "NordVPN server"),
        ("node-us-240.protonvpn.net", "ProtonVPN server"),
        ("sg630.nordvpn.com", "NordVPN server"),
        ("node-de-15.protonvpn.net", "ProtonVPN server")
    ]
    
    for server, description in test_cases:
        profiles = []
        provider = _determine_smart_vpn_provider(server, profiles)
        print(f"  {description}: {server} -> {provider}")
    
    # Test case 2: Country code
    print("\n📋 Test 2: Country code (2 ký tự)")
    country_codes = ["US", "UK", "DE", "SG", "CA"]
    
    for country in country_codes:
        profiles = []
        provider = _determine_smart_vpn_provider(country, profiles)
        print(f"  Country {country} -> {provider}")
    
    # Test case 3: Random server (empty)
    print("\n📋 Test 3: Random server (empty)")
    profiles = []
    provider = _determine_smart_vpn_provider("", profiles)
    print(f"  Empty server -> {provider}")
    
    provider = _determine_smart_vpn_provider(None, profiles)
    print(f"  None server -> {provider}")

def test_connection_limit_logic():
    """Test logic với giới hạn kết nối"""
    print("\n🧪 Testing connection limit logic...")
    
    # Test case 1: Ít kết nối
    print("\n📋 Test 1: Ít kết nối (NordVPN: 2, ProtonVPN: 1)")
    profiles = [
        {"proxy": "socks5://127.0.0.1:7891:uk2466.nordvpn.com:89"},
        {"proxy": "socks5://127.0.0.1:7892:sg630.nordvpn.com:89"},
        {"proxy": "socks5://127.0.0.1:7893:node-us-240.protonvpn.net:4443"}
    ]
    
    provider = _determine_smart_vpn_provider("US", profiles)
    print(f"  Country US with few connections -> {provider}")
    
    # Test case 2: NordVPN gần đạt giới hạn
    print("\n📋 Test 2: NordVPN gần đạt giới hạn (8 connections)")
    profiles = []
    for i in range(8):
        profiles.append({"proxy": f"socks5://127.0.0.1:789{i+1}:uk{i+1}.nordvpn.com:89"})
    
    provider = _determine_smart_vpn_provider("DE", profiles)
    print(f"  Country DE with 8 NordVPN connections -> {provider}")
    
    # Test case 3: NordVPN đạt giới hạn
    print("\n📋 Test 3: NordVPN đạt giới hạn (10 connections)")
    profiles = []
    for i in range(10):
        profiles.append({"proxy": f"socks5://127.0.0.1:789{i+1}:uk{i+1}.nordvpn.com:89"})
    
    provider = _determine_smart_vpn_provider("FR", profiles)
    print(f"  Country FR with 10 NordVPN connections -> {provider}")
    
    # Test case 4: ProtonVPN có nhiều kết nối
    print("\n📋 Test 4: ProtonVPN có nhiều kết nối (10 connections)")
    profiles = []
    for i in range(10):
        profiles.append({"proxy": f"socks5://127.0.0.1:789{i+1}:node-us-{i+1}.protonvpn.net:4443"})
    
    provider = _determine_smart_vpn_provider("IT", profiles)
    print(f"  Country IT with 10 ProtonVPN connections -> {provider}")

def test_mixed_connections():
    """Test với kết nối hỗn hợp"""
    print("\n🧪 Testing mixed connections...")
    
    # Test case: Hỗn hợp NordVPN và ProtonVPN
    profiles = [
        {"proxy": "socks5://127.0.0.1:7891:uk2466.nordvpn.com:89"},
        {"proxy": "socks5://127.0.0.1:7892:sg630.nordvpn.com:89"},
        {"proxy": "socks5://127.0.0.1:7893:node-us-240.protonvpn.net:4443"},
        {"proxy": "socks5://127.0.0.1:7894:node-de-15.protonvpn.net:4443"},
        {"proxy": "socks5://127.0.0.1:7895:mx86.nordvpn.com:89"},
    ]
    
    print(f"  Mixed connections (NordVPN: 3, ProtonVPN: 2)")
    provider = _determine_smart_vpn_provider("JP", profiles)
    print(f"  Country JP with mixed connections -> {provider}")

def test_edge_cases():
    """Test các trường hợp edge case"""
    print("\n🧪 Testing edge cases...")
    
    # Test case 1: Profiles rỗng
    profiles = []
    provider = _determine_smart_vpn_provider("", profiles)
    print(f"  Empty profiles -> {provider}")
    
    # Test case 2: Profiles với proxy không hợp lệ
    profiles = [
        {"proxy": "invalid_proxy"},
        {"proxy": "socks5://127.0.0.1:7891"},
        {"proxy": ""}
    ]
    provider = _determine_smart_vpn_provider("", profiles)
    print(f"  Invalid proxy formats -> {provider}")
    
    # Test case 3: Server name không rõ ràng
    provider = _determine_smart_vpn_provider("unknown-server", profiles)
    print(f"  Unknown server -> {provider}")

if __name__ == "__main__":
    test_vpn_provider_logic()
    test_connection_limit_logic()
    test_mixed_connections()
    test_edge_cases()
    print("\n✅ Test completed!")
