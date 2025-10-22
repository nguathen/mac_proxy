#!/usr/bin/env python3
"""
HAProxy & Wireproxy Web UI
Quản lý HAProxy và Wireproxy qua giao diện web
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
import subprocess
import os
import re
import json
import sys
import requests
from datetime import datetime
import concurrent.futures

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nordvpn_api import NordVPNAPI
from protonvpn_api import ProtonVPNAPI
from proxy_api import proxy_api

app = Flask(__name__)
app.config['SECRET_KEY'] = 'haproxy-webui-secret-key-2025'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WG1_CONF = os.path.join(BASE_DIR, 'wg18181.conf')
WG2_CONF = os.path.join(BASE_DIR, 'wg18182.conf')
LOG_DIR = os.path.join(BASE_DIR, 'logs')

# Initialize NordVPN API
nordvpn_api = NordVPNAPI(os.path.join(BASE_DIR, 'nordvpn_servers_cache.json'))

# Initialize ProtonVPN API
# Try to load credentials from file
protonvpn_api = None
protonvpn_credentials_file = os.path.join(BASE_DIR, 'protonvpn_credentials.json')
if os.path.exists(protonvpn_credentials_file):
    try:
        with open(protonvpn_credentials_file, 'r') as f:
            creds = json.load(f)
            bearer_token = creds.get('bearer_token', '')
            uid = creds.get('uid', '')
            if bearer_token and uid:
                protonvpn_api = ProtonVPNAPI(
                    cache_file=os.path.join(BASE_DIR, 'protonvpn_servers_cache.json'),
                    bearer_token=bearer_token,
                    uid=uid
                )
    except Exception:
        pass

def run_command(cmd, cwd=BASE_DIR):
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
    config_dir = os.path.join(BASE_DIR, 'config')
    if os.path.exists(config_dir):
        for filename in os.listdir(config_dir):
            if filename.startswith('haproxy_') and filename.endswith('.cfg'):
                try:
                    port = filename.replace('haproxy_', '').replace('.cfg', '')
                    haproxy_ports.add(port)
                except (ValueError, IndexError):
                    pass
    
    # Scan PID files for running processes
    if os.path.exists(LOG_DIR):
        for filename in os.listdir(LOG_DIR):
            if filename.startswith('haproxy_') and filename.endswith('.pid'):
                try:
                    port = filename.replace('haproxy_', '').replace('.pid', '')
                    haproxy_ports.add(port)
                except (ValueError, IndexError):
                    pass
    
    return sorted(list(haproxy_ports))

def get_available_gost_ports():
    """Dynamically scan for available gost ports from config files"""
    gost_ports = set()
    
    # Scan config files in config/ directory
    config_dir = os.path.join(BASE_DIR, 'config')
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
                    import re
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

def get_protonvpn_proxy_with_server(server):
    """Get ProtonVPN proxy URL with correct port based on server label"""
    try:
        # Calculate port based on server label
        # Get label from servers array
        server_label = '0'  # Default
        if server.get('servers') and len(server['servers']) > 0:
            server_label = server['servers'][0].get('label', '0')
        
        try:
            server_label_int = int(server_label)
        except (ValueError, TypeError):
            server_label_int = 0  # Fallback to 0
        
        protonvpn_port = server_label_int + 4443
        
        # Get proxy URL with correct port
        return proxy_api.get_protonvpn_proxy_with_port(server.get('domain', server.get('name', '')), protonvpn_port)
    except Exception as e:
        print(f"⚠️  Error getting ProtonVPN proxy with server: {e}")
        return None

def trigger_health_check():
    """Trigger HAProxy health monitors to check immediately by creating trigger file"""
    try:
        # Create trigger files for health monitors
        available_ports = get_available_haproxy_ports()
        for port in available_ports:
            trigger_file = os.path.join(LOG_DIR, f'trigger_check_{port}')
            try:
                with open(trigger_file, 'w') as f:
                    f.write('1')
            except Exception:
                pass
    except Exception:
        pass

@app.route('/')
def index():
    """Trang chủ"""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """Lấy trạng thái tất cả services"""
    status = {
        'gost': [],
        'haproxy': [],
        'timestamp': datetime.now().isoformat()
    }
    
    # Check gost services - include services that have been created or are running
    gost_services = {}
    
    # Check for port-based config files (gost_PORT.config) - use dynamic discovery
    available_ports = get_available_gost_ports()
    for port in available_ports:
        config_file = os.path.join(BASE_DIR, 'config', f'gost_{port}.config')
        pid_file = os.path.join(LOG_DIR, f'gost_{port}.pid')
        
        # Include service if it has config file, pid file, or is running on port
        if (os.path.exists(config_file) or 
            os.path.exists(pid_file) or 
            run_command(f'lsof -ti :{port}')['success']):
            gost_services[port] = port
    
    # Check status for each gost service in parallel to avoid blocking
    def _probe_gost(port):
        running = False
        pid = None
        proxy_url = ""
        
        # Use port-based file naming
        pid_file = os.path.join(LOG_DIR, f'gost_{port}.pid')
        
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                    os.kill(pid, 0)
                    running = True
            except (OSError, ValueError):
                try:
                    os.remove(pid_file)
                except Exception:
                    pass
        
        if not running:
            result = run_command(f'lsof -ti :{port}')
            if result['success'] and result['stdout'].strip():
                try:
                    pid = int(result['stdout'].strip().split('\n')[0])
                    check = run_command(f'ps -p {pid} -o command=')
                    if check['success'] and 'gost' in check['stdout']:
                        running = True
                        try:
                            with open(pid_file, 'w') as f:
                                f.write(str(pid))
                        except Exception:
                            pass
                        # Extract proxy URL from command
                        import re
                        match = re.search(r'-F\s+([^\s]+)', check['stdout'])
                        if match:
                            proxy_url = match.group(1)
                except (ValueError, IndexError):
                    pass
        
        # Try to get proxy URL from config file if not found in command
        if not proxy_url:
            # Try new format config file first
            config_file = os.path.join(BASE_DIR, 'config', f'gost_{port}.config')
            if not os.path.exists(config_file):
                # Fallback to old format
                config_file = os.path.join(BASE_DIR, 'config', f'gost_{port}.config')
            
            if os.path.exists(config_file):
                try:
                    with open(config_file, 'r') as f:
                        import json
                        config = json.load(f)
                        proxy_url = config.get('proxy_url', '')
                except Exception:
                    pass
        
        connection_ok = False
        if running:
            result = run_command(f'curl -s --max-time 2 -x socks5h://127.0.0.1:{port} https://api.ipify.org')
            connection_ok = bool(result['success'] and result['stdout'].strip())
        
        # Parse server:port from proxy_url
        server_info = ""
        if proxy_url:
            try:
                # Extract server and port from proxy URL
                import re
                # Match patterns like https://user:pass@server:port or socks5://server:port
                match = re.search(r'@([^:]+):(\d+)', proxy_url)
                if match:
                    server = match.group(1)
                    server_port = match.group(2)
                    server_info = f"{server}:{server_port}"
                else:
                    # Try to extract from other patterns
                    match = re.search(r'://([^:]+):(\d+)', proxy_url)
                    if match:
                        server = match.group(1)
                        server_port = match.group(2)
                        server_info = f"{server}:{server_port}"
            except Exception:
                pass
        
        return {
            'name': f'Port {port}',
            'port': port,
            'running': running,
            'pid': pid,
            'connection': connection_ok,
            'proxy_url': proxy_url,
            'server_info': server_info
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(gost_services)))) as executor:
        results = list(executor.map(_probe_gost, gost_services.keys()))
    status['gost'].extend(results)
    
    # Check HAProxy - scan all config files and running processes
    haproxy_ports = set()
    
    # Get ports from config files
    config_dir = os.path.join(BASE_DIR, 'config')
    if os.path.exists(config_dir):
        for filename in os.listdir(config_dir):
            if filename.startswith('haproxy_') and filename.endswith('.cfg'):
                port = filename.replace('haproxy_', '').replace('.cfg', '')
                haproxy_ports.add(port)
    
    # Get ports from PID files (running processes)
    if os.path.exists(LOG_DIR):
        for filename in os.listdir(LOG_DIR):
            if filename.startswith('haproxy_') and filename.endswith('.pid'):
                port = filename.replace('haproxy_', '').replace('.pid', '')
                haproxy_ports.add(port)
    
    # Check status for each port
    for port in sorted(haproxy_ports):
        pid_file = os.path.join(LOG_DIR, f'haproxy_{port}.pid')
        running = False
        pid = None
        wireproxy_port = None
        
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                    os.kill(pid, 0)
                    running = True
            except (OSError, ValueError):
                pass
        
        # Get gost backend port from HAProxy config
        haproxy_config = os.path.join(BASE_DIR, 'config', f'haproxy_{port}.cfg')
        if os.path.exists(haproxy_config):
            try:
                with open(haproxy_config, 'r') as f:
                    content = f.read()
                    import re
                    # Look for gost backend servers
                    match = re.search(r'server\s+gost\d+\s+127\.0\.0\.1:(\d+)', content)
                    if match:
                        wireproxy_port = match.group(1)
                    else:
                        # Fallback to old wireproxy format
                        match = re.search(r'server\s+wg\d+\s+127\.0\.0\.1:(\d+)', content)
                        if match:
                            wireproxy_port = match.group(1)
            except Exception:
                pass
        
        # Calculate stats port
        try:
            stats_port = int(port) + 200
        except ValueError:
            stats_port = 8091
        
        status['haproxy'].append({
            'name': f'HAProxy {port}',
            'port': port,
            'running': running,
            'pid': pid,
            'wireproxy_port': wireproxy_port,
            'gost_backend': wireproxy_port,  # Show gost backend port
            'stats_url': f'http://127.0.0.1:{stats_port}/haproxy?stats'
        })
    
    
    return jsonify(status)

@app.route('/api/gost/config/<port>')
def api_get_gost_config(port):
    """Lấy config gost theo port"""
    # Validate port
    if port not in ['18181', '18182', '18183', '18184', '18185', '18186', '18187']:
        return jsonify({
            'success': False, 
            'error': f'Invalid port. Available ports: 18181-18187'
        }), 400
    
    config = parse_gost_config(port)
    if config:
        return jsonify({'success': True, 'config': config})
    else:
        return jsonify({'success': False, 'error': 'Cannot read config'}), 500

@app.route('/api/gost/config/<port>', methods=['POST'])
def api_save_gost_config(port):
    """Lưu config gost theo port"""
    data = request.json
    
    # Validate port
    if port not in ['18181', '18182', '18183', '18184', '18185', '18186', '18187']:
        return jsonify({
            'success': False, 
            'error': f'Invalid port. Available ports: 18181-18187'
        }), 400
    
    config = data.get('config')
    if not config:
        return jsonify({'success': False, 'error': 'No config provided'}), 400
    
    if save_gost_config(port, config):
        return jsonify({'success': True, 'message': 'Config saved successfully'})
    else:
        return jsonify({'success': False, 'error': 'Cannot save config'}), 500

@app.route('/api/gost/<action>', methods=['POST'])
def api_gost_action(action):
    """Điều khiển gost (start/stop/restart)"""
    if action not in ['start', 'stop', 'restart']:
        return jsonify({'success': False, 'error': 'Invalid action'}), 400
    
    result = run_command(f'bash manage_gost.sh {action}')
    
    return jsonify({
        'success': result['success'],
        'output': result['stdout'],
        'error': result['stderr']
    })

@app.route('/api/gost/<port>/<action>', methods=['POST'])
def api_gost_port_action(port, action):
    """Điều khiển gost theo port"""
    if action not in ['start', 'stop', 'restart']:
        return jsonify({'success': False, 'error': 'Invalid action'}), 400
    
    # Validate port
    if not is_valid_gost_port(port):
        return jsonify({
            'success': False, 
            'error': f'Invalid port: {port}'
        }), 400
    
    # Use port-based file naming
    pid_file = os.path.join(LOG_DIR, f'gost_{port}.pid')
    
    if action == 'stop':
        # Stop gost service
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, 15)  # SIGTERM
                try:
                    os.remove(pid_file)
                except Exception:
                    pass
                return jsonify({
                    'success': True,
                    'message': f'Gost on port {port} stopped successfully'
                })
            except (OSError, ValueError) as e:
                return jsonify({
                    'success': False,
                    'error': f'Failed to stop: {str(e)}'
                }), 500
        else:
            return jsonify({
                'success': False,
                'error': 'Gost not running'
            }), 400
    
    elif action == 'start':
        # Check if already running
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)  # Check if process exists
                return jsonify({
                    'success': False,
                    'error': 'Gost already running'
                }), 400
            except OSError:
                try:
                    os.remove(pid_file)
                except Exception:
                    pass
        
        # Kill any process on the port
        run_command(f'lsof -ti :{port} | xargs -r kill -9 2>/dev/null || true')
        
        # Get proxy URL from config
        config = parse_gost_config(port)
        proxy_url = config.get('proxy_url', '') if config else ''
        
        # If no proxy URL or empty, try to create random config
        if not proxy_url or proxy_url == '':
            try:
                import random
                # Try ProtonVPN first
                servers = protonvpn_api.fetch_servers() if protonvpn_api else []
                if servers:
                    selected_server = random.choice(servers)
                    server_name = selected_server.get('domain', selected_server.get('name', ''))
                    proxy_url = proxy_api.get_protonvpn_proxy(server_name)
                    
                    # Save the random config
                    if proxy_url:
                        random_config = {
                            'provider': 'protonvpn',
                            'country': server_name,
                            'proxy_url': proxy_url
                        }
                        save_gost_config(port, random_config)
                        print(f"✅ Created random ProtonVPN config for gost port {port}: {server_name}")
                
                # If ProtonVPN failed, try NordVPN
                if not proxy_url:
                    servers = nordvpn_api.fetch_servers() if nordvpn_api else []
                    if servers:
                        selected_server = random.choice(servers)
                        server_name = selected_server.get('hostname', selected_server.get('name', ''))
                        proxy_url = proxy_api.get_nordvpn_proxy(server_name)
                        
                        # Save the random config
                        if proxy_url:
                            random_config = {
                                'provider': 'nordvpn',
                                'country': server_name,
                                'proxy_url': proxy_url
                            }
                            save_gost_config(port, random_config)
                            print(f"✅ Created random NordVPN config for gost port {port}: {server_name}")
                
            except Exception as e:
                print(f"⚠️  Failed to create random config for gost port {port}: {e}")
        
        # Fallback to default if still no proxy URL
        if not proxy_url:
            proxy_url = 'https://user:pass@az-01.protonvpn.net:4465'
        
        # Start gost
        log_file = os.path.join(LOG_DIR, f'gost_{port}.log')
        cmd = f'nohup gost -L socks5://:{port} -F "{proxy_url}" > {log_file} 2>&1 & echo $!'
        result = run_command(cmd)
        
        if result['success']:
            pid = result['stdout'].strip()
            try:
                with open(pid_file, 'w') as f:
                    f.write(pid)
            except Exception:
                pass
            
            # Trigger health monitor to check immediately
            trigger_health_check()
            
            return jsonify({
                'success': True,
                'message': f'Gost port {port} started successfully',
                'pid': pid
            })
        else:
            return jsonify({
                'success': False,
                'error': result['stderr']
            }), 500
    
    elif action == 'restart':
        # Stop then start
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, 15)
                try:
                    os.remove(pid_file)
                except Exception:
                    pass
            except (OSError, ValueError):
                pass
        
        import time
        time.sleep(1)
        
        # Kill any process on the port
        run_command(f'lsof -ti :{port} | xargs -r kill -9 2>/dev/null || true')
        time.sleep(1)
        
        # Get proxy URL from config
        config = parse_gost_config(port)
        proxy_url = config.get('proxy_url', '') if config else ''
        
        # If no proxy URL or empty, try to create random config
        if not proxy_url or proxy_url == '':
            try:
                import random
                # Try ProtonVPN first
                servers = protonvpn_api.fetch_servers() if protonvpn_api else []
                if servers:
                    selected_server = random.choice(servers)
                    server_name = selected_server.get('domain', selected_server.get('name', ''))
                    proxy_url = proxy_api.get_protonvpn_proxy(server_name)
                    
                    # Save the random config
                    if proxy_url:
                        random_config = {
                            'provider': 'protonvpn',
                            'country': server_name,
                            'proxy_url': proxy_url
                        }
                        save_gost_config(port, random_config)
                        print(f"✅ Created random ProtonVPN config for gost port {port}: {server_name}")
                
                # If ProtonVPN failed, try NordVPN
                if not proxy_url:
                    servers = nordvpn_api.fetch_servers() if nordvpn_api else []
                    if servers:
                        selected_server = random.choice(servers)
                        server_name = selected_server.get('hostname', selected_server.get('name', ''))
                        proxy_url = proxy_api.get_nordvpn_proxy(server_name)
                        
                        # Save the random config
                        if proxy_url:
                            random_config = {
                                'provider': 'nordvpn',
                                'country': server_name,
                                'proxy_url': proxy_url
                            }
                            save_gost_config(port, random_config)
                            print(f"✅ Created random NordVPN config for gost port {port}: {server_name}")
                
            except Exception as e:
                print(f"⚠️  Failed to create random config for gost port {port}: {e}")
        
        # Fallback to default if still no proxy URL
        if not proxy_url:
            proxy_url = 'https://user:pass@az-01.protonvpn.net:4465'
        
        # Start gost
        log_file = os.path.join(LOG_DIR, f'gost_{port}.log')
        cmd = f'nohup gost -L socks5://:{port} -F "{proxy_url}" > {log_file} 2>&1 & echo $!'
        result = run_command(cmd)
        
        if result['success']:
            pid = result['stdout'].strip()
            with open(pid_file, 'w') as f:
                f.write(pid)
            
            # Trigger health monitor to check immediately
            trigger_health_check()
            
            return jsonify({
                'success': True,
                'message': f'Gost port {port} restarted successfully',
                'pid': pid
            })
        else:
            return jsonify({
                'success': False,
                'error': result['stderr']
            }), 500

@app.route('/api/haproxy/list')
def api_haproxy_list():
    """Lấy danh sách tất cả HAProxy services"""
    try:
        config_dir = os.path.join(BASE_DIR, 'config')
        services = []
        
        if os.path.exists(config_dir):
            for filename in os.listdir(config_dir):
                if filename.startswith('haproxy_') and filename.endswith('.cfg'):
                    port = filename.replace('haproxy_', '').replace('.cfg', '')
                    config_path = os.path.join(config_dir, filename)
                    
                    # Parse config to get stats port
                    stats_port = None
                    try:
                        with open(config_path, 'r') as f:
                            for line in f:
                                if 'listen stats_' in line:
                                    stats_port = line.split('stats_')[1].strip()
                                elif 'bind 0.0.0.0:' in line and stats_port is None:
                                    # Get stats port from bind line
                                    match = re.search(r'bind 0.0.0.0:(\d+)', line)
                                    if match and 'listen stats_' in open(config_path).read():
                                        pass
                                elif 'bind 0.0.0.0:' in line and 'listen stats_' in open(config_path).read():
                                    # Find the stats bind port
                                    content = open(config_path).read()
                                    match = re.search(r'listen stats_\d+\s+bind 0\.0\.0\.0:(\d+)', content)
                                    if match:
                                        stats_port = match.group(1)
                                        break
                    except Exception:
                        pass
                    
                    # Get stats port from config properly
                    if not stats_port:
                        try:
                            with open(config_path, 'r') as f:
                                content = f.read()
                                match = re.search(r'listen stats_\d+\s+bind 0\.0\.0\.0:(\d+)', content)
                                if match:
                                    stats_port = match.group(1)
                        except Exception:
                            pass
                    
                    services.append({
                        'port': port,
                        'stats_port': stats_port,
                        'config_file': filename
                    })
        
        return jsonify({
            'success': True,
            'services': services
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/haproxy/create', methods=['POST'])
def api_haproxy_create():
    """Tạo HAProxy service mới"""
    try:
        data = request.json
        sock_port = data.get('sock_port')
        stats_port = data.get('stats_port')
        wg_ports = data.get('wg_ports', [])
        
        if not sock_port:
            return jsonify({
                'success': False,
                'error': 'sock_port is required'
            }), 400
        
        # Validate and auto-calculate stats_port
        try:
            sock_port = int(sock_port)
            if sock_port < 1024 or sock_port > 65535:
                raise ValueError("Port out of range")
            
            # Auto-calculate stats_port if not provided
            if not stats_port:
                stats_port = sock_port + 200
            else:
                stats_port = int(stats_port)
                if stats_port < 1024 or stats_port > 65535:
                    raise ValueError("Stats port out of range")
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid port numbers: {str(e)}'
            }), 400
        
        # Check if service already exists (check both config file and running process)
        config_dir = os.path.join(BASE_DIR, 'config')
        config_file = os.path.join(config_dir, f'haproxy_{sock_port}.cfg')
        pid_file = os.path.join(LOG_DIR, f'haproxy_{sock_port}.pid')
        
        # Check config file
        if os.path.exists(config_file):
            return jsonify({
                'success': False,
                'error': f'HAProxy service on port {sock_port} already exists (config file found)'
            }), 400
        
        # Check if process is running
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)  # Check if process exists
                return jsonify({
                    'success': False,
                    'error': f'HAProxy service on port {sock_port} is already running (PID: {pid}). Please stop it first.'
                }), 400
            except (OSError, ValueError):
                # PID file exists but process not running, clean up
                try:
                    os.remove(pid_file)
                except:
                    pass
        
        # Create config directory if not exists
        os.makedirs(config_dir, exist_ok=True)
        
        # Auto-create Gost config files for ports that don't exist
        if wg_ports:
            for port in wg_ports:
                gost_config_file = os.path.join(BASE_DIR, 'config', f'gost_{port}.config')
                if not os.path.exists(gost_config_file):
                    # Create default Gost config with Cloudflare WARP fallback
                    default_config = {
                        "port": str(port),
                        "provider": "protonvpn",
                        "country": "node-uk-29.protonvpn.net",
                        "proxy_url": "socks5://127.0.0.1:8111",
                        "created_at": datetime.now().isoformat()
                    }
                    try:
                        import json
                        with open(gost_config_file, 'w') as f:
                            json.dump(default_config, f, indent=4)
                    except Exception as e:
                        # Log error but continue
                        pass
        
        # Build Gost servers config
        gost_servers = ""
        if wg_ports:
            for i, port in enumerate(wg_ports, 1):
                if i == 1:
                    gost_servers += f"    server gost{i} 127.0.0.1:{port} check inter 1s rise 1 fall 2 on-error fastinter\n"
                else:
                    gost_servers += f"    server gost{i} 127.0.0.1:{port} check inter 1s rise 1 fall 2 on-error fastinter backup\n"
        
        # Create HAProxy config
        config_content = f"""global
    log stdout format raw local0
    maxconn 4096
    pidfile ./logs/haproxy_{sock_port}.pid
    daemon

defaults
    mode tcp
    timeout connect 2s
    timeout client 1m
    timeout server 1m
    timeout check 2s
    retries 2
    option redispatch
    option tcplog
    log global

frontend socks_front_{sock_port}
    bind 0.0.0.0:{sock_port}
    default_backend socks_back_{sock_port}

backend socks_back_{sock_port}
    balance first
    option tcp-check
    tcp-check connect
{gost_servers}    server cloudflare_warp 127.0.0.1:8111 check inter 1s rise 1 fall 2 on-error fastinter backup

listen stats_{sock_port}
    bind 0.0.0.0:{stats_port}
    mode http
    stats enable
    stats uri /haproxy?stats
    stats refresh 2s
    stats show-legends
    stats show-desc HAProxy Instance - SOCKS:{sock_port}
    stats auth admin:admin123
"""
        
        # Write config file
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        # Calculate corresponding gost port dynamically
        # Find available gost ports and map to HAProxy port
        available_gost_ports = get_available_gost_ports()
        if available_gost_ports:
            # Use first available gost port or calculate based on HAProxy port
            gost_port = int(available_gost_ports[0]) if len(available_gost_ports) == 1 else 18181 + (sock_port - 7891)
        else:
            gost_port = 18181 + (sock_port - 7891)
        
        # Create gost config with random server if no specific country
        gost_config_created = False
        if 18181 <= gost_port <= 18999:  # Valid gost port range
            try:
                # Try to get random server from ProtonVPN first
                import random
                servers = protonvpn_api.fetch_servers() if protonvpn_api else []
                if servers:
                    selected_server = random.choice(servers)
                    server_name = selected_server.get('domain', selected_server.get('name', ''))
                    
                    # Create gost config
                    config = {
                        'provider': 'protonvpn',
                        'country': server_name,
                        'proxy_url': proxy_api.get_protonvpn_proxy(server_name)  # Random server, use old method
                    }
                    
                    if save_gost_config(str(gost_port), config):
                        gost_config_created = True
                        print(f"✅ Created gost config for port {gost_port} with random ProtonVPN server: {server_name}")
                
                # If ProtonVPN failed, try NordVPN
                if not gost_config_created:
                    servers = nordvpn_api.fetch_servers() if nordvpn_api else []
                    if servers:
                        selected_server = random.choice(servers)
                        server_name = selected_server.get('hostname', selected_server.get('name', ''))
                        
                        # Create gost config
                        config = {
                            'provider': 'nordvpn',
                            'country': server_name,
                            'proxy_url': proxy_api.get_nordvpn_proxy(server_name)
                        }
                        
                        if save_gost_config(str(gost_port), config):
                            gost_config_created = True
                            print(f"✅ Created gost config for port {gost_port} with random NordVPN server: {server_name}")
                
            except Exception as e:
                print(f"⚠️  Failed to create gost config: {e}")
        
        # Start Gost services for the backend ports
        if wg_ports:
            for port in wg_ports:
                # Start gost service for this port
                gost_cmd = f'bash manage_gost.sh restart-port {port}'
                gost_result = run_command(gost_cmd)
                if gost_result['success']:
                    print(f"✅ Started gost service on port {port}")
                else:
                    print(f"⚠️  Failed to start gost service on port {port}: {gost_result['stderr']}")
        
        # Start the HAProxy service using setup_haproxy.sh in background
        wg_ports_str = ','.join(map(str, wg_ports)) if wg_ports else '18181'
        log_file = os.path.join(LOG_DIR, f'haproxy_health_{sock_port}.log')
        
        # Run setup_haproxy.sh in background using nohup
        cmd = f'nohup bash setup_haproxy.sh --sock-port {sock_port} --stats-port {stats_port} --gost-ports {wg_ports_str} --daemon > {log_file} 2>&1 &'
        result = run_command(cmd)
        
        if result['success'] or result['returncode'] == 0:
            # Give it a moment to start
            import time
            time.sleep(2)
            
            # Start gost service if config was created
            if gost_config_created and 18181 <= gost_port <= 18999:
                try:
                    # Start gost service using manage_gost.sh
                    gost_cmd = f'./manage_gost.sh start'
                    gost_result = run_command(gost_cmd)
                    if gost_result['success']:
                        print(f"✅ Started gost service on port {gost_port}")
                    else:
                        print(f"⚠️  Failed to start gost service on port {gost_port}: {gost_result.get('stderr', 'Unknown error')}")
                except Exception as e:
                    print(f"⚠️  Error starting gost service on port {gost_port}: {e}")
            
            # Verify HAProxy started
            pid_file = os.path.join(LOG_DIR, f'haproxy_{sock_port}.pid')
            if os.path.exists(pid_file):
                try:
                    with open(pid_file) as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 0)  # Check if process exists
                    
                    message = f'HAProxy service created on port {sock_port}'
                    if gost_config_created:
                        message += f' with gost service on port {gost_port}'
                    
                    return jsonify({
                        'success': True,
                        'message': message,
                        'service': {
                            'sock_port': sock_port,
                            'stats_port': stats_port,
                            'wg_ports': wg_ports,
                            'gost_port': gost_port if gost_config_created else None
                        }
                    })
                except (OSError, ValueError):
                    pass
            
            # If we can't verify, assume it's starting
            return jsonify({
                'success': True,
                'message': f'HAProxy service created on port {sock_port} (starting...)',
                'service': {
                    'sock_port': sock_port,
                    'stats_port': stats_port,
                    'wg_ports': wg_ports
                }
            })
        else:
            # Clean up config file if start failed
            try:
                os.remove(config_file)
            except:
                pass
            
            return jsonify({
                'success': False,
                'error': f'Failed to start HAProxy: {result["stderr"]}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/haproxy/delete/<port>', methods=['DELETE'])
def api_haproxy_delete(port):
    """Xóa HAProxy service"""
    try:
        # Stop the service first
        pid_file = os.path.join(LOG_DIR, f'haproxy_{port}.pid')
        health_pid_file = os.path.join(LOG_DIR, f'health_{port}.pid')
        
        # Stop HAProxy process
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                # Check if process is still running
                try:
                    os.kill(pid, 0)  # Check if process exists
                    os.kill(pid, 15)  # SIGTERM
                    print(f"✅ Stopped HAProxy process {pid}")
                except OSError:
                    print(f"⚠️  HAProxy process {pid} not running, removing stale PID file")
                os.remove(pid_file)
            except (OSError, ValueError) as e:
                print(f"⚠️  Error handling HAProxy PID file: {e}")
                # Remove stale PID file
                try:
                    os.remove(pid_file)
                except:
                    pass
        
        # Stop health monitor
        if os.path.exists(health_pid_file):
            try:
                with open(health_pid_file) as f:
                    pid = int(f.read().strip())
                # Check if process is still running
                try:
                    os.kill(pid, 0)  # Check if process exists
                    os.kill(pid, 15)  # SIGTERM
                    print(f"✅ Stopped health monitor process {pid}")
                except OSError:
                    print(f"⚠️  Health monitor process {pid} not running, removing stale PID file")
                os.remove(health_pid_file)
            except (OSError, ValueError) as e:
                print(f"⚠️  Error handling health monitor PID file: {e}")
                # Remove stale PID file
                try:
                    os.remove(health_pid_file)
                except:
                    pass
        
        # Kill any process still running on the port
        result = run_command(f'lsof -ti :{port}')
        if result['success'] and result['stdout'].strip():
            pids = result['stdout'].strip().split('\n')
            for pid in pids:
                if pid.strip():
                    try:
                        run_command(f'kill -9 {pid.strip()}')
                        print(f"✅ Killed process {pid.strip()} on port {port}")
                    except:
                        pass
        
        # Remove config file
        config_file = os.path.join(BASE_DIR, 'config', f'haproxy_{port}.cfg')
        if os.path.exists(config_file):
            os.remove(config_file)
            print(f"✅ Removed config file: {config_file}")
        
        # Clean up log files
        log_file = os.path.join(LOG_DIR, f'haproxy_health_{port}.log')
        if os.path.exists(log_file):
            os.remove(log_file)
        
        last_backend_file = os.path.join(LOG_DIR, f'last_backend_{port}')
        if os.path.exists(last_backend_file):
            os.remove(last_backend_file)
        
        return jsonify({
            'success': True,
            'message': f'HAProxy service on port {port} deleted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/gost/delete/<port>', methods=['DELETE'])
def api_gost_delete(port):
    """Xóa Gost theo port"""
    try:
        # Validate port using dynamic port discovery
        available_ports = get_available_gost_ports()
        if port not in available_ports:
            return jsonify({
                'success': False, 
                'error': f'Invalid port. Available ports: {", ".join(available_ports)}'
            }), 400
        
        # Stop the service first if running
        pid_file = os.path.join(LOG_DIR, f'gost_{port}.pid')
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, 15)  # SIGTERM
                os.remove(pid_file)
            except (OSError, ValueError):
                pass
        
        # Kill any process on the port
        run_command(f'lsof -ti :{port} | xargs kill -9 2>/dev/null || true')
        
        # Remove config file
        config_file = os.path.join(BASE_DIR, 'config', f'gost_{port}.config')
        if os.path.exists(config_file):
            os.remove(config_file)
        
        # Clean up log files
        log_file = os.path.join(LOG_DIR, f'gost_{port}.log')
        if os.path.exists(log_file):
            os.remove(log_file)
        
        return jsonify({
            'success': True,
            'message': f'Gost port {port} deleted successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/haproxy/<action>', methods=['POST'])
def api_haproxy_action(action):
    """Điều khiển HAProxy (start/stop/restart)"""
    if action == 'start':
        result = run_command('bash start_haproxy_adaptive.sh')
    elif action == 'stop':
        result = run_command('bash stop_haproxy_only.sh')
    elif action == 'restart':
        result = run_command('bash stop_haproxy_only.sh && sleep 2 && bash start_haproxy_adaptive.sh')
    else:
        return jsonify({'success': False, 'error': 'Invalid action'}), 400
    
    return jsonify({
        'success': result['success'],
        'output': result['stdout'],
        'error': result['stderr']
    })


@app.route('/api/logs/<service>')
def api_get_logs(service):
    """Lấy logs"""
    # Dynamic log file mapping
    log_file = None
    
    # Check for gost logs (gost_PORT or gost1, gost2, etc.)
    if service.startswith('gost'):
        # Extract port from service name
        port_or_instance = service.replace('gost', '')
        if port_or_instance.isdigit():
            # Check if it's a port (4+ digits) or instance (1-2 digits)
            if len(port_or_instance) >= 4:  # Port like 18181, 18182
                log_file = f'gost_{port_or_instance}.log'
            else:  # Instance like 1, 2, 3 (legacy)
                log_file = f'gost{port_or_instance}.log'
        else:
            return jsonify({'success': False, 'error': 'Invalid gost service'}), 400
    # Check for wireproxy logs (legacy support)
    elif service.startswith('wireproxy'):
        # Extract port number from service name (e.g., wireproxy18183 -> 18183)
        port = service.replace('wireproxy', '')
        # Use port-based file naming
        new_log_file = f'wireproxy_{port}.log'
        old_log_file = f'wireproxy_{port}.log'
        
        # Prefer new format if it exists and is newer
        if os.path.exists(os.path.join(LOG_DIR, new_log_file)):
            if os.path.exists(os.path.join(LOG_DIR, old_log_file)):
                # Compare modification times
                new_time = os.path.getmtime(os.path.join(LOG_DIR, new_log_file))
                old_time = os.path.getmtime(os.path.join(LOG_DIR, old_log_file))
                if new_time > old_time:
                    log_file = new_log_file
                else:
                    log_file = old_log_file
            else:
                log_file = new_log_file
        elif os.path.exists(os.path.join(LOG_DIR, old_log_file)):
            log_file = old_log_file
        else:
            log_file = new_log_file  # Default to new format
    # Check for haproxy logs (haproxy1, haproxy2, ... or haproxy7891, haproxy7892, ...)
    elif service.startswith('haproxy'):
        # Extract port number
        port_or_instance = service.replace('haproxy', '')
        if port_or_instance.isdigit():
            # Check if it's a port (4 digits) or instance (1-2 digits)
            if len(port_or_instance) >= 4:  # Port like 7891, 7892, 7893
                port = port_or_instance
            else:  # Instance like 1, 2, 3
                # Use dynamic port discovery from config files
                available_ports = get_available_haproxy_ports()
                try:
                    instance_num = int(port_or_instance)
                    if 1 <= instance_num <= len(available_ports):
                        port = available_ports[instance_num - 1]  # 1-based indexing
                    else:
                        port = f'789{port_or_instance}'  # Fallback
                except (ValueError, IndexError):
                    port = f'789{port_or_instance}'  # Fallback
            log_file = f'haproxy_health_{port}.log'
    # Check for HTTPS proxy logs
    
    if not log_file:
        return jsonify({'success': False, 'error': 'Invalid service'}), 400
    
    log_path = os.path.join(LOG_DIR, log_file)
    
    if not os.path.exists(log_path):
        return jsonify({'success': True, 'logs': 'No logs available'})
    
    try:
        # Read last 100 lines
        result = run_command(f'tail -n 100 {log_path}')
        return jsonify({
            'success': True,
            'logs': result['stdout']
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/test/proxy/<port>')
def api_test_proxy(port):
    """Test proxy connection"""
    result = run_command(f'curl -s --max-time 5 -x socks5h://127.0.0.1:{port} https://api.ipify.org')
    
    if result['success']:
        ip = result['stdout'].strip()
        return jsonify({
            'success': True,
            'ip': ip,
            'message': f'Proxy working! IP: {ip}'
        })
    else:
        return jsonify({
            'success': False,
            'error': result['stderr'] or 'Connection failed'
        })

@app.route('/api/gost/reset-configs', methods=['POST'])
def api_reset_gost_configs():
    """Reset all gost configs to force different random servers"""
    try:
        import os
        import glob
        
        # Remove all gost config files from config/ directory
        config_dir = os.path.join(BASE_DIR, 'config')
        config_files = glob.glob(os.path.join(config_dir, 'gost*.config'))
        removed_count = 0
        
        for config_file in config_files:
            try:
                os.remove(config_file)
                removed_count += 1
            except Exception as e:
                print(f"⚠️  Failed to remove {config_file}: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Reset {removed_count} gost config files. Restart gost services to get new random servers.',
            'removed_count': removed_count
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/nordvpn/servers')
def api_nordvpn_servers():
    """Lấy danh sách server NordVPN"""
    try:
        force_refresh = request.args.get('refresh', 'false').lower() == 'true'
        servers = nordvpn_api.fetch_servers(force_refresh=force_refresh)
        
        return jsonify({
            'success': True,
            'servers': servers,
            'count': len(servers)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/nordvpn/countries')
def api_nordvpn_countries():
    """Lấy danh sách quốc gia"""
    try:
        countries = nordvpn_api.get_countries()
        
        return jsonify({
            'success': True,
            'countries': countries
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/nordvpn/servers/<country_code>')
def api_nordvpn_servers_by_country(country_code):
    """Lấy danh sách server theo quốc gia"""
    try:
        servers = nordvpn_api.get_servers_by_country(country_code)
        
        return jsonify({
            'success': True,
            'servers': servers,
            'count': len(servers)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/nordvpn/best')
def api_nordvpn_best_server():
    """Lấy server tốt nhất"""
    try:
        country_code = request.args.get('country')
        server = nordvpn_api.get_best_server(country_code)
        
        if server:
            return jsonify({
                'success': True,
                'server': server
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No server found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/nordvpn/apply/<port>', methods=['POST'])
def api_nordvpn_apply_server(port):
    """Áp dụng server NordVPN vào gost port"""
    try:
        data = request.json
        server_name = data.get('server_name')
        
        if not server_name:
            return jsonify({'success': False, 'error': 'No server name provided'}), 400
        
        # Get server info
        server = nordvpn_api.get_server_by_name(server_name)
        if not server:
            return jsonify({'success': False, 'error': 'Server not found'}), 404
        
        # Validate port
        if port not in ['18181', '18182', '18183', '18184', '18185', '18186', '18187']:
            return jsonify({
                'success': False, 
                'error': f'Invalid port. Available ports: 18181-18187'
            }), 400
        
        # Use port-based management
        
        # Get proxy URL for NordVPN server
        proxy_url = proxy_api.get_nordvpn_proxy(server['hostname'])
        if not proxy_url:
            return jsonify({
                'success': False,
                'error': 'Failed to generate proxy URL for NordVPN server'
            }), 500
        
        # Save gost config
        config = {
            'provider': 'nordvpn',
            'country': server['hostname'],
            'proxy_url': proxy_url
        }
        
        if not save_gost_config(port, config):
            return jsonify({
                'success': False,
                'error': 'Failed to save gost config'
            }), 500
        
        # Restart gost service using manage_gost.sh
        cmd = f'./manage_gost.sh restart-port {port}'
        result = run_command(cmd)
        
        if result['success']:
            # Trigger health monitor
            trigger_health_check()
            
            return jsonify({
                'success': True,
                'message': f'Applied NordVPN server {server["name"]} to Gost port {port}',
                'server': server,
                'port': port,
                'port': port,
                'proxy_url': proxy_url
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to restart Gost: {result["stderr"]}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/protonvpn/servers')
def api_protonvpn_servers():
    """Lấy danh sách ProtonVPN servers"""
    try:
        if not protonvpn_api:
            return jsonify({
                'success': False,
                'error': 'ProtonVPN API not configured. Please create protonvpn_credentials.json'
            }), 400
        
        force_refresh = request.args.get('refresh', 'false').lower() == 'true'
        servers = protonvpn_api.fetch_servers(force_refresh=force_refresh)
        
        return jsonify({
            'success': True,
            'servers': servers,
            'count': len(servers)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/protonvpn/countries')
def api_protonvpn_countries():
    """Lấy danh sách quốc gia"""
    try:
        if not protonvpn_api:
            return jsonify({
                'success': False,
                'error': 'ProtonVPN API not configured'
            }), 400
        
        countries = protonvpn_api.get_countries()
        return jsonify({
            'success': True,
            'countries': countries
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/protonvpn/servers/<country_code>')
def api_protonvpn_servers_by_country(country_code):
    """Lấy servers theo quốc gia"""
    try:
        if not protonvpn_api:
            return jsonify({
                'success': False,
                'error': 'ProtonVPN API not configured'
            }), 400
        
        servers = protonvpn_api.get_servers_by_country(country_code)
        
        return jsonify({
            'success': True,
            'servers': servers,
            'count': len(servers)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/protonvpn/best')
def api_protonvpn_best_server():
    """Lấy best server"""
    try:
        if not protonvpn_api:
            return jsonify({
                'success': False,
                'error': 'ProtonVPN API not configured'
            }), 400
        
        country_code = request.args.get('country')
        tier = request.args.get('tier', type=int)
        server = protonvpn_api.get_best_server(country_code, tier)
        
        if server:
            return jsonify({
                'success': True,
                'server': server
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No server found'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/protonvpn/apply/<port>', methods=['POST'])
def api_protonvpn_apply_server(port):
    """Áp dụng ProtonVPN server vào gost port"""
    try:
        if not protonvpn_api:
            return jsonify({'success': False, 'error': 'ProtonVPN API not configured'}), 400
        
        data = request.json
        server_name = data.get('server_name')
        
        if not server_name:
            return jsonify({'success': False, 'error': 'No server_name provided'}), 400
        
        # Get server info
        server = protonvpn_api.get_server_by_name(server_name)
        if not server:
            return jsonify({'success': False, 'error': 'Server not found'}), 404
        
        # Validate port
        if port not in ['18181', '18182', '18183', '18184', '18185', '18186', '18187']:
            return jsonify({
                'success': False, 
                'error': f'Invalid port. Available ports: 18181-18187'
            }), 400
        
        # Use port-based management
        
        # Calculate ProtonVPN port based on server label
        # Get label from servers array
        server_label = '0'  # Default
        if server.get('servers') and len(server['servers']) > 0:
            server_label = server['servers'][0].get('label', '0')
        
        try:
            server_label_int = int(server_label)
        except (ValueError, TypeError):
            server_label_int = 0  # Fallback to 0
        
        protonvpn_port = server_label_int + 4443
        
        # Get proxy URL for ProtonVPN server with correct port
        proxy_url = proxy_api.get_protonvpn_proxy_with_port(server['domain'], protonvpn_port)
        if not proxy_url:
            return jsonify({
                'success': False,
                'error': 'Failed to generate proxy URL for ProtonVPN server'
            }), 500
        
        # Save gost config
        config = {
            'provider': 'protonvpn',
            'country': server['domain'],
            'proxy_url': proxy_url,
            'port': str(protonvpn_port)
        }
        
        if not save_gost_config(port, config):
            return jsonify({
                'success': False,
                'error': 'Failed to save gost config'
            }), 500
        
        # Restart gost service using manage_gost.sh
        cmd = f'./manage_gost.sh restart-port {port}'
        result = run_command(cmd)
        
        if result['success']:
            # Trigger health monitor
            trigger_health_check()
            
            name = server.get('name', 'Unknown')
            return jsonify({
                'success': True,
                'message': f'Applied ProtonVPN {name} to Gost port {port}',
                'server': server,
                'port': port,
                'port': port,
                'proxy_url': proxy_url
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to restart Gost: {result["stderr"]}'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _get_proxy_port(server_name, vpn_provider):
    """Get actual proxy port based on VPN provider and server name"""
    if vpn_provider == 'nordvpn':
        return 89
    elif vpn_provider == 'protonvpn':
        # Extract server label from server name (e.g., us-ca-10 -> 10)
        try:
            server_label = server_name.split('-')[-1]
            return int(server_label) + 4443
        except:
            return 4443  # Default ProtonVPN port
    else:
        return 89  # Default

@app.route('/api/chrome/proxy-check', methods=['POST'])
def api_chrome_proxy_check():
    """
    API kiểm tra và tạo proxy cho Chrome profiles
    Input format: 
    {
      "proxy_check": "socks5://server:7891:vn42.nordvpn.com:",
      "data": {
        "count": 3,
        "profiles": [
          {"id": 1, "name": "Profile 1", "proxy": "127.0.0.1:7891:vn42.nordvpn.com"},
          {"id": 2, "name": "Profile 2", "proxy": null}
        ]
      }
    }
    """
    try:
        data = request.json
        proxy_check = data.get('proxy_check', '')
        profiles_data = data.get('data', {})
        profiles = profiles_data.get('profiles', [])
        
        # Parse proxy_check: "socks5://HOST:PORT:SERVER_NAME:"
        if not proxy_check or not proxy_check.startswith('socks5://'):
            return jsonify({
                'success': False,
                'error': 'Invalid proxy_check format. Expected: socks5://HOST:PORT:SERVER_NAME:'
            }), 400
        
        # Extract components from proxy_check
        proxy_parts = proxy_check.replace('socks5://', '').rstrip(':').split(':')
        if len(proxy_parts) < 3:
            return jsonify({
                'success': False,
                'error': 'Invalid proxy_check format. Expected: socks5://HOST:PORT:SERVER_NAME:'
            }), 400
        
        client_host = proxy_parts[0]  # Extract host from proxy_check
        check_port = proxy_parts[1]
        check_server = proxy_parts[2]
        
        # Determine VPN provider from server name
        if 'nordvpn' in check_server.lower():
            vpn_provider = 'nordvpn'
        elif 'protonvpn' in check_server.lower():
            vpn_provider = 'protonvpn'
        elif len(check_server) == 2:
            # For 2-character server names (country codes), random select VPN provider
            import random
            vpn_provider = random.choice(['nordvpn', 'protonvpn'])
        else:
            return jsonify({
                'success': False,
                'error': f'Unknown VPN provider from server name: {check_server}'
            }), 400
        
        # Check opened profiles
        port_in_use_by_other_server = False
        exact_match_found = False
        
        for profile in profiles:
            if profile.get('proxy'):
                proxy_str = profile['proxy']
                # Parse socks5://host:port:server format
                if proxy_str.startswith('socks5://'):
                    # Remove socks5:// prefix
                    proxy_str = proxy_str[9:]
                    parts = proxy_str.split(':')
                else:
                    # Parse: "127.0.0.1:PORT:SERVER_NAME" or "127.0.0.1:PORT"
                    parts = proxy_str.split(':')
                
                if len(parts) >= 2:
                    profile_port = parts[1]
                    profile_server = parts[2] if len(parts) >= 3 else ''
                    profile_proxy_port = parts[3] if len(parts) >= 4 else ''
                    
                    # Get expected proxy port for comparison
                    expected_proxy_port = str(_get_proxy_port(check_server, vpn_provider))
                    
                    # Case 1: Exact match - proxy_check matches existing profile (all 3 components)
                    if (profile_port == check_port and 
                        profile_server == check_server and 
                        profile_proxy_port == expected_proxy_port):
                        exact_match_found = True
                        break
                    
                    # Case 2: Same port but different server or proxy_port
                    if (profile_port == check_port and 
                        (profile_server != check_server or profile_proxy_port != expected_proxy_port)):
                        port_in_use_by_other_server = True
                        break
        
        # Case 1: Exact match found
        if exact_match_found:
            proxy_port = _get_proxy_port(check_server, vpn_provider)
            return f'socks5://{client_host}:{check_port}:{check_server}:{proxy_port}'
        
        # Case 2: Port in use with different server - try to reuse available HAProxy first
        if port_in_use_by_other_server:
            print(f"DEBUG: port_in_use_by_other_server = True")
            # First, try to find an available HAProxy that's not in the profiles list
            available_haproxy = _find_available_haproxy(profiles, check_server, vpn_provider)
            print(f"DEBUG: _find_available_haproxy returned: {available_haproxy}")
            if available_haproxy:
                # Use the actual server name from available HAProxy (in case of fallback)
                actual_server = available_haproxy.get('server', check_server)
                proxy_port = _get_proxy_port(actual_server, vpn_provider)
                print(f"DEBUG: Reusing HAProxy port {available_haproxy['port']}")
                return f'socks5://{client_host}:{available_haproxy["port"]}:{actual_server}:{proxy_port}'
            else:
                print("DEBUG: No available HAProxy found, will create new")
            
            # If no available HAProxy found, create new one
            # Find next available port by checking actual HAProxy configs
            existing_ports = set()
            
            # Check profiles first - parse both socks5:// and 127.0.0.1:port:server:proxy_port formats
            for profile in profiles:
                if profile.get('proxy'):
                    proxy = profile['proxy']
                    # Parse socks5://host:port:server format
                    if proxy.startswith('socks5://'):
                        # Remove socks5:// prefix
                        proxy = proxy[9:]
                        parts = proxy.split(':')
                    else:
                        # Parse 127.0.0.1:port:server:proxy_port format
                        parts = proxy.split(':')
                    
                    if len(parts) >= 2:
                        try:
                            port = int(parts[1])
                            existing_ports.add(port)
                        except ValueError:
                            pass
            
            # Check actual HAProxy config files
            import glob
            for cfg_file in glob.glob(os.path.join(BASE_DIR, 'config', 'haproxy_*.cfg')):
                try:
                    port = int(cfg_file.split('_')[-1].replace('.cfg', ''))
                    existing_ports.add(port)
                except (ValueError, IndexError):
                    pass
            
            # Find next available port dynamically
            available_ports = get_available_haproxy_ports()
            new_port = None
            
            # Try to find an available port starting from 7891
            for port in range(7891, 8000):  # Safety limit 7891-7999
                if port not in existing_ports and port != int(check_port):
                    new_port = port
                    break
            
            if new_port is None:
                return jsonify({
                    'success': False,
                    'error': 'No available ports (limit: 7891-7999)'
                }), 500
            
            # Verify the corresponding wireproxy port is also available
            expected_wireproxy_port = 18181 + (new_port - 7891)
            if expected_wireproxy_port > 18999:
                return jsonify({
                    'success': False,
                    'error': f'Wireproxy port {expected_wireproxy_port} exceeds limit (18999)'
                }), 500
            
            # Create new HAProxy service
            result = _create_haproxy_with_server(new_port, check_server, vpn_provider)
            if not result['success']:
                return jsonify({
                    'success': False,
                    'error': result['error']
                }), 500
            
            # Use the actual server name from result (in case of fallback)
            actual_server = result.get('server', check_server)
            proxy_port = _get_proxy_port(actual_server, vpn_provider)
            # Use the actual port from result (in case of fallback)
            actual_port = result.get('port', new_port)
            print(f"DEBUG: Creating new HAProxy port {actual_port}")
            return f'socks5://{client_host}:{actual_port}:{actual_server}:{proxy_port}'
        
        # Case 3: Port not in use - check if HAProxy exists and matches server
        haproxy_config = os.path.join(BASE_DIR, 'config', f'haproxy_{check_port}.cfg')
        
        if os.path.exists(haproxy_config):
            # Check if server matches
            current_server = _get_server_from_haproxy_config(haproxy_config)
            
            if current_server and current_server != check_server:
                # Server mismatch - only reconfigure if there are active profiles using this port
                # If no profiles are using this port (count=0, profiles=[]), just return the current server
                if len(profiles) == 0:
                    # No active profiles - reconfigure existing port to match requested server
                    result = _reconfigure_haproxy_with_server(check_port, check_server, vpn_provider)
                    if not result['success']:
                        return jsonify({
                            'success': False,
                            'error': result['error']
                        }), 500
                    
                    # Use the actual server name from result (in case of fallback)
                    actual_server = result.get('server', check_server)
                    return jsonify({
                        'success': True,
                        'proxy': f'socks5://{client_host}:{check_port}:{actual_server}:',
                        'action': 'reconfigure',
                        'port': check_port,
                        'server': actual_server
                    })
                else:
                    # Active profiles exist - reconfigure to match requested server
                    result = _reconfigure_haproxy_with_server(check_port, check_server, vpn_provider)
                    if not result['success']:
                        return jsonify({
                            'success': False,
                            'error': result['error']
                        }), 500
                    
                    # Use the actual server name from result (in case of fallback)
                    actual_server = result.get('server', check_server)
                    proxy_port = _get_proxy_port(actual_server, vpn_provider)
                    return f'socks5://{client_host}:{check_port}:{actual_server}:{proxy_port}'
            elif current_server == check_server:
                # Server matches - just return
                proxy_port = _get_proxy_port(check_server, vpn_provider)
                return f'socks5://{client_host}:{check_port}:{check_server}:{proxy_port}'
        
        # HAProxy doesn't exist - create new
        result = _create_haproxy_with_server(check_port, check_server, vpn_provider)
        if not result['success']:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
        
        # Use the actual server name from result (in case of fallback)
        actual_server = result.get('server', check_server)
        proxy_port = _get_proxy_port(actual_server, vpn_provider)
        return f'socks5://{client_host}:{check_port}:{actual_server}:{proxy_port}'
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _find_available_port_for_fallback(original_port):
    """Tìm port khả dụng cho fallback logic"""
    try:
        # Get existing ports
        existing_ports = set()
        
        # Check HAProxy config files
        import glob
        for cfg_file in glob.glob(os.path.join(BASE_DIR, 'config', 'haproxy_*.cfg')):
            try:
                port = int(cfg_file.split('_')[-1].replace('.cfg', ''))
                existing_ports.add(port)
            except (ValueError, IndexError):
                pass
        
        # Check PID files for running processes
        if os.path.exists(LOG_DIR):
            for filename in os.listdir(LOG_DIR):
                if filename.startswith('haproxy_') and filename.endswith('.pid'):
                    try:
                        port = int(filename.replace('haproxy_', '').replace('.pid', ''))
                        existing_ports.add(port)
                    except (ValueError, IndexError):
                        pass
        
        # Find next available port dynamically
        fallback_port = None
        
        # Try to find an available port starting from 7891
        for port in range(7891, 8000):  # Safety limit 7891-7999
            if port not in existing_ports and port != original_port:
                fallback_port = port
                break
        
        if fallback_port is None:
            return None
        
        # Verify the corresponding wireproxy port is also available
        expected_wireproxy_port = 18181 + (fallback_port - 7891)
        if expected_wireproxy_port > 18999:
            return None
        
        # Double check wireproxy port is not in use
        try:
            result = run_command(f'lsof -ti :{expected_wireproxy_port}')
            if result['success'] and result['stdout'].strip():
                # Port is in use, try next port
                return _find_available_port_for_fallback(fallback_port)
        except Exception:
            pass
            
        return fallback_port
        
    except Exception as e:
        return None

def _find_available_haproxy(profiles, target_server, vpn_provider):
    """
    Tìm HAProxy rảnh (không nằm trong danh sách profiles) để tái sử dụng
    """
    try:
        # Get ports used by profiles
        profile_ports = set()
        for profile in profiles:
            if profile.get('proxy'):
                proxy = profile['proxy']
                # Parse socks5://host:port:server format
                if proxy.startswith('socks5://'):
                    # Remove socks5:// prefix
                    proxy = proxy[9:]
                    parts = proxy.split(':')
                else:
                    # Parse 127.0.0.1:port:server:proxy_port format
                    parts = proxy.split(':')
                
                if len(parts) >= 2:
                    try:
                        port = int(parts[1])
                        profile_ports.add(port)
                    except ValueError:
                        pass
        
        # Find all existing HAProxy configs
        import glob
        available_haproxies = []
        
        for cfg_file in glob.glob(os.path.join(BASE_DIR, 'config', 'haproxy_*.cfg')):
            try:
                port = int(cfg_file.split('_')[-1].replace('.cfg', ''))
                
                # Skip if port is used by profiles
                if port in profile_ports:
                    continue
                
                # Check if HAProxy is running
                pid_file = os.path.join(BASE_DIR, 'logs', f'haproxy_{port}.pid')
                is_running = False
                if os.path.exists(pid_file):
                    try:
                        with open(pid_file, 'r') as f:
                            pid = int(f.read().strip())
                        os.kill(pid, 0)  # Check if process exists
                        is_running = True
                    except (OSError, ValueError):
                        pass
                
                # If not running, check if port is listening
                if not is_running:
                    result = run_command(f'lsof -ti :{port}')
                    is_running = bool(result['success'] and result['stdout'].strip())
                
                if is_running:
                    # Get current server from HAProxy config
                    current_server = _get_server_from_haproxy_config(cfg_file)
                    available_haproxies.append({
                        'port': port,
                        'config_file': cfg_file,
                        'current_server': current_server
                    })
                    
            except (ValueError, IndexError):
                continue
        
        # If no available HAProxy found, return None
        if not available_haproxies:
            return None
        
        # Try to reconfigure the first available HAProxy
        for haproxy in available_haproxies:
            port = haproxy['port']
            current_server = haproxy['current_server']
            
            # Check if the wireproxy port mapping is correct
            expected_wireproxy_port = 18181 + (int(port) - 7891)
            
            # Verify the HAProxy is using the correct wireproxy port
            haproxy_config_path = os.path.join(BASE_DIR, 'config', f'haproxy_{port}.cfg')
            if os.path.exists(haproxy_config_path):
                with open(haproxy_config_path, 'r') as f:
                    content = f.read()
                    import re
                    match = re.search(r'server\s+wg\d+\s+127\.0\.0\.1:(\d+)', content)
                    if match:
                        actual_wireproxy_port = int(match.group(1))
                        if actual_wireproxy_port != expected_wireproxy_port:
                            # Skip this HAProxy if port mapping is incorrect
                            continue
            
            # Reconfigure HAProxy with new server
            result = _reconfigure_haproxy_with_server(port, target_server, vpn_provider)
            if result['success']:
                return {
                    'port': port,
                    'server': result.get('server', target_server),
                    'old_server': current_server,
                    'new_server': target_server
                }
        
        return None
        
    except Exception as e:
        return None

def _get_server_from_haproxy_config(haproxy_config_path):
    """Lấy server name từ HAProxy config bằng cách kiểm tra wireproxy backend"""
    try:
        # Read HAProxy config to find which wireproxy port it's using
        with open(haproxy_config_path, 'r') as f:
            content = f.read()
            # Find wireproxy backend port (e.g., "server wg1 127.0.0.1:18181")
            import re
            match = re.search(r'server\s+wg\d+\s+127\.0\.0\.1:(\d+)', content)
            if not match:
                return None
            
            wireproxy_port = match.group(1)
            
            # Find wireproxy config file using this port
            import glob
            for conf_file in glob.glob(os.path.join(BASE_DIR, 'wg*.conf')):
                try:
                    with open(conf_file, 'r') as f:
                        conf_content = f.read()
                        if f'BindAddress = 127.0.0.1:{wireproxy_port}' in conf_content or \
                           f'BindAddress = 0.0.0.0:{wireproxy_port}' in conf_content:
                            # Found the wireproxy config, now get endpoint
                            endpoint_match = re.search(r'Endpoint\s*=\s*([^\s:]+):', conf_content)
                            if endpoint_match:
                                endpoint = endpoint_match.group(1)
                                # Try to resolve server name from endpoint IP
                                server_name = _resolve_server_name_from_endpoint(endpoint)
                                return server_name
                except Exception:
                    continue
        
        return None
    except Exception:
        return None

def _resolve_server_name_from_endpoint(endpoint_ip):
    """Resolve server name from endpoint IP by checking VPN APIs"""
    try:
        # Check NordVPN servers
        if nordvpn_api:
            nordvpn_api.fetch_servers()
            for server in nordvpn_api.servers:
                if server['station'] == endpoint_ip:
                    return server['name']
        
        # Check ProtonVPN servers
        if protonvpn_api:
            protonvpn_api.fetch_servers()
            for server in protonvpn_api.servers:
                if server['entry_ip'] == endpoint_ip:
                    return server['name']
        
        return None
    except Exception:
        return None

def _handle_server_not_found(server_name, original_vpn_provider, port):
    """
    Handle server not found by trying fallback logic:
    1. Extract country code from server name (if length = 2)
    2. Random select VPN provider and find server by country
    3. If no country match, fallback to random server
    """
    import random
    
    try:
        # Extract country code from server name based on VPN provider
        country_code = None
        
        # If servername is exactly 2 characters, that's the country
        if len(server_name) == 2:
            country_code = server_name.upper()
            # For 2-character server names, we'll random select VPN provider
            # and find server by country code
        else:
            # Determine VPN provider from server name
            if 'nordvpn' in server_name.lower():
                # NordVPN: fr42.nordvpn.com -> fr (first 2 characters before first number)
                parts = server_name.split('.')
                if parts:
                    first_part = parts[0]
                    # Extract country code (2 letters before first number)
                    import re
                    match = re.match(r'^([a-zA-Z]{2})', first_part)
                    if match:
                        country_code = match.group(1).upper()
            elif 'protonvpn' in server_name.lower():
                # ProtonVPN: vn-01.protonvpn.net -> vn (split by '-' and take [0])
                # Also handle: node-lu-06.protonvpn.net -> lu (split by '-' and take [1])
                parts = server_name.split('.')
                if parts:
                    first_part = parts[0]
                    dash_parts = first_part.split('-')
                    if len(dash_parts) >= 2 and dash_parts[0] == 'node':
                        # For node-lu-06.protonvpn.net, take the second part (lu)
                        country_code = dash_parts[1].upper()
                    elif len(dash_parts) >= 1:
                        # For vn-01.protonvpn.net, take the first part (vn)
                        country_code = dash_parts[0].upper()
            else:
                # Generic fallback: try to extract 2 letters from beginning
                parts = server_name.split('.')
                if parts:
                    first_part = parts[0]
                    import re
                    match = re.match(r'^([a-zA-Z]{2})', first_part)
                    if match:
                        country_code = match.group(1).upper()
        
        # Available VPN providers
        vpn_providers = ['nordvpn', 'protonvpn']
        
        # Try to find server by country code
        if country_code:
            # Country code mapping for common cases
            country_mappings = {
                'UK': 'GB',  # United Kingdom
                'US': 'US',  # United States
                'FR': 'FR',  # France
                'DE': 'DE',  # Germany
                'JP': 'JP',  # Japan
                'CA': 'CA',  # Canada
                'AU': 'AU',  # Australia
                'IT': 'IT',  # Italy
                'ES': 'ES',  # Spain
                'NL': 'NL',  # Netherlands
                'SE': 'SE',  # Sweden
                'NO': 'NO',  # Norway
                'DK': 'DK',  # Denmark
                'FI': 'FI',  # Finland
                'CH': 'CH',  # Switzerland
                'AT': 'AT',  # Austria
                'BE': 'BE',  # Belgium
                'PL': 'PL',  # Poland
                'CZ': 'CZ',  # Czech Republic
                'HU': 'HU',  # Hungary
                'RO': 'RO',  # Romania
                'BG': 'BG',  # Bulgaria
                'HR': 'HR',  # Croatia
                'SI': 'SI',  # Slovenia
                'SK': 'SK',  # Slovakia
                'LT': 'LT',  # Lithuania
                'LV': 'LV',  # Latvia
                'EE': 'EE',  # Estonia
                'IE': 'IE',  # Ireland
                'PT': 'PT',  # Portugal
                'GR': 'GR',  # Greece
                'CY': 'CY',  # Cyprus
                'MT': 'MT',  # Malta
                'LU': 'LU',  # Luxembourg
                'IS': 'IS',  # Iceland
                'LI': 'LI',  # Liechtenstein
                'MC': 'MC',  # Monaco
                'SM': 'SM',  # San Marino
                'VA': 'VA',  # Vatican City
                'AD': 'AD',  # Andorra
                'VN': 'VN',  # Vietnam -> Vietnam (keep original)
            }
            
            # Map country code if needed
            mapped_country = country_mappings.get(country_code, country_code)
            
            # For 2-character server names, try both providers but prioritize based on country availability
            if len(server_name) == 2:
                # Check which providers have servers for this country
                available_providers = []
                
                # Check NordVPN
                try:
                    nordvpn_servers = nordvpn_api.get_servers_by_country(mapped_country)
                    if nordvpn_servers:
                        available_providers.append('nordvpn')
                except Exception:
                    pass
                
                # Check ProtonVPN
                try:
                    if protonvpn_api:
                        protonvpn_servers = protonvpn_api.get_servers_by_country(mapped_country)
                        if protonvpn_servers:
                            available_providers.append('protonvpn')
                except Exception:
                    pass
                
                # If no providers have servers for this country, fallback to random
                if not available_providers:
                    vpn_providers = ['nordvpn', 'protonvpn']
                    random.shuffle(vpn_providers)
                else:
                    # Use available providers, shuffle for randomness
                    vpn_providers = available_providers
                    random.shuffle(vpn_providers)
            else:
                # Randomize order of VPN providers
                random.shuffle(vpn_providers)
            
            for vpn_provider in vpn_providers:
                try:
                    if vpn_provider == 'nordvpn':
                        api = nordvpn_api
                    elif vpn_provider == 'protonvpn':
                        if not protonvpn_api:
                            continue
                        api = protonvpn_api
                    else:
                        continue
                    
                    # Try original country code first, then mapped
                    for test_country in [country_code, mapped_country]:
                        if test_country == country_code and test_country == mapped_country:
                            # Same country, only process once
                            pass
                            
                        # Get servers by country
                        servers = api.get_servers_by_country(test_country)
                        if servers:
                            # Try multiple servers to find one that works
                            max_attempts = min(3, len(servers))  # Try up to 3 servers
                            for attempt in range(max_attempts):
                                # Random select a server
                                selected_server = random.choice(servers)
                                server_name = selected_server['hostname'] if vpn_provider == 'nordvpn' else selected_server['name']
                                
                                # Get domain name instead of display name
                                if 'domain' in selected_server:
                                    server_domain = selected_server['domain']
                                elif 'hostname' in selected_server:
                                    server_domain = selected_server['hostname']
                                else:
                                    # Fallback to name if no domain field
                                    server_domain = server_name
                                
                                # Find available port for fallback
                                fallback_port = _find_available_port_for_fallback(port)
                                if fallback_port:
                                    # Create HAProxy with the selected server (avoid recursion)
                                    result = _create_haproxy_with_server_direct(fallback_port, server_domain, vpn_provider)
                                    if result['success']:
                                        # Test if the created HAProxy actually works
                                        import time
                                        time.sleep(5)  # Wait longer for HAProxy to start
                                        
                                        # Quick connectivity test - try multiple times
                                        test_success = False
                                        for test_attempt in range(3):
                                            test_result = run_command(f'curl -s --connect-timeout 5 --socks5 127.0.0.1:{fallback_port} http://httpbin.org/ip')
                                            if test_result['success'] and 'origin' in test_result['stdout']:
                                                test_success = True
                                                break
                                            time.sleep(2)  # Wait between tests
                                        
                                        if test_success:
                                            result['fallback_info'] = {
                                                'original_server': server_domain,
                                                'country_code': test_country,
                                                'vpn_provider': vpn_provider,
                                                'reason': 'country_match',
                                                'fallback_port': fallback_port
                                            }
                                            # Update the port to the actual fallback port used
                                            result['port'] = fallback_port
                                            return result
                                        else:
                                            # Server doesn't work, clean up and try next
                                            try:
                                                # Stop HAProxy and Wireproxy
                                                run_command(f'lsof -ti :{fallback_port} | xargs -r kill -9 2>/dev/null || true')
                                                wireproxy_port = 18181 + (fallback_port - 7891)
                                                run_command(f'lsof -ti :{wireproxy_port} | xargs -r kill -9 2>/dev/null || true')
                                            except Exception:
                                                pass
                                            continue
                                    else:
                                        # If creation failed, try next port
                                        continue
                            else:
                                # No available port, try next country
                                continue
                        else:
                            # No servers found for this country, try next
                            continue
                except Exception as e:
                    continue
        
        # If no country match or country code not found, try random server from any provider
        random.shuffle(vpn_providers)
        
        for vpn_provider in vpn_providers:
            try:
                if vpn_provider == 'nordvpn':
                    api = nordvpn_api
                elif vpn_provider == 'protonvpn':
                    if not protonvpn_api:
                        continue
                    api = protonvpn_api
                else:
                    continue
                
                # Get random server
                servers = api.fetch_servers()
                if servers:
                    selected_server = random.choice(servers)
                    
                    # Get domain name instead of display name
                    if 'domain' in selected_server:
                        server_domain = selected_server['domain']
                    elif 'hostname' in selected_server:
                        server_domain = selected_server['hostname']
                    else:
                        # Fallback to name if no domain field
                        server_domain = selected_server.get('name', 'unknown')
                    
                    # Find available port for fallback
                    fallback_port = _find_available_port_for_fallback(port)
                    if fallback_port:
                        # Create HAProxy with the selected server (avoid recursion)
                        result = _create_haproxy_with_server_direct(fallback_port, server_domain, vpn_provider)
                        if result['success']:
                            result['fallback_info'] = {
                                'original_server': server_domain,
                                'country_code': country_code,
                                'vpn_provider': vpn_provider,
                                'reason': 'random_fallback',
                                'fallback_port': fallback_port
                            }
                            # Update the port to the actual fallback port used
                            result['port'] = fallback_port
                            return result
                        else:
                            # If creation failed, try next port
                            continue
                    else:
                        # No available port, try next provider
                        continue
                else:
                    # No servers available, try next provider
                    continue
            except Exception as e:
                continue
        
        return {'success': False, 'error': 'No servers available from any VPN provider'}
        
    except Exception as e:
        return {'success': False, 'error': f'Fallback logic failed: {str(e)}'}

def _create_haproxy_with_server_direct(port, server_name, vpn_provider):
    """Tạo HAProxy service mới với server cụ thể (không có fallback logic)"""
    try:
        # Get server info from VPN API
        if vpn_provider == 'nordvpn':
            api = nordvpn_api
            from nordvpn_api import DEFAULT_PRIVATE_KEY
            private_key = DEFAULT_PRIVATE_KEY
        elif vpn_provider == 'protonvpn':
            if not protonvpn_api:
                return {'success': False, 'error': 'ProtonVPN API not configured'}
            api = protonvpn_api
            from protonvpn_api import DEFAULT_PRIVATE_KEY
            private_key = DEFAULT_PRIVATE_KEY
        else:
            return {'success': False, 'error': f'Unknown VPN provider: {vpn_provider}'}
        
        # Get server
        server = api.get_server_by_name(server_name)
        if not server:
            return {'success': False, 'error': f'Server {server_name} not found'}
        
        # Continue with the rest of the original logic...
        return _create_haproxy_with_server_impl(port, server_name, vpn_provider, server, private_key)
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def _create_haproxy_with_server(port, server_name, vpn_provider):
    """Tạo HAProxy service mới với server cụ thể"""
    try:
        # Get server info from VPN API
        if vpn_provider == 'nordvpn':
            api = nordvpn_api
            from nordvpn_api import DEFAULT_PRIVATE_KEY
            private_key = DEFAULT_PRIVATE_KEY
        elif vpn_provider == 'protonvpn':
            if not protonvpn_api:
                return {'success': False, 'error': 'ProtonVPN API not configured'}
            api = protonvpn_api
            from protonvpn_api import DEFAULT_PRIVATE_KEY
            private_key = DEFAULT_PRIVATE_KEY
        else:
            return {'success': False, 'error': f'Unknown VPN provider: {vpn_provider}'}
        
        # Get server
        server = api.get_server_by_name(server_name)
        if not server:
            # If server name is 2 characters (country code), try to find by country
            if len(server_name) == 2:
                servers = api.get_servers_by_country(server_name.upper())
                if servers:
                    # Use the first available server from that country
                    server = servers[0]
                    # Update server_name to the correct format based on provider
                    if vpn_provider == 'nordvpn':
                        server_name = server['hostname']  # NordVPN: use hostname
                    elif vpn_provider == 'protonvpn':
                        server_name = server['domain']    # ProtonVPN: use domain
                    elif vpn_provider == 'nordvpn':
                        server_name = server['hostname']  # NordVPN: use hostname
                    else:
                        server_name = server['name']      # Fallback: use name
            else:
                # Server not found - try fallback logic
                fallback_result = _handle_server_not_found(server_name, vpn_provider, port)
                if fallback_result['success']:
                    return fallback_result
                else:
                    return {'success': False, 'error': f'Server {server_name} not found and fallback failed: {fallback_result["error"]}'}
        
        if not server:
            return {'success': False, 'error': f'Server {server_name} not found'}
        
        # Continue with implementation
        return _create_haproxy_with_server_impl(port, server_name, vpn_provider, server, private_key)
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def _create_haproxy_with_server_impl(port, server_name, vpn_provider, server, private_key):
    """Implementation chung cho việc tạo HAProxy với server"""
    try:
        # Calculate gost port dynamically based on available ports
        try:
            haproxy_port_num = int(port)
            available_gost_ports = get_available_gost_ports()
            
            # Try to find a matching gost port or calculate one
            if available_gost_ports:
                # Use first available gost port or calculate based on HAProxy port
                gost_port = int(available_gost_ports[0]) if len(available_gost_ports) == 1 else 18181 + (haproxy_port_num - 7891)
            else:
                gost_port = 18181 + (haproxy_port_num - 7891)
            
            # Validate port range
            if gost_port < 18181 or gost_port > 18999:
                return {'success': False, 'error': f'Invalid port mapping: HAProxy {port} -> Gost {gost_port} (range: 18181-18999)'}
                
        except ValueError:
            return {'success': False, 'error': f'Invalid HAProxy port: {port}'}
        
        # Check if gost port is already in use by another HAProxy
        import glob
        for cfg_file in glob.glob(os.path.join(BASE_DIR, 'config', 'haproxy_*.cfg')):
            try:
                with open(cfg_file, 'r') as f:
                    content = f.read()
                    import re
                    # Find gost port in HAProxy config
                    match = re.search(r'server\s+gost\d+\s+127\.0\.0\.1:(\d+)', content)
                    if match:
                        existing_gost_port = int(match.group(1))
                        if existing_gost_port == gost_port:
                            # This gost port is already used by another HAProxy
                            return {'success': False, 'error': f'Gost port {gost_port} is already used by another HAProxy. Port mapping conflict.'}
            except Exception:
                pass
        
        # Get API service
        if vpn_provider == 'nordvpn':
            api = nordvpn_api
        elif vpn_provider == 'protonvpn':
            api = protonvpn_api
        else:
            return {'success': False, 'error': f'Unknown VPN provider: {vpn_provider}'}
        
        # Create gost config
        proxy_url = None
        
        if vpn_provider == 'nordvpn':
            proxy_url = proxy_api.get_nordvpn_proxy(server['hostname'])
        elif vpn_provider == 'protonvpn':
            proxy_url = get_protonvpn_proxy_with_server(server)
        
        if not proxy_url:
            return {'success': False, 'error': f'Failed to generate proxy URL for {vpn_provider} server'}
        
        # Save gost config
        config = {
            'provider': vpn_provider,
            'country': server['hostname'] if vpn_provider == 'nordvpn' else server['name'],
            'proxy_url': proxy_url
        }
        
        if not save_gost_config(str(gost_port), config):
            return {'success': False, 'error': 'Failed to save gost config'}
        
        # Start gost with verification and logging
        os.makedirs(LOG_DIR, exist_ok=True)
        
        # Start gost service using manage_gost.sh
        cmd = f'./manage_gost.sh start'
        result = run_command(cmd)
        
        if not result['success']:
            return {'success': False, 'error': f'Failed to start gost: {result["stderr"]}'}
        
        # Wait for gost to be ready
        import time
        for _ in range(20):  # ~10s max
            time.sleep(0.5)
            # Check if port is listening
            port_check = run_command(f'lsof -ti :{gost_port}')
            if port_check['success'] and port_check['stdout'].strip():
                break
        else:
            return {'success': False, 'error': 'Timeout waiting for gost to start'}
        
        # Force kill any HAProxy processes on this port
        try:
            # Kill by port using lsof
            run_command(f'lsof -ti :{port} | xargs -r kill -9 2>/dev/null || true')
            import time
            time.sleep(1)
        except Exception:
            pass
        
        # Also check PID file and kill if exists
        pid_file = os.path.join(BASE_DIR, 'logs', f'haproxy_{port}.pid')
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    old_pid = int(f.read().strip())
                # Force kill the process
                try:
                    os.kill(old_pid, 9)  # SIGKILL
                except (ProcessLookupError, OSError):
                    pass  # Process already dead
            except (ValueError, FileNotFoundError):
                pass
        
        # Also stop any health monitor for this port
        health_pid_file = os.path.join(LOG_DIR, f'health_{port}.pid')
        if os.path.exists(health_pid_file):
            try:
                with open(health_pid_file, 'r') as f:
                    health_pid = int(f.read().strip())
                os.kill(health_pid, 15)
                os.remove(health_pid_file)
            except (ValueError, FileNotFoundError, ProcessLookupError, OSError):
                pass
        
        # Create HAProxy config
        haproxy_config_path = os.path.join(BASE_DIR, 'config', f'haproxy_{port}.cfg')
        # Calculate stats port dynamically: HAProxy port + 200
        stats_port = int(port) + 200
        
        # Generate HAProxy config content
        config_content = f"""global
    log stdout format raw local0
    maxconn 4096
    pidfile {os.path.join(BASE_DIR, 'logs', f'haproxy_{port}.pid')}
    daemon

defaults
    mode tcp
    timeout connect 2s
    timeout client 1m
    timeout server 1m
    timeout check 2s
    retries 2
    option redispatch
    option tcplog
    log global

frontend socks_front_{port}
    bind 0.0.0.0:{port}
    default_backend socks_back_{port}

backend socks_back_{port}
    balance first
    option tcp-check
    tcp-check connect
    server gost1 127.0.0.1:{gost_port} check inter 1s rise 1 fall 2 on-error fastinter
    server cloudflare_warp 127.0.0.1:8111 check inter 1s rise 1 fall 2 on-error fastinter backup

listen stats_{port}
    bind 0.0.0.0:{stats_port}
    mode http
    stats enable
    stats uri /haproxy?stats
    stats refresh 2s
    stats show-legends
    stats show-desc HAProxy Instance - SOCKS:{port}
    stats auth admin:admin123
"""
        
        # Write HAProxy config
        os.makedirs(os.path.dirname(haproxy_config_path), exist_ok=True)
        with open(haproxy_config_path, 'w') as f:
            f.write(config_content)
        
        # Start HAProxy
        try:
            haproxy_bin = subprocess.check_output(['which', 'haproxy'], text=True).strip()
        except Exception:
            haproxy_bin = '/opt/homebrew/sbin/haproxy'
        
        cmd = f'{haproxy_bin} -f {haproxy_config_path} -p {pid_file} -D'
        result = run_command(cmd)
        
        if not result['success']:
            # Cleanup gost if HAProxy fails
            try:
                # Stop only the specific gost service for this port
                run_command(f'./manage_gost.sh restart-port {gost_port}')
            except Exception:
                pass
            return {'success': False, 'error': f'Failed to start HAProxy: {result["stderr"]}'}
        
        # Start health monitor
        _start_health_monitor(port, [gost_port])
        
        return {'success': True, 'port': port, 'server': server_name, 'gost_port': gost_port}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def _reconfigure_haproxy_with_server(port, server_name, vpn_provider):
    """Reconfigure existing HAProxy với server mới"""
    try:
        # Find associated gost
        haproxy_config_path = os.path.join(BASE_DIR, 'config', f'haproxy_{port}.cfg')
        gost_port = None
        
        if os.path.exists(haproxy_config_path):
            with open(haproxy_config_path, 'r') as f:
                content = f.read()
                import re
                match = re.search(r'server\s+gost\d+\s+127\.0\.0\.1:(\d+)', content)
                if match:
                    gost_port = int(match.group(1))
        
        # Stop existing HAProxy
        pid_file = os.path.join(BASE_DIR, 'logs', f'haproxy_{port}.pid')
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                os.kill(pid, 15)
            except Exception:
                pass
        
        # Stop health monitor
        health_pid_file = os.path.join(BASE_DIR, 'logs', f'health_{port}.pid')
        if os.path.exists(health_pid_file):
            try:
                with open(health_pid_file, 'r') as f:
                    pid = int(f.read().strip())
                os.kill(pid, 15)
                os.remove(health_pid_file)
            except Exception:
                pass
        
        # Stop and reconfigure gost if found
        if gost_port:
            # Stop and reconfigure specific gost service
            run_command(f'./manage_gost.sh restart-port {gost_port}')
            
            # Wait for port to be released
            import time
            time.sleep(1)
            
            # Wait for port to be released
            for _ in range(10):  # Wait up to 5 seconds
                time.sleep(0.5)
                result = run_command(f'lsof -ti :{gost_port}')
                if not (result['success'] and result['stdout'].strip()):
                    break
            
            # Update gost config with new server
            if vpn_provider == 'nordvpn':
                api = nordvpn_api
            elif vpn_provider == 'protonvpn':
                if not protonvpn_api:
                    return {'success': False, 'error': 'ProtonVPN API not configured'}
                api = protonvpn_api
            else:
                return {'success': False, 'error': f'Unknown VPN provider: {vpn_provider}'}
            
            server = api.get_server_by_name(server_name)
            if not server:
                # If server name is 2 characters (country code), try to find by country
                if len(server_name) == 2:
                    servers = api.get_servers_by_country(server_name.upper())
                    if servers:
                        # Use the first available server from that country
                        server = servers[0]
                        # Update server_name to the correct format based on provider
                        if vpn_provider == 'nordvpn':
                            server_name = server['hostname']  # NordVPN: use hostname
                        elif vpn_provider == 'protonvpn':
                            server_name = server['domain']    # ProtonVPN: use domain
                        elif vpn_provider == 'nordvpn':
                            server_name = server['hostname']  # NordVPN: use hostname
                        else:
                            server_name = server['name']      # Fallback: use name
                
                if not server:
                    # Server not found - try to extract country code and find alternative server
                    country_code = None
                    
                    # Extract country code from server name based on provider
                    print(f"DEBUG: Extracting country code from '{server_name}' for provider '{vpn_provider}'")
                    
                    if vpn_provider == 'nordvpn':
                        # NordVPN: node-vn-02.protonvpn.net -> vn (first 2 characters before first number)
                        parts = server_name.split('.')
                        if parts:
                            first_part = parts[0]
                            import re
                            match = re.match(r'^([a-zA-Z]{2})', first_part)
                            if match:
                                country_code = match.group(1).upper()
                                print(f"DEBUG: NordVPN country code: {country_code}")
                    elif vpn_provider == 'protonvpn':
                        # ProtonVPN: vn-01.protonvpn.net -> vn (split by '-' and take [0])
                        # Also handle: node-lu-06.protonvpn.net -> lu (split by '-' and take [1])
                        parts = server_name.split('.')
                        if parts:
                            first_part = parts[0]
                            dash_parts = first_part.split('-')
                            print(f"DEBUG: ProtonVPN dash_parts: {dash_parts}")
                            
                            if len(dash_parts) >= 2 and dash_parts[0] == 'node':
                                # For node-lu-06.protonvpn.net, take the second part (lu)
                                country_code = dash_parts[1].upper()
                                print(f"DEBUG: ProtonVPN node format country code: {country_code}")
                            elif len(dash_parts) >= 1:
                                # For vn-01.protonvpn.net, take the first part (vn)
                                country_code = dash_parts[0].upper()
                                print(f"DEBUG: ProtonVPN standard format country code: {country_code}")
                    
                    print(f"DEBUG: Final country code: {country_code}")
                    
                    if country_code:
                        # Try to find alternative server from same country
                        servers = api.get_servers_by_country(country_code)
                        if servers:
                            # Use random server from same country
                            import random
                            server = random.choice(servers)
                            # Update server_name to the correct format based on provider
                            if vpn_provider == 'nordvpn':
                                server_name = server['hostname']  # NordVPN: use hostname
                            elif vpn_provider == 'protonvpn':
                                server_name = server['domain']    # ProtonVPN: use domain
                            elif vpn_provider == 'nordvpn':
                                server_name = server['hostname']  # NordVPN: use hostname
                            else:
                                server_name = server['name']      # Fallback: use name
                            
                            # Debug logging
                            print(f"DEBUG: Found {len(servers)} servers for country {country_code}")
                            print(f"DEBUG: Selected server: {server_name}")
                            print(f"DEBUG: Server domain: {server.get('domain', 'N/A')}")
                            print(f"DEBUG: Server name: {server.get('name', 'N/A')}")
                        else:
                            print(f"DEBUG: No servers found for country {country_code}")
                    
                    if not server:
                        # If still no server found, try random server from any country
                        try:
                            # Try to get all servers from the current provider
                            all_servers = api.fetch_servers()
                            if all_servers:
                                import random
                                server = random.choice(all_servers)
                                # Update server_name to the correct format based on provider
                                if vpn_provider == 'nordvpn':
                                    server_name = server['hostname']  # NordVPN: use hostname
                                elif vpn_provider == 'protonvpn':
                                    server_name = server['domain']    # ProtonVPN: use domain
                                elif vpn_provider == 'nordvpn':
                                    server_name = server['hostname']  # NordVPN: use hostname
                                else:
                                    server_name = server['name']      # Fallback: use name
                                
                                # Debug logging
                                print(f"DEBUG: Fallback to random server from {vpn_provider}")
                                print(f"DEBUG: Selected random server: {server_name}")
                                print(f"DEBUG: Server domain: {server.get('domain', 'N/A')}")
                                print(f"DEBUG: Server country: {server.get('country_code', 'N/A')}")
                        except Exception as e:
                            print(f"DEBUG: Error in random fallback: {e}")
                            pass
                    
                    if not server:
                        # If still no server found, try the other VPN provider as last resort
                        try:
                            other_provider = 'protonvpn' if vpn_provider == 'nordvpn' else 'nordvpn'
                            other_api = protonvpn_api if other_provider == 'protonvpn' else nordvpn_api
                            
                            if other_api:
                                all_servers = other_api.fetch_servers()
                                if all_servers:
                                    import random
                                    server = random.choice(all_servers)
                                    # Update server_name to the correct format based on provider
                                    if other_provider == 'nordvpn':
                                        server_name = server['hostname']  # NordVPN: use hostname
                                    elif other_provider == 'protonvpn':
                                        server_name = server['domain']    # ProtonVPN: use domain
                                    elif other_provider == 'nordvpn':
                                        server_name = server['hostname']  # NordVPN: use hostname
                                    else:
                                        server_name = server['name']      # Fallback: use name
                                    
                                    # Update vpn_provider to the one we actually used
                                    vpn_provider = other_provider
                        except Exception:
                            pass
                    
                    if not server:
                        # If still no server found, return error
                        return {'success': False, 'error': f'Server {server_name} not found and no alternative server available'}
            
            # Get proxy URL for the server
            proxy_url = None
        if vpn_provider == 'nordvpn':
            proxy_url = proxy_api.get_nordvpn_proxy(server['hostname'])
        elif vpn_provider == 'protonvpn':
            proxy_url = get_protonvpn_proxy_with_server(server)
            
            if not proxy_url:
                return {'success': False, 'error': f'Failed to generate proxy URL for {vpn_provider} server'}
            
            # Save gost config
            config = {
                'provider': vpn_provider,
                'country': server['name'],
                'proxy_url': proxy_url
            }
            
            if not save_gost_config(str(gost_port), config):
                return {'success': False, 'error': 'Failed to save gost config'}
            
            # Gost config already saved above
            
            # Restart gost with verification

            # Restart gost service
            cmd = f'./manage_gost.sh restart'
            result = run_command(cmd)
            
            if not result['success']:
                return {'success': False, 'error': f'Failed to restart gost: {result["stderr"]}'}
            
            # Wait for gost to be ready
            import time
            for _ in range(20):  # ~10s max
                time.sleep(0.5)
                # Check if port is listening
                port_check = run_command(f'lsof -ti :{gost_port}')
                if port_check['success'] and port_check['stdout'].strip():
                    break
            else:
                return {'success': False, 'error': 'Timeout waiting for gost to start'}

            # Gost restarted successfully
        
        # CRITICAL: Restart HAProxy and verify it's working
        try:
            haproxy_bin = subprocess.check_output(['which', 'haproxy'], text=True).strip()
        except Exception:
            haproxy_bin = '/opt/homebrew/sbin/haproxy'
        
        cmd = f'{haproxy_bin} -f {haproxy_config_path} -p {pid_file} -D'
        result = run_command(cmd)
        
        if not result['success']:
            return {'success': False, 'error': f'Failed to start HAProxy: {result["stderr"]}'}
        
        # Verify HAProxy is actually running and listening on the port
        import time
        time.sleep(2)  # Give HAProxy time to start
        port_check = run_command(f'lsof -ti :{port}')
        if not (port_check['success'] and port_check['stdout'].strip()):
            return {'success': False, 'error': f'HAProxy started but not listening on port {port}'}
        
        # Restart health monitor
        if gost_port:
            _start_health_monitor(port, [gost_port])
        
        return {'success': True, 'port': port, 'server': server_name, 'gost_port': gost_port}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _start_health_monitor(haproxy_port, gost_ports):
    """Start health monitor for HAProxy service"""
    try:
        script_path = os.path.join(BASE_DIR, 'setup_haproxy.sh')
        cmd = f'{script_path} --sock-port {haproxy_port} --stats-port {8000 + int(haproxy_port) - 7890} --gost-ports {",".join(map(str, gost_ports))} --daemon'
        
        # Run in background
        subprocess.Popen(cmd, shell=True, cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        return True
    except Exception:
        return False

if __name__ == '__main__':
    # Tạo thư mục logs nếu chưa có
    os.makedirs(LOG_DIR, exist_ok=True)
    
    print("=" * 60)
    print("🌐 HAProxy & Gost Web UI")
    print("=" * 60)
    print(f"📂 Base Directory: {BASE_DIR}")
    print(f"📝 Log Directory: {LOG_DIR}")
    print(f"🔧 Config Files:")
    print(f"   - Gost 18181: {os.path.join(BASE_DIR, 'config', 'gost_18181.config')}")
    print(f"   - Gost 18182: {os.path.join(BASE_DIR, 'config', 'gost_18182.config')}")
    print("=" * 60)
    print("🚀 Starting Web UI on http://0.0.0.0:5000")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
