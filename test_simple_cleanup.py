#!/usr/bin/env python3
"""
Test Simple Cleanup
Test đơn giản logic cleanup với thời gian thực
"""

import sys
import os
import json
import time
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_credential_updater import AutoCredentialUpdater

def test_current_cleanup():
    """Test cleanup với services hiện tại"""
    print("🧪 Testing current cleanup logic...")
    
    updater = AutoCredentialUpdater()
    
    # Test với API thật
    print("📋 Testing with real API...")
    try:
        import requests
        response = requests.get("http://localhost:18112/api/profiles/count-open", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"API Response: {data}")
            
            # Parse used ports
            used_ports = set()
            for profile in data:
                proxy = profile.get('proxy', '')
                if proxy and ':' in proxy:
                    parts = proxy.split(':')
                    for part in parts:
                        if part.isdigit() and 1000 <= int(part) <= 65535:
                            port = int(part)
                            used_ports.add(port)
            
            print(f"Used ports: {sorted(used_ports)}")
            
            # Test cleanup
            print("\n🧪 Testing cleanup with real data...")
            updater._cleanup_unused_services()
            
        else:
            print(f"❌ API failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_manual_cleanup():
    """Test manual cleanup"""
    print("\n🧪 Testing manual cleanup...")
    
    updater = AutoCredentialUpdater()
    updater.manual_cleanup()

if __name__ == "__main__":
    test_current_cleanup()
    test_manual_cleanup()
    print("\n✅ Test completed!")
