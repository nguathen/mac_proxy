#!/usr/bin/env python3
"""
Script để sửa lỗi gost random server selection
Đảm bảo mỗi gost port có server khác nhau
"""

import os
import json
import random
import time
import sys

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from proxy_api import proxy_api
from protonvpn_api import ProtonVPNAPI
from nordvpn_api import NordVPNAPI

# Initialize APIs
protonvpn_api = ProtonVPNAPI()
nordvpn_api = NordVPNAPI()

LOG_DIR = "./logs"

def get_random_server_for_port(port, provider='protonvpn'):
    """Get a random server for specific port to ensure different servers"""
    try:
        # Add port-specific seed to ensure different servers
        random.seed(int(time.time() * 1000) + int(port))
        
        if provider == 'protonvpn':
            servers = protonvpn_api.fetch_servers() if protonvpn_api else []
            if servers:
                random.shuffle(servers)
                selected_server = servers[int(port) % len(servers)]
                return selected_server.get('domain', selected_server.get('name', ''))
        elif provider == 'nordvpn':
            servers = nordvpn_api.fetch_servers() if nordvpn_api else []
            if servers:
                random.shuffle(servers)
                selected_server = servers[int(port) % len(servers)]
                return selected_server.get('hostname', selected_server.get('name', ''))
        
        return None
    except Exception as e:
        print(f"⚠️  Error getting random server for port {port}: {e}")
        return None

def reset_gost_configs():
    """Reset all gost configs with different random servers"""
    try:
        # Find all existing config files
        config_files = []
        for config_file in os.listdir(LOG_DIR):
            if config_file.startswith('gost_') and config_file.endswith('.config'):
                config_files.append(config_file)
                os.remove(os.path.join(LOG_DIR, config_file))
                print(f"✅ Removed {config_file}")
        
        print(f"✅ Removed {len(config_files)} existing config files")
        
        # Create new configs with different servers for common ports
        gost_ports = ["18181", "18182", "18183", "18184", "18185", "18186", "18187"]
        for port in gost_ports:
            try:
                # Try ProtonVPN first
                server_name = get_random_server_for_port(port, 'protonvpn')
                if server_name:
                    proxy_url = proxy_api.get_protonvpn_proxy(server_name)
                    
                    if proxy_url:
                        config = {
                            'port': port,
                            'provider': 'protonvpn',
                            'country': server_name,
                            'proxy_url': proxy_url,
                            'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                        }
                        
                        config_file = os.path.join(LOG_DIR, f'gost_{port}.config')
                        with open(config_file, 'w') as f:
                            json.dump(config, f, indent=4)
                        
                        print(f"✅ Created gost_{port}.config with ProtonVPN server: {server_name}")
                        continue
                
                # If ProtonVPN failed, try NordVPN
                server_name = get_random_server_for_port(port, 'nordvpn')
                if server_name:
                    proxy_url = proxy_api.get_nordvpn_proxy(server_name)
                    
                    if proxy_url:
                        config = {
                            'port': port,
                            'provider': 'nordvpn',
                            'country': server_name,
                            'proxy_url': proxy_url,
                            'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                        }
                        
                        config_file = os.path.join(LOG_DIR, f'gost_{port}.config')
                        with open(config_file, 'w') as f:
                            json.dump(config, f, indent=4)
                        
                        print(f"✅ Created gost_{port}.config with NordVPN server: {server_name}")
                        continue
                
                print(f"⚠️  Failed to create config for port {port}")
                
            except Exception as e:
                print(f"⚠️  Error creating config for port {port}: {e}")
        
        print("✅ Gost configs reset completed!")
        
    except Exception as e:
        print(f"❌ Error resetting gost configs: {e}")

if __name__ == "__main__":
    print("🔄 Resetting gost configs with different random servers...")
    reset_gost_configs()
    print("✅ Done! Restart gost ports to use new configs.")
