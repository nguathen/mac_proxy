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
from datetime import datetime

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nordvpn_api import NordVPNAPI
from protonvpn_api import ProtonVPNAPI

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

def parse_wireproxy_config(config_path):
    """Parse wireproxy config file"""
    if not os.path.exists(config_path):
        return None
    
    config = {
        'interface': {},
        'peer': {},
        'socks5': {}
    }
    
    try:
        with open(config_path, 'r') as f:
            current_section = None
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if line.startswith('[') and line.endswith(']'):
                    current_section = line[1:-1].lower()
                    continue
                
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if current_section == 'interface':
                        config['interface'][key] = value
                    elif current_section == 'peer':
                        config['peer'][key] = value
                    elif current_section == 'socks5':
                        config['socks5'][key] = value
        
        return config
    except Exception as e:
        return None

def save_wireproxy_config(config_path, config):
    """Save wireproxy config file"""
    try:
        with open(config_path, 'w') as f:
            f.write('[Interface]\n')
            for key, value in config.get('interface', {}).items():
                f.write(f'{key} = {value}\n')
            
            f.write('\n[Peer]\n')
            for key, value in config.get('peer', {}).items():
                f.write(f'{key} = {value}\n')
            
            f.write('\n[Socks5]\n')
            for key, value in config.get('socks5', {}).items():
                f.write(f'{key} = {value}\n')
        
        return True
    except Exception as e:
        return False

def trigger_health_check():
    """Trigger HAProxy health monitors to check immediately by creating trigger file"""
    try:
        # Create trigger files for health monitors
        for port in ['7891', '7892']:
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
        'wireproxy': [],
        'haproxy': [],
        'timestamp': datetime.now().isoformat()
    }
    
    # Check wireproxy
    for i, (name, port, conf) in enumerate([
        ('Wireproxy 1', '18181', WG1_CONF),
        ('Wireproxy 2', '18182', WG2_CONF)
    ], 1):
        pid_file = os.path.join(LOG_DIR, f'wireproxy{i}.pid')
        running = False
        pid = None
        
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                    # Check if process is running
                    os.kill(pid, 0)
                    running = True
            except (OSError, ValueError):
                pass
        
        # Test connection
        connection_ok = False
        if running:
            result = run_command(f'curl -s --max-time 3 -x socks5h://127.0.0.1:{port} https://api.ipify.org')
            connection_ok = result['success'] and result['stdout'].strip()
        
        status['wireproxy'].append({
            'name': name,
            'port': port,
            'running': running,
            'pid': pid,
            'connection': connection_ok,
            'config': conf
        })
    
    # Check HAProxy
    for port in ['7891', '7892']:
        pid_file = os.path.join(LOG_DIR, f'haproxy_{port}.pid')
        running = False
        pid = None
        
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                    os.kill(pid, 0)
                    running = True
            except (OSError, ValueError):
                pass
        
        status['haproxy'].append({
            'name': f'HAProxy {port}',
            'port': port,
            'running': running,
            'pid': pid,
            'stats_url': f'http://127.0.0.1:809{port[-1]}/haproxy?stats'
        })
    
    return jsonify(status)

@app.route('/api/wireproxy/config/<int:instance>')
def api_get_wireproxy_config(instance):
    """Lấy config wireproxy"""
    if instance == 1:
        config = parse_wireproxy_config(WG1_CONF)
    elif instance == 2:
        config = parse_wireproxy_config(WG2_CONF)
    else:
        return jsonify({'success': False, 'error': 'Invalid instance'}), 400
    
    if config:
        return jsonify({'success': True, 'config': config})
    else:
        return jsonify({'success': False, 'error': 'Cannot read config'}), 500

@app.route('/api/wireproxy/config/<int:instance>', methods=['POST'])
def api_save_wireproxy_config(instance):
    """Lưu config wireproxy"""
    data = request.json
    
    if instance == 1:
        config_path = WG1_CONF
    elif instance == 2:
        config_path = WG2_CONF
    else:
        return jsonify({'success': False, 'error': 'Invalid instance'}), 400
    
    config = data.get('config')
    if not config:
        return jsonify({'success': False, 'error': 'No config provided'}), 400
    
    # Backup old config
    if os.path.exists(config_path):
        backup_path = f"{config_path}.backup.{int(datetime.now().timestamp())}"
        os.rename(config_path, backup_path)
    
    if save_wireproxy_config(config_path, config):
        return jsonify({'success': True, 'message': 'Config saved successfully'})
    else:
        return jsonify({'success': False, 'error': 'Cannot save config'}), 500

@app.route('/api/wireproxy/<action>', methods=['POST'])
def api_wireproxy_action(action):
    """Điều khiển wireproxy (start/stop/restart)"""
    if action not in ['start', 'stop', 'restart']:
        return jsonify({'success': False, 'error': 'Invalid action'}), 400
    
    result = run_command(f'bash manage_wireproxy.sh {action}')
    
    return jsonify({
        'success': result['success'],
        'output': result['stdout'],
        'error': result['stderr']
    })

@app.route('/api/wireproxy/<int:instance>/<action>', methods=['POST'])
def api_wireproxy_instance_action(instance, action):
    """Điều khiển từng wireproxy instance riêng lẻ"""
    if instance not in [1, 2]:
        return jsonify({'success': False, 'error': 'Invalid instance'}), 400
    
    if action not in ['start', 'stop', 'restart']:
        return jsonify({'success': False, 'error': 'Invalid action'}), 400
    
    pid_file = os.path.join(LOG_DIR, f'wireproxy{instance}.pid')
    config_file = WG1_CONF if instance == 1 else WG2_CONF
    port = 18181 if instance == 1 else 18182
    
    if action == 'stop':
        # Stop wireproxy instance
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, 15)  # SIGTERM
                os.remove(pid_file)
                return jsonify({
                    'success': True,
                    'message': f'Wireproxy {instance} stopped successfully'
                })
            except (OSError, ValueError) as e:
                return jsonify({
                    'success': False,
                    'error': f'Failed to stop: {str(e)}'
                }), 500
        else:
            return jsonify({
                'success': False,
                'error': 'Wireproxy not running'
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
                    'error': 'Wireproxy already running'
                }), 400
            except OSError:
                os.remove(pid_file)
        
        # Kill any process on the port
        run_command(f'lsof -ti :{port} | xargs -r kill -9 2>/dev/null || true')
        
        # Start wireproxy
        log_file = os.path.join(LOG_DIR, f'wireproxy{instance}.log')
        cmd = f'nohup {os.path.join(BASE_DIR, "wireproxy")} -c {config_file} > {log_file} 2>&1 & echo $!'
        result = run_command(cmd)
        
        if result['success']:
            pid = result['stdout'].strip()
            with open(pid_file, 'w') as f:
                f.write(pid)
            
            # Trigger health monitor to check immediately
            trigger_health_check()
            
            return jsonify({
                'success': True,
                'message': f'Wireproxy {instance} started successfully',
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
                os.remove(pid_file)
            except (OSError, ValueError):
                pass
        
        import time
        time.sleep(1)
        
        # Kill any process on the port
        run_command(f'lsof -ti :{port} | xargs -r kill -9 2>/dev/null || true')
        time.sleep(1)
        
        # Start wireproxy
        log_file = os.path.join(LOG_DIR, f'wireproxy{instance}.log')
        cmd = f'nohup {os.path.join(BASE_DIR, "wireproxy")} -c {config_file} > {log_file} 2>&1 & echo $!'
        result = run_command(cmd)
        
        if result['success']:
            pid = result['stdout'].strip()
            with open(pid_file, 'w') as f:
                f.write(pid)
            
            # Trigger health monitor to check immediately
            trigger_health_check()
            
            return jsonify({
                'success': True,
                'message': f'Wireproxy {instance} restarted successfully',
                'pid': pid
            })
        else:
            return jsonify({
                'success': False,
                'error': result['stderr']
            }), 500

@app.route('/api/haproxy/<action>', methods=['POST'])
def api_haproxy_action(action):
    """Điều khiển HAProxy (start/stop/restart)"""
    if action == 'start':
        result = run_command('bash start_all.sh')
    elif action == 'stop':
        result = run_command('bash stop_all.sh')
    elif action == 'restart':
        result = run_command('bash stop_all.sh && sleep 2 && bash start_all.sh')
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
    log_files = {
        'wireproxy1': 'wireproxy1.log',
        'wireproxy2': 'wireproxy2.log',
        'haproxy1': 'haproxy_health_7891.log',
        'haproxy2': 'haproxy_health_7892.log'
    }
    
    if service not in log_files:
        return jsonify({'success': False, 'error': 'Invalid service'}), 400
    
    log_path = os.path.join(LOG_DIR, log_files[service])
    
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

@app.route('/api/nordvpn/apply/<int:instance>', methods=['POST'])
def api_nordvpn_apply_server(instance):
    """Áp dụng server NordVPN vào wireproxy instance"""
    try:
        if instance not in [1, 2]:
            return jsonify({'success': False, 'error': 'Invalid instance'}), 400
        
        data = request.json
        server_name = data.get('server_name')
        
        if not server_name:
            return jsonify({'success': False, 'error': 'No server name provided'}), 400
        
        # Get server info
        server = nordvpn_api.get_server_by_name(server_name)
        if not server:
            return jsonify({'success': False, 'error': 'Server not found'}), 404
        
        # Get current config to preserve private key
        config_path = WG1_CONF if instance == 1 else WG2_CONF
        current_config = parse_wireproxy_config(config_path)
        
        if not current_config or 'PrivateKey' not in current_config.get('interface', {}):
            return jsonify({
                'success': False,
                'error': 'Cannot read current private key'
            }), 500
        
        private_key = current_config['interface']['PrivateKey']
        
        # Generate new config with NordVPN server
        bind_address = f"127.0.0.1:1818{instance}"
        new_config = nordvpn_api.generate_wireguard_config(
            server=server,
            private_key=private_key,
            bind_address=bind_address
        )
        
        # Backup old config
        if os.path.exists(config_path):
            backup_path = f"{config_path}.backup.{int(datetime.now().timestamp())}"
            os.rename(config_path, backup_path)
        
        # Save new config
        if not save_wireproxy_config(config_path, new_config):
            return jsonify({
                'success': False,
                'error': 'Failed to save config'
            }), 500
        
        # Restart wireproxy instance
        pid_file = os.path.join(LOG_DIR, f'wireproxy{instance}.pid')
        port = 18181 if instance == 1 else 18182
        
        # Stop if running
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, 15)
                os.remove(pid_file)
            except (OSError, ValueError):
                pass
        
        import time
        time.sleep(1)
        
        # Kill any process on the port
        run_command(f'lsof -ti :{port} | xargs -r kill -9 2>/dev/null || true')
        time.sleep(1)
        
        # Start wireproxy
        log_file = os.path.join(LOG_DIR, f'wireproxy{instance}.log')
        cmd = f'nohup {os.path.join(BASE_DIR, "wireproxy")} -c {config_path} > {log_file} 2>&1 & echo $!'
        result = run_command(cmd)
        
        if result['success']:
            pid = result['stdout'].strip()
            with open(pid_file, 'w') as f:
                f.write(pid)
            
            # Trigger health monitor
            trigger_health_check()
            
            return jsonify({
                'success': True,
                'message': f'Applied NordVPN server {server["name"]} to Wireproxy {instance}',
                'server': server,
                'pid': pid
            })
        else:
            return jsonify({
                'success': False,
                'error': result['stderr']
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

@app.route('/api/protonvpn/apply/<int:instance>', methods=['POST'])
def api_protonvpn_apply_server(instance):
    """Áp dụng ProtonVPN server vào wireproxy instance"""
    try:
        if instance not in [1, 2]:
            return jsonify({'success': False, 'error': 'Invalid instance'}), 400
        
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
        
        # Get current config to preserve private key
        config_path = WG1_CONF if instance == 1 else WG2_CONF
        current_config = parse_wireproxy_config(config_path)
        
        if not current_config or 'PrivateKey' not in current_config.get('interface', {}):
            return jsonify({
                'success': False,
                'error': 'Cannot read current private key'
            }), 500
        
        private_key = current_config['interface']['PrivateKey']
        
        # Generate new config with ProtonVPN server
        bind_address = f"127.0.0.1:1818{instance}"
        new_config = protonvpn_api.generate_wireguard_config(
            server=server,
            private_key=private_key,
            bind_address=bind_address
        )
        
        # Backup old config
        if os.path.exists(config_path):
            backup_path = f"{config_path}.backup.{int(datetime.now().timestamp())}"
            os.rename(config_path, backup_path)
        
        # Save new config
        if not save_wireproxy_config(config_path, new_config):
            return jsonify({
                'success': False,
                'error': 'Failed to save config'
            }), 500
        
        # Restart wireproxy instance
        pid_file = os.path.join(LOG_DIR, f'wireproxy{instance}.pid')
        port = 18181 if instance == 1 else 18182
        
        # Stop if running
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, 15)
                os.remove(pid_file)
            except (OSError, ValueError):
                pass
        
        import time
        time.sleep(1)
        
        # Kill any process on the port
        run_command(f'lsof -ti :{port} | xargs -r kill -9 2>/dev/null || true')
        time.sleep(1)
        
        # Start wireproxy
        log_file = os.path.join(LOG_DIR, f'wireproxy{instance}.log')
        cmd = f'nohup {os.path.join(BASE_DIR, "wireproxy")} -c {config_path} > {log_file} 2>&1 & echo $!'
        result = run_command(cmd)
        
        if result['success']:
            pid = result['stdout'].strip()
            with open(pid_file, 'w') as f:
                f.write(pid)
            
            # Trigger health monitor
            trigger_health_check()
            
            name = server.get('name', 'Unknown')
            return jsonify({
                'success': True,
                'message': f'Applied ProtonVPN {name} to Wireproxy {instance}',
                'server': server,
                'pid': pid
            })
        else:
            return jsonify({
                'success': False,
                'error': result['stderr']
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Tạo thư mục logs nếu chưa có
    os.makedirs(LOG_DIR, exist_ok=True)
    
    print("=" * 60)
    print("🌐 HAProxy & Wireproxy Web UI")
    print("=" * 60)
    print(f"📂 Base Directory: {BASE_DIR}")
    print(f"📝 Log Directory: {LOG_DIR}")
    print(f"🔧 Config Files:")
    print(f"   - Wireproxy 1: {WG1_CONF}")
    print(f"   - Wireproxy 2: {WG2_CONF}")
    print("=" * 60)
    print("🚀 Starting Web UI on http://0.0.0.0:5000")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=True)

