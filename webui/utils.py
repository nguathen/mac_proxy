"""
Utility Functions
Các function tiện ích chung
"""

import subprocess
import os
import json
import sys
import re
from datetime import datetime

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_command(cmd, cwd=None):
    """Chạy shell command và trả về output"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'stdout': '',
            'stderr': 'Command timeout',
            'returncode': -1
        }
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'returncode': -1
        }

def get_available_haproxy_ports():
    """Dynamically scan for available HAProxy ports from config files"""
    haproxy_ports = set()
    
    # Scan config files
    config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config')
    if os.path.exists(config_dir):
        for filename in os.listdir(config_dir):
            if filename.startswith('haproxy_') and filename.endswith('.cfg'):
                try:
                    port = filename.replace('haproxy_', '').replace('.cfg', '')
                    haproxy_ports.add(port)
                except (ValueError, IndexError):
                    pass
    
    return sorted(list(haproxy_ports))

def get_available_gost_ports():
    """Dynamically scan for available gost ports from config files"""
    gost_ports = set()
    
    # Scan config files in config/ directory
    config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config')
    if os.path.exists(config_dir):
        for filename in os.listdir(config_dir):
            if filename.startswith('gost_') and filename.endswith('.config'):
                try:
                    port = filename.replace('gost_', '').replace('.config', '')
                    gost_ports.add(port)
                except (ValueError, IndexError):
                    pass
    
    return sorted(list(gost_ports))

def is_valid_gost_port(port):
    """Check if port is a valid gost port using dynamic discovery"""
    available_ports = get_available_gost_ports()
    return port in available_ports

def parse_gost_config(port):
    """Parse gost config for port"""
    if not is_valid_gost_port(port):
        return None
    
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Use port-based file naming in config/ directory
    config_file = os.path.join(BASE_DIR, 'config', f'gost_{port}.config')
    
    # Default config
    config = {
        'port': port,
        'proxy_url': '',
        'provider': 'protonvpn',
        'country': ''
    }
    
    # Try to load from config file
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                saved_config = json.load(f)
                config.update(saved_config)
                # Port trả về là port của proxy server (từ proxy_url hoặc port field)
                if 'port' in saved_config and saved_config['port']:
                    config['port'] = saved_config['port']
                elif 'proxy_url' in saved_config and saved_config['proxy_url']:
                    # Trích xuất port từ proxy_url
                    proxy_url = saved_config['proxy_url']
                    port_match = re.search(r':(\d+)$', proxy_url)
                    if port_match:
                        config['port'] = port_match.group(1)
        except Exception:
            pass
    
    return config

def save_gost_config(port, config):
    """Save gost config for port"""
    try:
        if not is_valid_gost_port(port):
            return False
            
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        provider = config.get('provider', 'protonvpn')
        country = config.get('country', '')
        
        if not provider or not country:
            return False
        
        # Use port-based file naming in config/ directory
        config_file = os.path.join(BASE_DIR, 'config', f'gost_{port}.config')
        
        # Thêm thông tin cần thiết vào config
        config['port'] = port
        config['created_at'] = datetime.now().isoformat() + 'Z'
        
        try:
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            print(f"⚠️  Error saving config: {e}")
            return False
    except Exception as e:
        return False

def get_random_server_for_port(port, provider='protonvpn'):
    """Get a random server for specific port to ensure different servers"""
    try:
        import random
        import time
        
        # Add port-specific seed to ensure different servers
        random.seed(int(time.time() * 1000) + int(port))
        
        if provider == 'protonvpn':
            from protonvpn_api import ProtonVPNAPI
            protonvpn_api = ProtonVPNAPI()
            servers = protonvpn_api.fetch_servers() if protonvpn_api else []
            if servers:
                return random.choice(servers)
        elif provider == 'nordvpn':
            from nordvpn_api import NordVPNAPI
            nordvpn_api = NordVPNAPI()
            servers = nordvpn_api.fetch_servers() if nordvpn_api else []
            if servers:
                return random.choice(servers)
        
        return None
    except Exception:
        return None

def get_protonvpn_proxy_with_server(server):
    """Get ProtonVPN proxy URL with server"""
    try:
        from proxy_api import proxy_api
        
        if not server:
            return None
        
        # Get server domain
        domain = server.get('domain', '')
        if not domain:
            return None
        
        # Get server label for port calculation
        server_label = '0'  # Default
        if server.get('servers') and len(server['servers']) > 0:
            server_label = server['servers'][0].get('label', '0')
        
        try:
            server_label_int = int(server_label)
        except (ValueError, TypeError):
            server_label_int = 0  # Fallback to 0
        
        # Calculate port: 4443 + server_label
        port = 4443 + server_label_int
        
        # Get proxy URL
        proxy_url = proxy_api.get_protonvpn_proxy_with_port(domain, port)
        return proxy_url
    except Exception:
        return None

def trigger_health_check():
    """Trigger health check for all services"""
    try:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cmd = f'bash monitor_gost.sh'
        result = run_command(cmd, cwd=BASE_DIR)
        return result['success']
    except Exception:
        return False
