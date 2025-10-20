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
        'https_proxy': [],
        'timestamp': datetime.now().isoformat()
    }
    
    # Check wireproxy - auto-discover all wg*.conf files
    wireproxy_configs = []
    
    # Scan for all wg*.conf files
    import glob
    for conf_file in sorted(glob.glob(os.path.join(BASE_DIR, 'wg*.conf'))):
        # Extract port from config file
        try:
            with open(conf_file, 'r') as f:
                for line in f:
                    if 'BindAddress' in line:
                        # Extract port from "BindAddress = 127.0.0.1:18181"
                        port = line.split(':')[-1].strip()
                        wireproxy_configs.append({
                            'config': conf_file,
                            'port': port
                        })
                        break
        except Exception:
            pass
    
    # Check status for each wireproxy in parallel to avoid blocking
    def _probe_wireproxy(index_and_cfg):
        i, wp_config = index_and_cfg
        port = wp_config['port']
        conf = wp_config['config']
        pid_file = os.path.join(LOG_DIR, f'wireproxy_{port}.pid')
        running = False
        pid = None
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
                    if check['success'] and 'wireproxy' in check['stdout']:
                        running = True
                        try:
                            with open(pid_file, 'w') as f:
                                f.write(str(pid))
                        except Exception:
                            pass
                except (ValueError, IndexError):
                    pass
        connection_ok = False
        if running:
            result = run_command(f'curl -s --max-time 2 -x socks5h://127.0.0.1:{port} https://api.ipify.org')
            connection_ok = bool(result['success'] and result['stdout'].strip())
        return {
            'name': f'Wireproxy {i}',
            'port': port,
            'running': running,
            'pid': pid,
            'connection': connection_ok,
            'config': conf
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(wireproxy_configs)))) as executor:
        results = list(executor.map(_probe_wireproxy, enumerate(wireproxy_configs, 1)))
    status['wireproxy'].extend(results)
    
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
        
        # Get wireproxy port from HAProxy config
        haproxy_config = os.path.join(BASE_DIR, 'config', f'haproxy_{port}.cfg')
        if os.path.exists(haproxy_config):
            try:
                with open(haproxy_config, 'r') as f:
                    content = f.read()
                    import re
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
            'stats_url': f'http://127.0.0.1:{stats_port}/haproxy?stats'
        })
    
    # Check HTTPS Proxy
    for i, port in enumerate(['8181', '8182'], 1):
        pid_file = os.path.join(LOG_DIR, f'https_proxy_{port}.pid')
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
        
        # Test connection
        connection_ok = False
        if running:
            result = run_command(f'curl -s --max-time 2 -x http://127.0.0.1:{port} https://api.ipify.org')
            connection_ok = result['success'] and result['stdout'].strip()
        
        status['https_proxy'].append({
            'name': f'HTTPS Proxy {i}',
            'port': port,
            'running': running,
            'pid': pid,
            'connection': connection_ok
        })
    
    return jsonify(status)

@app.route('/api/wireproxy/config/<int:instance>')
def api_get_wireproxy_config(instance):
    """Lấy config wireproxy"""
    # Get all wireproxy configs
    import glob
    wireproxy_configs = []
    for conf_file in sorted(glob.glob(os.path.join(BASE_DIR, 'wg*.conf'))):
        try:
            with open(conf_file, 'r') as f:
                for line in f:
                    if 'BindAddress' in line:
                        port = line.split(':')[-1].strip()
                        wireproxy_configs.append({
                            'config': conf_file,
                            'port': port
                        })
                        break
        except Exception:
            pass
    
    # Validate instance
    if instance < 1 or instance > len(wireproxy_configs):
        return jsonify({
            'success': False, 
            'error': f'Invalid instance. Available instances: 1-{len(wireproxy_configs)}'
        }), 400
    
    # Get config path for this instance
    config_path = wireproxy_configs[instance - 1]['config']
    
    config = parse_wireproxy_config(config_path)
    if config:
        return jsonify({'success': True, 'config': config})
    else:
        return jsonify({'success': False, 'error': 'Cannot read config'}), 500

@app.route('/api/wireproxy/config/<int:instance>', methods=['POST'])
def api_save_wireproxy_config(instance):
    """Lưu config wireproxy"""
    data = request.json
    
    # Get all wireproxy configs
    import glob
    wireproxy_configs = []
    for conf_file in sorted(glob.glob(os.path.join(BASE_DIR, 'wg*.conf'))):
        try:
            with open(conf_file, 'r') as f:
                for line in f:
                    if 'BindAddress' in line:
                        port = line.split(':')[-1].strip()
                        wireproxy_configs.append({
                            'config': conf_file,
                            'port': port
                        })
                        break
        except Exception:
            pass
    
    # Validate instance
    if instance < 1 or instance > len(wireproxy_configs):
        return jsonify({
            'success': False, 
            'error': f'Invalid instance. Available instances: 1-{len(wireproxy_configs)}'
        }), 400
    
    # Get config path for this instance
    config_path = wireproxy_configs[instance - 1]['config']
    
    config = data.get('config')
    if not config:
        return jsonify({'success': False, 'error': 'No config provided'}), 400
    
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
    if action not in ['start', 'stop', 'restart']:
        return jsonify({'success': False, 'error': 'Invalid action'}), 400
    
    # Get all wireproxy configs
    import glob
    wireproxy_configs = []
    for conf_file in sorted(glob.glob(os.path.join(BASE_DIR, 'wg*.conf'))):
        try:
            with open(conf_file, 'r') as f:
                for line in f:
                    if 'BindAddress' in line:
                        port = line.split(':')[-1].strip()
                        wireproxy_configs.append({
                            'config': conf_file,
                            'port': port
                        })
                        break
        except Exception:
            pass
    
    # Validate instance
    if instance < 1 or instance > len(wireproxy_configs):
        return jsonify({
            'success': False, 
            'error': f'Invalid instance. Available instances: 1-{len(wireproxy_configs)}'
        }), 400
    
    # Get config and port for this instance
    config_file = wireproxy_configs[instance - 1]['config']
    port = wireproxy_configs[instance - 1]['port']
    # Enforce single PID file naming by port only
    pid_file_port = os.path.join(LOG_DIR, f'wireproxy_{port}.pid')
    
    if action == 'stop':
        # Stop wireproxy instance
        target_pid_file = pid_file_port if os.path.exists(pid_file_port) else None
        if target_pid_file:
            try:
                with open(target_pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, 15)  # SIGTERM
                try:
                    os.remove(pid_file_port)
                except Exception:
                    pass
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
        if os.path.exists(pid_file_port):
            try:
                with open(pid_file_port) as f:
                    pid = int(f.read().strip())
                os.kill(pid, 0)  # Check if process exists
                return jsonify({
                    'success': False,
                    'error': 'Wireproxy already running'
                }), 400
            except OSError:
                try:
                    os.remove(pid_file_port)
                except Exception:
                    pass
        
        # Kill any process on the port
        run_command(f'lsof -ti :{port} | xargs -r kill -9 2>/dev/null || true')
        
        # Start wireproxy
        # Enforce single LOG naming by port only
        log_file_port = os.path.join(LOG_DIR, f'wireproxy_{port}.log')
        cmd = f'nohup {os.path.join(BASE_DIR, "wireproxy")} -c {config_file} > {log_file_port} 2>&1 & echo $!'
        result = run_command(cmd)
        
        if result['success']:
            pid = result['stdout'].strip()
            try:
                with open(pid_file_port, 'w') as f:
                    f.write(pid)
            except Exception:
                pass
            
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
        target_pid_file = pid_file_port if os.path.exists(pid_file_port) else None
        if target_pid_file:
            try:
                with open(target_pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, 15)
                try:
                    os.remove(pid_file_port)
                except Exception:
                    pass
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
            pid_file = os.path.join(LOG_DIR, f'wireproxy{instance}.pid')
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
        
        # Auto-create Wireproxy config files for ports that don't exist
        if wg_ports:
            for port in wg_ports:
                wg_conf_file = os.path.join(BASE_DIR, f'wg{port}.conf')
                if not os.path.exists(wg_conf_file):
                    # Create default Wireproxy config
                    default_config = f"""[Interface]
PrivateKey = ECDeW1Oi8TC5reUZcyp8n3KAOaDVz3ZXZB5tu1+8Ik4=
Address = 10.5.0.2/16
DNS = 103.86.96.100

[Peer]
PublicKey = aUuKVXQ//4UnXcPOqai/qGTfUK6qrdNRa6crPCF32x4=
Endpoint = 185.153.177.126:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 15

[Socks5]
BindAddress = 127.0.0.1:{port}
"""
                    try:
                        with open(wg_conf_file, 'w') as f:
                            f.write(default_config)
                    except Exception as e:
                        # Log error but continue
                        pass
        
        # Build WireGuard servers config
        wg_servers = ""
        if wg_ports:
            for i, port in enumerate(wg_ports, 1):
                if i == 1:
                    wg_servers += f"    server wg{i} 127.0.0.1:{port} check inter 1s rise 1 fall 2 on-error fastinter\n"
                else:
                    wg_servers += f"    server wg{i} 127.0.0.1:{port} check inter 1s rise 1 fall 2 on-error fastinter backup\n"
        
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
{wg_servers}    server cloudflare_warp 127.0.0.1:8111 check inter 1s rise 1 fall 2 on-error fastinter backup

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
        
        # Start the HAProxy instance using setup_haproxy.sh in background
        wg_ports_str = ','.join(map(str, wg_ports)) if wg_ports else '18181'
        log_file = os.path.join(LOG_DIR, f'haproxy_health_{sock_port}.log')
        
        # Run setup_haproxy.sh in background using nohup
        cmd = f'nohup bash setup_haproxy.sh --sock-port {sock_port} --stats-port {stats_port} --wg-ports {wg_ports_str} --daemon > {log_file} 2>&1 &'
        result = run_command(cmd)
        
        if result['success'] or result['returncode'] == 0:
            # Give it a moment to start
            import time
            time.sleep(2)
            
            # Verify HAProxy started
            pid_file = os.path.join(LOG_DIR, f'haproxy_{sock_port}.pid')
            if os.path.exists(pid_file):
                try:
                    with open(pid_file) as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 0)  # Check if process exists
                    
                    return jsonify({
                        'success': True,
                        'message': f'HAProxy service created on port {sock_port}',
                        'service': {
                            'sock_port': sock_port,
                            'stats_port': stats_port,
                            'wg_ports': wg_ports
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
                os.kill(pid, 15)  # SIGTERM
                os.remove(pid_file)
            except (OSError, ValueError):
                pass
        
        # Stop health monitor
        if os.path.exists(health_pid_file):
            try:
                with open(health_pid_file) as f:
                    pid = int(f.read().strip())
                os.kill(pid, 15)  # SIGTERM
                os.remove(health_pid_file)
            except (OSError, ValueError):
                pass
        
        # Remove config file
        config_file = os.path.join(BASE_DIR, 'config', f'haproxy_{port}.cfg')
        if os.path.exists(config_file):
            os.remove(config_file)
        
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

@app.route('/api/wireproxy/delete/<int:instance>', methods=['DELETE'])
def api_wireproxy_delete(instance):
    """Xóa Wireproxy instance"""
    try:
        # Get all wireproxy configs
        import glob
        wireproxy_configs = []
        for conf_file in sorted(glob.glob(os.path.join(BASE_DIR, 'wg*.conf'))):
            try:
                with open(conf_file, 'r') as f:
                    for line in f:
                        if 'BindAddress' in line:
                            port = line.split(':')[-1].strip()
                            wireproxy_configs.append({
                                'config': conf_file,
                                'port': port
                            })
                            break
            except Exception:
                pass
        
        # Validate instance
        if instance < 1 or instance > len(wireproxy_configs):
            return jsonify({
                'success': False, 
                'error': f'Invalid instance. Available instances: 1-{len(wireproxy_configs)}'
            }), 400
        
        # Get config and port for this instance
        config_file = wireproxy_configs[instance - 1]['config']
        port = wireproxy_configs[instance - 1]['port']
        
        # Stop the service first if running
        pid_file = os.path.join(LOG_DIR, f'wireproxy{instance}.pid')
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
        if os.path.exists(config_file):
            os.remove(config_file)
        
        # Clean up log files
        log_file = os.path.join(LOG_DIR, f'wireproxy{instance}.log')
        if os.path.exists(log_file):
            os.remove(log_file)
        
        return jsonify({
            'success': True,
            'message': f'Wireproxy {instance} (port {port}) deleted successfully'
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

@app.route('/api/manage_https_proxy/<action>', methods=['POST'])
def api_https_proxy_action(action):
    """Điều khiển HTTPS Proxy (start/stop/restart)"""
    if action not in ['start', 'stop', 'restart']:
        return jsonify({'success': False, 'error': 'Invalid action'}), 400
    
    result = run_command(f'bash manage_https_proxy.sh {action}')
    
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
    
    # Check for wireproxy logs (wireproxy18181, wireproxy18182, etc.)
    if service.startswith('wireproxy'):
        # Extract port number from service name (e.g., wireproxy18183 -> 18183)
        port = service.replace('wireproxy', '')
        # Map port to instance number for new format
        port_to_instance = {
            '18181': '1', '18182': '2', '18183': '3', 
            '18184': '4', '18185': '5', '18186': '6'
        }
        instance = port_to_instance.get(port, port)
        new_log_file = f'wireproxy{instance}.log'
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
    # Check for haproxy logs (haproxy1, haproxy2, ...)
    elif service.startswith('haproxy'):
        # Extract instance number
        instance_num = service.replace('haproxy', '')
        if instance_num.isdigit():
            # Map to port-based log file
            port_map = {'1': '7891', '2': '7892', '3': '7893', '4': '7894', '5': '7895'}
            port = port_map.get(instance_num, f'789{instance_num}')
            log_file = f'haproxy_health_{port}.log'
    # Check for HTTPS proxy logs
    elif service.startswith('https_proxy_'):
        log_file = f'{service}.log'
    
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
        data = request.json
        server_name = data.get('server_name')
        
        if not server_name:
            return jsonify({'success': False, 'error': 'No server name provided'}), 400
        
        # Get server info
        server = nordvpn_api.get_server_by_name(server_name)
        if not server:
            return jsonify({'success': False, 'error': 'Server not found'}), 404
        
        # Get all wireproxy configs
        import glob
        wireproxy_configs = []
        for conf_file in sorted(glob.glob(os.path.join(BASE_DIR, 'wg*.conf'))):
            try:
                with open(conf_file, 'r') as f:
                    for line in f:
                        if 'BindAddress' in line:
                            port = line.split(':')[-1].strip()
                            wireproxy_configs.append({
                                'config': conf_file,
                                'port': port
                            })
                            break
            except Exception:
                pass
        
        # Validate instance
        if instance < 1 or instance > len(wireproxy_configs):
            return jsonify({
                'success': False, 
                'error': f'Invalid instance. Available instances: 1-{len(wireproxy_configs)}'
            }), 400
        
        # Get config path for this instance
        config_path = wireproxy_configs[instance - 1]['config']
        port = wireproxy_configs[instance - 1]['port']
        
        # Use NordVPN private key (always use default for NordVPN)
        # NordVPN requires provider-specific key, don't reuse from config
        from nordvpn_api import DEFAULT_PRIVATE_KEY as NORDVPN_PRIVATE_KEY
        private_key = NORDVPN_PRIVATE_KEY
        
        # Generate new config with NordVPN server
        bind_address = f"127.0.0.1:{port}"
        new_config = nordvpn_api.generate_wireguard_config(
            server=server,
            private_key=private_key,
            bind_address=bind_address
        )
        
        # Save new config
        if not save_wireproxy_config(config_path, new_config):
            return jsonify({
                'success': False,
                'error': 'Failed to save config'
            }), 500
        
        # Restart wireproxy instance
        pid_file = os.path.join(LOG_DIR, f'wireproxy{instance}.pid')
        
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
                'message': f'Applied NordVPN server {server["name"]} to Wireproxy {instance} (port {port})',
                'server': server,
                'pid': pid,
                'port': port
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

@app.route('/api/protonvpn/apply/https/<int:instance>', methods=['POST'])
def api_protonvpn_apply_https_proxy(instance):
    """Áp dụng ProtonVPN server vào HTTPS Proxy instance"""
    try:
        if not protonvpn_api:
            return jsonify({'success': False, 'error': 'ProtonVPN API not configured'}), 400
        
        # Validate instance (HTTPS proxy typically has 1-2 instances, but we check dynamically)
        # For now, we support instances 1 and 2 for HTTPS proxy
        if instance not in [1, 2]:
            return jsonify({'success': False, 'error': 'Invalid instance. HTTPS Proxy supports instances 1-2'}), 400
        
        data = request.json
        server_name = data.get('server_name')
        
        if not server_name:
            return jsonify({'success': False, 'error': 'No server_name provided'}), 400
        
        # Get server info
        server = protonvpn_api.get_server_by_name(server_name)
        if not server:
            return jsonify({'success': False, 'error': 'Server not found'}), 404
        
        # Get proxy credentials from API
        try:
            creds_response = requests.get('http://localhost:5267/mmo/getpassproxy', timeout=5)
            if creds_response.status_code == 200:
                try:
                    creds_data = creds_response.json()
                    proxy_username = creds_data.get('username', '')
                    proxy_password = creds_data.get('password', '')
                    
                    if not proxy_username or not proxy_password:
                        return jsonify({
                            'success': False,
                            'error': 'API returned empty username or password'
                        }), 500
                except ValueError:
                    # API trả về plain text: username:password
                    response_text = creds_response.text.strip()
                    if ':' in response_text:
                        parts = response_text.split(':', 1)
                        proxy_username = parts[0]
                        proxy_password = parts[1]
                    else:
                        return jsonify({
                            'success': False,
                            'error': f'Invalid credentials format: {response_text[:100]}'
                        }), 500
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to get credentials: HTTP {creds_response.status_code}'
                }), 500
        except requests.exceptions.RequestException as e:
            return jsonify({
                'success': False,
                'error': f'Cannot connect to credentials API: {str(e)}'
            }), 500
        
        # Get domain from physical servers
        servers_list = server.get('servers', [])
        if not servers_list:
            return jsonify({
                'success': False,
                'error': f"Server {server.get('name')} has no physical servers data"
            }), 404
        
        # Get domain and label from first physical server
        first_server = servers_list[0]
        server_domain = first_server.get('domain')
        if not server_domain:
            return jsonify({
                'success': False,
                'error': 'Server domain not found'
            }), 404
        
        # Get label for port calculation
        label_str = first_server.get('label')
        if label_str is None:
            return jsonify({
                'success': False,
                'error': 'Server label not found'
            }), 404
        
        try:
            label = int(label_str)
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'error': f'Invalid label: {label_str}'
            }), 404
        
        proxy_port = 4443 + label  # Calculate port: 4443 + label
        
        # Configure HTTPS proxy (Python wrapper)
        https_port = 8181 if instance == 1 else 8182
        pid_file = os.path.join(LOG_DIR, f'https_proxy_{https_port}.pid')
        
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
        run_command(f'lsof -ti :{https_port} | xargs kill -9 2>/dev/null || true')
        time.sleep(1)
        
        # Start Python proxy wrapper with DOMAIN
        stdout_log = os.path.join(LOG_DIR, f'https_proxy_{https_port}_stdout.log')
        proxy_wrapper = os.path.join(BASE_DIR, 'https_proxy_wrapper.py')
        
        cmd = f'nohup python3 {proxy_wrapper} --port {https_port} --upstream-host {server_domain} --upstream-port {proxy_port} --upstream-user "{proxy_username}" --upstream-pass "{proxy_password}" > {stdout_log} 2>&1 & echo $!'
        result = run_command(cmd)
        
        if result['success']:
            pid = result['stdout'].strip()
            with open(pid_file, 'w') as f:
                f.write(pid)
            
            name = server.get('name', 'Unknown')
            return jsonify({
                'success': True,
                'message': f'Applied ProtonVPN {name} to HTTPS Proxy {instance}',
                'server': server,
                'proxy_config': {
                    'host': server_domain,
                    'port': proxy_port,
                    'local_port': https_port,
                    'username': proxy_username[:20] + '...'
                },
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

@app.route('/api/protonvpn/apply/<int:instance>', methods=['POST'])
def api_protonvpn_apply_server(instance):
    """Áp dụng ProtonVPN server vào Wireproxy instance"""
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
        
        # Get all wireproxy configs
        import glob
        wireproxy_configs = []
        for conf_file in sorted(glob.glob(os.path.join(BASE_DIR, 'wg*.conf'))):
            try:
                with open(conf_file, 'r') as f:
                    for line in f:
                        if 'BindAddress' in line:
                            port = line.split(':')[-1].strip()
                            wireproxy_configs.append({
                                'config': conf_file,
                                'port': port
                            })
                            break
            except Exception:
                pass
        
        # Validate instance
        if instance < 1 or instance > len(wireproxy_configs):
            return jsonify({
                'success': False, 
                'error': f'Invalid instance. Available instances: 1-{len(wireproxy_configs)}'
            }), 400
        
        # Get config path for this instance
        config_path = wireproxy_configs[instance - 1]['config']
        port = wireproxy_configs[instance - 1]['port']
        
        # Use ProtonVPN private key (always use default for ProtonVPN)
        # ProtonVPN requires provider-specific key, don't reuse from config
        from protonvpn_api import DEFAULT_PRIVATE_KEY as PROTONVPN_PRIVATE_KEY
        private_key = PROTONVPN_PRIVATE_KEY
        
        # Generate new config with ProtonVPN server
        bind_address = f"127.0.0.1:{port}"
        new_config = protonvpn_api.generate_wireguard_config(
            server=server,
            private_key=private_key,
            bind_address=bind_address
        )
        
        # Save new config
        if not save_wireproxy_config(config_path, new_config):
            return jsonify({
                'success': False,
                'error': 'Failed to save config'
            }), 500
        
        # Restart wireproxy instance
        pid_file = os.path.join(LOG_DIR, f'wireproxy{instance}.pid')
        
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
                'message': f'Applied ProtonVPN {name} to Wireproxy {instance} (port {port})',
                'server': server,
                'pid': pid,
                'port': port
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
        
        # Parse proxy_check: "socks5://server:PORT:SERVER_NAME:"
        if not proxy_check or not proxy_check.startswith('socks5://'):
            return jsonify({
                'success': False,
                'error': 'Invalid proxy_check format. Expected: socks5://server:PORT:SERVER_NAME:'
            }), 400
        
        # Extract components from proxy_check
        proxy_parts = proxy_check.replace('socks5://', '').rstrip(':').split(':')
        if len(proxy_parts) < 3:
            return jsonify({
                'success': False,
                'error': 'Invalid proxy_check format. Expected: socks5://server:PORT:SERVER_NAME:'
            }), 400
        
        check_port = proxy_parts[1]
        check_server = proxy_parts[2]
        
        # Determine VPN provider from server name
        if 'nordvpn' in check_server.lower():
            vpn_provider = 'nordvpn'
        elif 'protonvpn' in check_server.lower():
            vpn_provider = 'protonvpn'
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
                # Parse: "127.0.0.1:PORT:SERVER_NAME" or "127.0.0.1:PORT"
                parts = proxy_str.split(':')
                if len(parts) >= 2:
                    profile_port = parts[1]
                    profile_server = parts[2] if len(parts) >= 3 else ''
                    
                    # Case 1: Exact match - proxy_check matches existing profile
                    if profile_port == check_port and profile_server == check_server:
                        exact_match_found = True
                        break
                    
                    # Case 2: Same port but different server
                    if profile_port == check_port and profile_server != check_server:
                        port_in_use_by_other_server = True
                        break
        
        # Case 1: Exact match found
        if exact_match_found:
            return jsonify({
                'success': True,
                'message': 'Proxy already in use by another profile',
                'proxy_check': f'socks5://127.0.0.1:{check_port}:{check_server}:',
                'data': profiles_data,
                'action': 'use_existing'
            })
        
        # Case 2: Port in use with different server - try to reuse available HAProxy first
        if port_in_use_by_other_server:
            # First, try to find an available HAProxy that's not in the profiles list
            available_haproxy = _find_available_haproxy(profiles, check_server, vpn_provider)
            if available_haproxy:
                return jsonify({
                    'success': True,
                    'message': f'Reused available HAProxy on port {available_haproxy["port"]} with server {check_server}',
                    'proxy_check': f'socks5://127.0.0.1:{available_haproxy["port"]}:{check_server}:',
                    'data': profiles_data,
                    'action': 'reused_available',
                    'port': available_haproxy["port"],
                    'server': check_server,
                    'old_server': available_haproxy.get('old_server')
                })
            
            # If no available HAProxy found, create new one
            # Find next available port by checking actual HAProxy configs
            existing_ports = set()
            
            # Check profiles first
            for profile in profiles:
                if profile.get('proxy'):
                    parts = profile['proxy'].split(':')
                    if len(parts) >= 2:
                        existing_ports.add(int(parts[1]))
            
            # Check actual HAProxy config files
            import glob
            for cfg_file in glob.glob(os.path.join(BASE_DIR, 'config', 'haproxy_*.cfg')):
                try:
                    port = int(cfg_file.split('_')[-1].replace('.cfg', ''))
                    existing_ports.add(port)
                except (ValueError, IndexError):
                    pass
            
            # Find next available port starting from 7891 with proper mapping
            new_port = 7891
            while new_port in existing_ports or new_port == int(check_port):
                new_port += 1
                if new_port > 7999:  # Safety limit
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
            
            # Create new HAProxy instance
            result = _create_haproxy_with_server(new_port, check_server, vpn_provider)
            if not result['success']:
                return jsonify({
                    'success': False,
                    'error': result['error']
                }), 500
            
            return jsonify({
                'success': True,
                'message': f'Created new HAProxy on port {new_port} with server {check_server}',
                'proxy_check': f'socks5://127.0.0.1:{new_port}:{check_server}:',
                'data': profiles_data,
                'action': 'created_new',
                'port': new_port,
                'server': check_server
            })
        
        # Case 3: Port not in use - check if HAProxy exists and matches server
        haproxy_config = os.path.join(BASE_DIR, 'config', f'haproxy_{check_port}.cfg')
        
        if os.path.exists(haproxy_config):
            # Check if server matches
            current_server = _get_server_from_haproxy_config(haproxy_config)
            
            if current_server and current_server != check_server:
                # Server mismatch - reconfigure
                result = _reconfigure_haproxy_with_server(check_port, check_server, vpn_provider)
                if not result['success']:
                    return jsonify({
                        'success': False,
                        'error': result['error']
                    }), 500
                
                return jsonify({
                    'success': True,
                    'message': f'Reconfigured HAProxy port {check_port} with server {check_server}',
                    'proxy_check': f'socks5://127.0.0.1:{check_port}:{check_server}:',
                    'data': profiles_data,
                    'action': 'reconfigured',
                    'old_server': current_server,
                    'new_server': check_server
                })
            elif current_server == check_server:
                # Server matches - just return
                return jsonify({
                    'success': True,
                    'message': 'HAProxy already configured correctly',
                    'proxy_check': f'socks5://127.0.0.1:{check_port}:{check_server}:',
                    'data': profiles_data,
                    'action': 'already_configured'
                })
        
        # HAProxy doesn't exist - create new
        result = _create_haproxy_with_server(check_port, check_server, vpn_provider)
        if not result['success']:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
        
        return jsonify({
            'success': True,
            'message': f'Created new HAProxy on port {check_port} with server {check_server}',
            'proxy_check': f'socks5://127.0.0.1:{check_port}:{check_server}:',
            'data': profiles_data,
            'action': 'created_new',
            'port': check_port,
            'server': check_server
        })
        
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
        
        # Find next available port starting from 7891
        fallback_port = 7891
        while fallback_port in existing_ports or fallback_port == original_port:
            fallback_port += 1
            if fallback_port > 7999:  # Safety limit
                return None
        
        # If original port is 7891, start from 7892 to avoid conflict
        if original_port == 7891:
            fallback_port = 7892
            while fallback_port in existing_ports:
                fallback_port += 1
                if fallback_port > 7999:
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
                parts = profile['proxy'].split(':')
                if len(parts) >= 2:
                    try:
                        profile_ports.add(int(parts[1]))
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
                # ProtonVPN: node-am-01.protonvpn.net -> am (split by '-' and take [1])
                parts = server_name.split('.')
                if parts:
                    first_part = parts[0]
                    dash_parts = first_part.split('-')
                    if len(dash_parts) >= 2:
                        country_code = dash_parts[1].upper()
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
            }
            
            # Map country code if needed
            mapped_country = country_mappings.get(country_code, country_code)
            
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
                            continue  # Skip duplicate
                            
                        # Get servers by country
                        servers = api.get_servers_by_country(test_country)
                        if servers:
                            # Random select a server
                            selected_server = random.choice(servers)
                            server_name = selected_server['name']
                            
                            # Find available port for fallback
                            fallback_port = _find_available_port_for_fallback(port)
                            if fallback_port:
                                # Create HAProxy with the selected server (avoid recursion)
                                result = _create_haproxy_with_server_direct(fallback_port, server_name, vpn_provider)
                                if result['success']:
                                    result['fallback_info'] = {
                                        'original_server': server_name,
                                        'country_code': test_country,
                                        'vpn_provider': vpn_provider,
                                        'reason': 'country_match',
                                        'fallback_port': fallback_port
                                    }
                                    return result
                                else:
                                    # If port conflict, try next port
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
                    server_name = selected_server['name']
                    
                    # Find available port for fallback
                    fallback_port = _find_available_port_for_fallback(port)
                    if fallback_port:
                        # Create HAProxy with the selected server (avoid recursion)
                        result = _create_haproxy_with_server_direct(fallback_port, server_name, vpn_provider)
                        if result['success']:
                            result['fallback_info'] = {
                                'original_server': server_name,
                                'country_code': country_code,
                                'vpn_provider': vpn_provider,
                                'reason': 'random_fallback',
                                'fallback_port': fallback_port
                            }
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
    """Tạo HAProxy instance mới với server cụ thể (không có fallback logic)"""
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
    """Tạo HAProxy instance mới với server cụ thể"""
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
            # Server not found - try fallback logic
            fallback_result = _handle_server_not_found(server_name, vpn_provider, port)
            if fallback_result['success']:
                return fallback_result
            else:
                return {'success': False, 'error': f'Server {server_name} not found and fallback failed: {fallback_result["error"]}'}
        
        # Continue with implementation
        return _create_haproxy_with_server_impl(port, server_name, vpn_provider, server, private_key)
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def _create_haproxy_with_server_impl(port, server_name, vpn_provider, server, private_key):
    """Implementation chung cho việc tạo HAProxy với server"""
    try:
        # Calculate wireproxy port based on HAProxy port mapping
        # HAProxy port 7891 -> Wireproxy port 18181
        # HAProxy port 7892 -> Wireproxy port 18182
        # HAProxy port 7893 -> Wireproxy port 18183
        # Formula: wireproxy_port = 18181 + (haproxy_port - 7891)
        try:
            haproxy_port_num = int(port)
            wireproxy_port = 18181 + (haproxy_port_num - 7891)
            
            # Validate port range
            if wireproxy_port < 18181 or wireproxy_port > 18999:
                return {'success': False, 'error': f'Invalid port mapping: HAProxy {port} -> Wireproxy {wireproxy_port} (range: 18181-18999)'}
                
        except ValueError:
            return {'success': False, 'error': f'Invalid HAProxy port: {port}'}
        
        # Check if wireproxy port is already in use by another HAProxy
        import glob
        for cfg_file in glob.glob(os.path.join(BASE_DIR, 'config', 'haproxy_*.cfg')):
            try:
                with open(cfg_file, 'r') as f:
                    content = f.read()
                    import re
                    # Find wireproxy port in HAProxy config
                    match = re.search(r'server\s+wg\d+\s+127\.0\.0\.1:(\d+)', content)
                    if match:
                        existing_wp_port = int(match.group(1))
                        if existing_wp_port == wireproxy_port:
                            # This wireproxy port is already used by another HAProxy
                            return {'success': False, 'error': f'Wireproxy port {wireproxy_port} is already used by another HAProxy. Port mapping conflict.'}
            except Exception:
                pass
        
        # Get API instance
        if vpn_provider == 'nordvpn':
            api = nordvpn_api
        elif vpn_provider == 'protonvpn':
            api = protonvpn_api
        else:
            return {'success': False, 'error': f'Unknown VPN provider: {vpn_provider}'}
        
        # Create wireproxy config
        wireproxy_config_path = os.path.join(BASE_DIR, f'wg{wireproxy_port}.conf')
        bind_address = f'127.0.0.1:{wireproxy_port}'
        
        wireproxy_config = api.generate_wireguard_config(
            server=server,
            private_key=private_key,
            bind_address=bind_address
        )
        
        # Save wireproxy config
        if not save_wireproxy_config(wireproxy_config_path, wireproxy_config):
            return {'success': False, 'error': 'Failed to save wireproxy config'}
        
        # Start wireproxy with verification and logging
        os.makedirs(LOG_DIR, exist_ok=True)
        wireproxy_bin = os.path.join(BASE_DIR, 'wireproxy')
        wireproxy_pid_file = os.path.join(LOG_DIR, f'wireproxy_{wireproxy_port}.pid')
        wireproxy_log_file = os.path.join(LOG_DIR, f'wireproxy_{wireproxy_port}.log')

        def _start_and_verify_wireproxy():
            cmd_local = f'nohup {wireproxy_bin} -c {wireproxy_config_path} > {wireproxy_log_file} 2>&1 & echo $!'
            res = run_command(cmd_local)
            if not res['success']:
                return {'ok': False, 'error': res['stderr']}
            pid_str = res['stdout'].strip()
            try:
                with open(wireproxy_pid_file, 'w') as fp:
                    fp.write(pid_str)
            except Exception:
                pass

            # poll readiness: pid alive and port listening (LISTEN state only)
            import time
            for _ in range(40):  # ~20s max
                time.sleep(0.5)
                # check pid
                try:
                    os.kill(int(pid_str), 0)
                    pid_ok = True
                except Exception:
                    pid_ok = False
                # check port listening
                port_check = run_command(f'lsof -tiTCP:LISTEN -i :{wireproxy_port}')
                port_ok = bool(port_check['success'] and port_check['stdout'].strip())
                if pid_ok or port_ok:
                    return {'ok': True, 'pid': pid_str}
            return {'ok': False, 'error': 'wireproxy not listening'}

        start_try = _start_and_verify_wireproxy()
        if not start_try['ok']:
            # retry once
            start_try = _start_and_verify_wireproxy()
        if not start_try['ok']:
            return {'success': False, 'error': f'Failed to start wireproxy on {wireproxy_port}: {start_try.get("error", "unknown error")}'}
        
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
        stats_port = 8000 + int(port) - 7890  # 7891 -> 8091, 7892 -> 8092, etc
        
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
    server wg1 127.0.0.1:{wireproxy_port} check inter 1s rise 1 fall 2 on-error fastinter
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
            # Cleanup wireproxy if HAProxy fails
            try:
                os.kill(int(wireproxy_pid), 15)
                os.remove(wireproxy_pid_file)
                os.remove(wireproxy_config_path)
            except Exception:
                pass
            return {'success': False, 'error': f'Failed to start HAProxy: {result["stderr"]}'}
        
        # Start health monitor
        _start_health_monitor(port, [wireproxy_port])
        
        return {'success': True, 'port': port, 'server': server_name, 'wireproxy_port': wireproxy_port}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def _reconfigure_haproxy_with_server(port, server_name, vpn_provider):
    """Reconfigure existing HAProxy với server mới"""
    try:
        # Find associated wireproxy
        haproxy_config_path = os.path.join(BASE_DIR, 'config', f'haproxy_{port}.cfg')
        wireproxy_port = None
        wireproxy_config_path = None
        
        if os.path.exists(haproxy_config_path):
            with open(haproxy_config_path, 'r') as f:
                content = f.read()
                import re
                match = re.search(r'server\s+wg\d+\s+127\.0\.0\.1:(\d+)', content)
                if match:
                    wireproxy_port = match.group(1)
                    
                    # Find wireproxy config
                    import glob
                    for conf_file in glob.glob(os.path.join(BASE_DIR, 'wg*.conf')):
                        try:
                            with open(conf_file, 'r') as f:
                                if f'BindAddress = 127.0.0.1:{wireproxy_port}' in f.read():
                                    wireproxy_config_path = conf_file
                                    break
                        except Exception:
                            continue
        
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
        
        # Stop and reconfigure wireproxy if found
        if wireproxy_port and wireproxy_config_path:
            # Stop wireproxy
            wireproxy_pid_file = os.path.join(LOG_DIR, f'wireproxy_{wireproxy_port}.pid')
            if os.path.exists(wireproxy_pid_file):
                try:
                    with open(wireproxy_pid_file, 'r') as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 15)
                    os.remove(wireproxy_pid_file)
                except Exception:
                    pass
            
            # Update wireproxy config with new server
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
            
            server = api.get_server_by_name(server_name)
            if not server:
                # Server not found - try fallback logic
                fallback_result = _handle_server_not_found(server_name, vpn_provider, port)
                if fallback_result['success']:
                    return fallback_result
                else:
                    return {'success': False, 'error': f'Server {server_name} not found and fallback failed: {fallback_result["error"]}'}
            
            bind_address = f'127.0.0.1:{wireproxy_port}'
            wireproxy_config = api.generate_wireguard_config(
                server=server,
                private_key=private_key,
                bind_address=bind_address
            )
            
            # Save wireproxy config
            if not save_wireproxy_config(wireproxy_config_path, wireproxy_config):
                return {'success': False, 'error': 'Failed to save wireproxy config'}
            
            # Restart wireproxy with verification (no symlinks; single source of truth)
            wireproxy_bin = os.path.join(BASE_DIR, 'wireproxy')
            wireproxy_log_file = os.path.join(LOG_DIR, f'wireproxy_{wireproxy_port}.log')

            def _restart_and_verify_wireproxy():
                res = run_command(f'nohup {wireproxy_bin} -c {wireproxy_config_path} > {wireproxy_log_file} 2>&1 & echo $!')
                if not res['success']:
                    return {'ok': False, 'error': res['stderr']}
                pid_str = res['stdout'].strip()
                try:
                    with open(wireproxy_pid_file, 'w') as fp:
                        fp.write(pid_str)
                except Exception:
                    pass

            # Verify process/port becomes healthy
            import time
            for _ in range(40):  # ~20s max
                time.sleep(0.5)
                try:
                    os.kill(int(pid_str), 0)
                    pid_ok = True
                except Exception:
                    pid_ok = False
                port_check = run_command(f'lsof -tiTCP:LISTEN -i :{wireproxy_port}')
                port_ok = bool(port_check['success'] and port_check['stdout'].strip())
                if pid_ok or port_ok:
                    return {'ok': True, 'pid': pid_str}
            return {'ok': False, 'error': 'wireproxy not listening'}

            verify_res = _restart_and_verify_wireproxy()
            if not verify_res['ok']:
                verify_res = _restart_and_verify_wireproxy()
            if not verify_res['ok']:
                return {'success': False, 'error': f'Failed to restart wireproxy {wireproxy_port}: {verify_res.get("error", "unknown error") }'}
        
        # Restart HAProxy
        try:
            haproxy_bin = subprocess.check_output(['which', 'haproxy'], text=True).strip()
        except Exception:
            haproxy_bin = '/opt/homebrew/sbin/haproxy'
        
        cmd = f'{haproxy_bin} -f {haproxy_config_path} -p {pid_file} -D'
        result = run_command(cmd)
        
        if not result['success']:
            return {'success': False, 'error': f'Failed to start HAProxy: {result["stderr"]}'}
        
        # Restart health monitor
        if wireproxy_port:
            _start_health_monitor(port, [wireproxy_port])
        
        return {'success': True, 'port': port, 'server': server_name}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def _start_health_monitor(haproxy_port, wireproxy_ports):
    """Start health monitor for HAProxy instance"""
    try:
        script_path = os.path.join(BASE_DIR, 'setup_haproxy.sh')
        cmd = f'{script_path} --sock-port {haproxy_port} --stats-port {8000 + int(haproxy_port) - 7890} --wg-ports {",".join(map(str, wireproxy_ports))} --daemon'
        
        # Run in background
        subprocess.Popen(cmd, shell=True, cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        return True
    except Exception:
        return False

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
