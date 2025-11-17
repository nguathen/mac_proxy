#!/usr/bin/env python3
"""
Gost Web UI
Quản lý Gost proxy services qua giao diện web
"""

from flask import Flask, render_template, request, jsonify, send_from_directory
import subprocess
import os
import re
import json
import sys
import requests
from datetime import datetime

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nordvpn_api import NordVPNAPI
from protonvpn_api import ProtonVPNAPI
from proxy_api import proxy_api

# Import protonvpn_service để lấy credentials
try:
    from protonvpn_service import Instance as ProtonVpnServiceInstance
except ImportError:
    ProtonVpnServiceInstance = None

# Import handlers
from nordvpn_handler import register_nordvpn_routes
from protonvpn_handler import register_protonvpn_routes
from gost_handler import register_gost_routes
from chrome_handler import register_chrome_routes

app = Flask(__name__)
app.config['SECRET_KEY'] = 'gost-webui-secret-key-2025'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

def run_command(cmd, cwd=BASE_DIR, timeout=60):
    """Chạy shell command và trả về output"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
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
            'stderr': f'Command timeout after {timeout}s',
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
    """Deprecated - kept for API compatibility with chrome_handler"""
    # HAProxy removed - Gost now runs directly on public ports (7891-7999)
    return []

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
    try:
        port_num = int(port)
        # Check if port is in valid range (7891-7999) - Gost now runs directly on public ports
        return 7891 <= port_num <= 7999
    except (ValueError, TypeError):
        return False

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
    """Deprecated - kept for API compatibility with VPN handlers"""
    # HAProxy health checks removed - Gost runs directly
    pass

@app.route('/')
def index():
    """Trang chủ"""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """API endpoint để lấy trạng thái tất cả services"""
    try:
        # Lấy danh sách Gost ports
        gost_ports = get_available_gost_ports()
        gost_services = []
        
        for port in gost_ports:
            try:
                # Kiểm tra PID file
                pid_file = os.path.join(LOG_DIR, f'gost_{port}.pid')
                running = False
                pid = None
                
                if os.path.exists(pid_file):
                    try:
                        with open(pid_file, 'r') as f:
                            pid = f.read().strip()
                        if pid:
                            # Kiểm tra process có đang chạy không
                            import subprocess
                            result = subprocess.run(['ps', '-p', pid], capture_output=True, text=True)
                            running = result.returncode == 0
                    except:
                        pass
                
                # Lấy thông tin server từ config
                server_info = None
                try:
                    config_path = os.path.join(BASE_DIR, 'config', f'gost_{port}.config')
                    if os.path.exists(config_path):
                        import json
                        import re
                        with open(config_path, 'r') as f:
                            config = json.load(f)
                            server_name = config.get('country', '')
                            proxy_url = config.get('proxy_url', '')
                            # Tìm port cuối cùng trong proxy_url
                            port_match = re.search(r':(\d+)$', proxy_url)
                            if server_name and port_match:
                                server_port = port_match.group(1)
                                server_info = f"{server_name}:{server_port}"
                except:
                    pass
                
                gost_services.append({
                    'port': port,
                    'name': f'Gost {port}',
                    'running': running,
                    'pid': pid if running else None,
                    'server_info': server_info,
                    'connection': running  # Simplified
                })
            except Exception as e:
                print(f"Error processing gost port {port}: {e}")
        
        # Kiểm tra Gost Monitor status
        monitor_running = False
        monitor_pid = None
        try:
            monitor_pid_file = os.path.join(LOG_DIR, 'gost_monitor.pid')
            if os.path.exists(monitor_pid_file):
                with open(monitor_pid_file, 'r') as f:
                    monitor_pid = f.read().strip()
                if monitor_pid:
                    result = subprocess.run(['ps', '-p', monitor_pid], capture_output=True, text=True)
                    monitor_running = result.returncode == 0
        except:
            pass
        
        # HAProxy removed - Gost now runs directly on public ports
        return jsonify({
            'gost': gost_services,
            'haproxy': [],  # HAProxy no longer used
            'monitor': {
                'running': monitor_running,
                'pid': monitor_pid if monitor_running else None
            }
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'gost': [],
            'haproxy': [],  # Deprecated - kept for API compatibility
            'monitor': {
                'running': False,
                'pid': None
            }
        }), 500

@app.route('/api/protonvpn/credentials')
def api_protonvpn_credentials():
    """API endpoint để lấy ProtonVPN credentials từ protonvpn_service"""
    try:
        if not ProtonVpnServiceInstance:
            return jsonify({
                'success': False,
                'error': 'protonvpn_service not available'
            }), 500
        
        username = ProtonVpnServiceInstance.user_name
        password = ProtonVpnServiceInstance.password
        
        return jsonify({
            'success': True,
            'username': username,
            'password': password,
            'has_username': bool(username),
            'has_password': bool(password)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/test/proxy/<port>')
def api_test_proxy(port):
    """Test proxy connection"""
    try:
        import requests
        import socket
        
        # Test if port is listening
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(('127.0.0.1', int(port)))
        sock.close()
        
        if result != 0:
            return jsonify({
                'success': False,
                'error': f'Port {port} is not listening'
            })
        
        # Test proxy with requests
        try:
            proxies = {
                'http': f'socks5://127.0.0.1:{port}',
                'https': f'socks5://127.0.0.1:{port}'
            }
            
            response = requests.get('https://api.ipify.org', 
                                  proxies=proxies, 
                                  timeout=10)
            
            if response.status_code == 200:
                return jsonify({
                    'success': True,
                    'ip': response.text.strip()
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'HTTP {response.status_code}'
                })
        except requests.exceptions.RequestException as e:
            return jsonify({
                'success': False,
                'error': f'Proxy test failed: {str(e)}'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/logs/<service>')
def api_logs(service):
    """Get service logs"""
    try:
        log_files = []
        
        # Determine log file paths based on service name
        if service.startswith('gost') or service.startswith('wireproxy'):
            port = service.replace('gost', '').replace('wireproxy', '')
            log_files = [
                os.path.join(LOG_DIR, f'gost_{port}.log')
            ]
        
        # Read and combine logs
        all_logs = []
        for log_file in log_files:
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        if content.strip():
                            all_logs.append(f"=== {os.path.basename(log_file)} ===\n{content}")
                except Exception as e:
                    all_logs.append(f"=== {os.path.basename(log_file)} ===\nError reading file: {e}")
        
        if not all_logs:
            return jsonify({
                'success': True,
                'logs': f'No log files found for {service}'
            })
        
        # Combine all logs
        combined_logs = '\n\n'.join(all_logs)
        
        # Get last 1000 lines if too long
        lines = combined_logs.split('\n')
        if len(lines) > 1000:
            combined_logs = '\n'.join(lines[-1000:])
            combined_logs = f"[Showing last 1000 lines]\n\n{combined_logs}"
        
        return jsonify({
            'success': True,
            'logs': combined_logs
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/clear-all', methods=['POST'])
def api_clear_all():
    """Clear all Gost services"""
    try:
        stopped_services = []
        deleted_files = []
        
        # Get all available ports
        gost_ports = get_available_gost_ports()
        
        print(f"🧹 Starting Clear All operation...")
        print(f"Found {len(gost_ports)} Gost ports: {gost_ports}")
        
        # 1. Stop all Gost services
        for port in gost_ports:
            try:
                pid_file = os.path.join(LOG_DIR, f'gost_{port}.pid')
                if os.path.exists(pid_file):
                    try:
                        with open(pid_file) as f:
                            pid = int(f.read().strip())
                        os.kill(pid, 15)  # SIGTERM
                        stopped_services.append(f"Gost {port} (PID {pid})")
                        print(f"✓ Stopped Gost {port} (PID {pid})")
                    except (OSError, ValueError):
                        pass
                    finally:
                        try:
                            os.remove(pid_file)
                        except:
                            pass
            except Exception as e:
                print(f"⚠️  Error stopping Gost {port}: {e}")
        
        # 2. Force kill any remaining processes
        try:
            import subprocess
            
            # Kill any remaining gost processes
            result = subprocess.run(['pkill', '-f', 'gost'], capture_output=True, text=True)
            if result.returncode == 0:
                stopped_services.append("Remaining Gost processes")
                print("✓ Force killed remaining Gost processes")
                
        except Exception as e:
            print(f"⚠️  Error force killing processes: {e}")
        
        # 3. Delete all Gost configs and logs
        for port in gost_ports:
            files_to_remove = [
                (os.path.join(BASE_DIR, 'config', f'gost_{port}.config'), f'Gost config {port}'),
                (os.path.join(LOG_DIR, f'gost_{port}.log'), f'Gost log {port}'),
                (os.path.join(LOG_DIR, f'gost_{port}.pid'), f'Gost PID {port}')
            ]
            
            for file_path, description in files_to_remove:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        deleted_files.append(description)
                        print(f"✓ Deleted {description}")
                    except Exception as e:
                        print(f"⚠️  Error deleting {description}: {e}")
        
        # 4. Wait a moment to ensure processes are stopped
        import time
        time.sleep(2)
        
        
        return jsonify({
            'success': True,
            'message': f'All services cleared successfully! Stopped {len(stopped_services)} services and deleted {len(deleted_files)} files.',
            'stopped_services': stopped_services,
            'deleted_files': deleted_files
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# Helper functions for Chrome handler
def _get_proxy_port(server_name, vpn_provider):
    """Get actual proxy port based on VPN provider and server name"""
    if vpn_provider == 'nordvpn':
        return 89
    elif vpn_provider == 'protonvpn':
        # Extract server label from server name (e.g., us-ca-10 -> 10)
        try:
            parts = server_name.split('-')
            if len(parts) >= 3:
                label = parts[-1]
                return int(label) + 4443
        except (ValueError, IndexError):
            pass
        return 4443  # Default ProtonVPN port


# Gost Monitor API routes
@app.route('/api/monitor/<action>', methods=['POST'])
def api_monitor_action(action):
    """Điều khiển Gost Monitor"""
    monitor_script = os.path.join(BASE_DIR, 'gost_monitor.sh')
    
    if not os.path.exists(monitor_script):
        return jsonify({
            'success': False,
            'error': 'Gost monitor script not found'
        }), 404
    
    if action not in ['start', 'stop', 'status', 'check']:
        return jsonify({
            'success': False,
            'error': f'Invalid action: {action}'
        }), 400
    
    try:
        result = run_command(f'bash {monitor_script} {action}', timeout=30)
        
        # Với action 'check', exit code 1 có nghĩa là đã restart (không phải lỗi)
        if action == 'check':
            output = result['stdout'] or result['stderr'] or ''
            if result['returncode'] == 0:
                return jsonify({
                    'success': True,
                    'message': 'All gost services are working',
                    'output': output
                })
            elif result['returncode'] == 1:
                # Exit code 1 có nghĩa là đã restart một số services
                return jsonify({
                    'success': True,
                    'message': 'Some gost services were restarted',
                    'output': output
                })
            else:
                # Các exit code khác là lỗi thật sự
                return jsonify({
                    'success': False,
                    'error': result['stderr'] or 'Unknown error',
                    'output': output
                }), 500
        elif result['success']:
            return jsonify({
                'success': True,
                'message': f'Monitor {action} successful',
                'output': result['stdout']
            })
        else:
            return jsonify({
                'success': False,
                'error': result['stderr'] or 'Unknown error',
                'output': result['stdout']
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Register all routes
register_nordvpn_routes(app, save_gost_config, run_command, trigger_health_check, nordvpn_api, proxy_api)
register_protonvpn_routes(app, save_gost_config, run_command, trigger_health_check, protonvpn_api, proxy_api)
register_gost_routes(app, BASE_DIR, LOG_DIR, run_command, save_gost_config, parse_gost_config, is_valid_gost_port, get_available_gost_ports)
# HAProxy routes removed - Gost now runs directly on public ports (7891-7999)
# register_haproxy_routes(app, BASE_DIR, LOG_DIR, run_command, get_available_haproxy_ports, get_available_gost_ports)
register_chrome_routes(app, BASE_DIR, get_available_haproxy_ports, _get_proxy_port)

if __name__ == '__main__':
    # Tạo thư mục logs nếu chưa có
    os.makedirs(LOG_DIR, exist_ok=True)
    
    print("=" * 60)
    print("🌐 Gost Web UI")
    print("=" * 60)
    print(f"📂 Base Directory: {BASE_DIR}")
    print(f"📝 Log Directory: {LOG_DIR}")
    print(f"🔧 Config Files:")
    print(f"   - Config directory: {os.path.join(BASE_DIR, 'config')}")
    print("=" * 60)
    print("🚀 Starting Web UI on http://0.0.0.0:5000")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
