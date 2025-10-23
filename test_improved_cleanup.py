#!/usr/bin/env python3
"""
Test Improved Cleanup Logic
Test logic cleanup đã cải thiện với kiểm tra thời gian tạo
"""

import sys
import os
import json
import time
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_credential_updater import AutoCredentialUpdater

def create_test_services():
    """Tạo test services với thời gian tạo khác nhau"""
    print("🧪 Creating test services with different creation times...")
    
    config_dir = "/Volumes/Ssd/Projects/mac_proxy/config"
    
    # Tạo Gost config cũ (10 phút trước)
    old_gost_config = {
        "provider": "protonvpn",
        "country": "node-vn-01.protonvpn.net",
        "proxy_url": "https://token@node-vn-01.protonvpn.net:4453",
        "port": "18181",
        "created_at": datetime.fromtimestamp(datetime.now().timestamp() - 600).isoformat() + "Z"  # 10 phút trước
    }
    
    with open(os.path.join(config_dir, "gost_18181.config"), 'w') as f:
        json.dump(old_gost_config, f, indent=2)
    print("✅ Created old Gost config (10 minutes ago)")
    
    # Tạo Gost config mới (1 phút trước)
    new_gost_config = {
        "provider": "protonvpn", 
        "country": "node-de-15.protonvpn.net",
        "proxy_url": "https://token@node-de-15.protonvpn.net:4453",
        "port": "18182",
        "created_at": datetime.fromtimestamp(datetime.now().timestamp() - 60).isoformat() + "Z"  # 1 phút trước
    }
    
    with open(os.path.join(config_dir, "gost_18182.config"), 'w') as f:
        json.dump(new_gost_config, f, indent=2)
    print("✅ Created new Gost config (1 minute ago)")
    
    # Tạo HAProxy config cũ (8 phút trước)
    old_haproxy_content = f"""
global
    daemon
    pidfile /Volumes/Ssd/Projects/mac_proxy/logs/haproxy_7891.pid

defaults
    mode tcp
    timeout connect 2s
    timeout client 1m

listen socks_proxy
    bind 0.0.0.0:7891
    server gost1 127.0.0.1:18181 check
"""
    
    with open(os.path.join(config_dir, "haproxy_7891.cfg"), 'w') as f:
        f.write(old_haproxy_content)
    print("✅ Created old HAProxy config (8 minutes ago)")
    
    # Tạo HAProxy config mới (2 phút trước)
    new_haproxy_content = f"""
global
    daemon
    pidfile /Volumes/Ssd/Projects/mac_proxy/logs/haproxy_7892.pid

defaults
    mode tcp
    timeout connect 2s
    timeout client 1m

listen socks_proxy
    bind 0.0.0.0:7892
    server gost1 127.0.0.1:18182 check
"""
    
    with open(os.path.join(config_dir, "haproxy_7892.cfg"), 'w') as f:
        f.write(new_haproxy_content)
    print("✅ Created new HAProxy config (2 minutes ago)")

def test_cleanup_logic():
    """Test logic cleanup với thời gian tạo"""
    print("\n🧪 Testing improved cleanup logic...")
    
    updater = AutoCredentialUpdater()
    
    # Scenario: Chỉ HAProxy 7891 được sử dụng (cũ)
    print("\n📋 Scenario: HAProxy 7891 (old) được sử dụng")
    used_ports = {7891}
    print(f"Used ports: {sorted(used_ports)}")
    print("Expected:")
    print("  - Gost 18181 (old): Should be PROTECTED (belongs to HAProxy 7891)")
    print("  - Gost 18182 (new): Should be PROTECTED (too recent)")
    print("  - HAProxy 7891 (old): Should be PROTECTED (in use)")
    print("  - HAProxy 7892 (new): Should be PROTECTED (too recent)")
    
    print("\n🧪 Testing Gost cleanup...")
    updater._cleanup_unused_gost_services(used_ports)
    
    print("\n🧪 Testing HAProxy cleanup...")
    updater._cleanup_unused_haproxy_services(used_ports)
    
    # Scenario: Không có service nào được sử dụng
    print("\n📋 Scenario: No services in use")
    used_ports = set()
    print(f"Used ports: {sorted(used_ports)}")
    print("Expected:")
    print("  - Gost 18181 (old): Should be CLEANED UP")
    print("  - Gost 18182 (new): Should be PROTECTED (too recent)")
    print("  - HAProxy 7891 (old): Should be CLEANED UP")
    print("  - HAProxy 7892 (new): Should be PROTECTED (too recent)")
    
    print("\n🧪 Testing Gost cleanup...")
    updater._cleanup_unused_gost_services(used_ports)
    
    print("\n🧪 Testing HAProxy cleanup...")
    updater._cleanup_unused_haproxy_services(used_ports)

def cleanup_test_files():
    """Dọn dẹp test files"""
    print("\n🧹 Cleaning up test files...")
    
    config_dir = "/Volumes/Ssd/Projects/mac_proxy/config"
    test_files = [
        "gost_18181.config",
        "gost_18182.config",
        "haproxy_7891.cfg",
        "haproxy_7892.cfg"
    ]
    
    for filename in test_files:
        filepath = os.path.join(config_dir, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"✅ Removed {filepath}")

def test_service_age_check():
    """Test riêng logic kiểm tra tuổi service"""
    print("\n🧪 Testing service age check logic...")
    
    updater = AutoCredentialUpdater()
    
    # Test với service cũ
    print("Testing old service (should be safe to cleanup):")
    result = updater._should_cleanup_service(18181, "gost")
    print(f"  Result: {result}")
    
    # Test với service mới
    print("Testing new service (should be protected):")
    result = updater._should_cleanup_service(18182, "gost")
    print(f"  Result: {result}")

if __name__ == "__main__":
    create_test_services()
    test_service_age_check()
    test_cleanup_logic()
    cleanup_test_files()
    print("\n✅ Test completed!")
