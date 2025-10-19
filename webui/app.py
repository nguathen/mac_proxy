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
    
    # Check status for each wireproxy
    for i, wp_config in enumerate(wireproxy_configs, 1):
        port = wp_config['port']
        conf = wp_config['config']
        pid_file = os.path.join(LOG_DIR, f'wireproxy{i}.pid')
        running = False
        pid = None
        
        # Try to get PID from file
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                    # Check if process is running
                    os.kill(pid, 0)
                    running = True
            except (OSError, ValueError):
                # PID file exists but process not running, clean up
                try:
                    os.remove(pid_file)
                except:
                    pass
        
        # If PID check failed, try to find process by port
        if not running:
            result = run_command(f'lsof -ti :{port}')
            if result['success'] and result['stdout'].strip():
                try:
                    pid = int(result['stdout'].strip().split('\n')[0])
                    # Verify it's wireproxy process
                    check = run_command(f'ps -p {pid} -o command=')
                    if check['success'] and 'wireproxy' in check['stdout']:
                        running = True
                        # Update PID file
                        try:
                            with open(pid_file, 'w') as f:
                                f.write(str(pid))
                        except:
                            pass
                except (ValueError, IndexError):
                    pass
        
        # Test connection
        connection_ok = False
        if running:
            result = run_command(f'curl -s --max-time 3 -x socks5h://127.0.0.1:{port} https://api.ipify.org')
            connection_ok = result['success'] and result['stdout'].strip()
        
        status['wireproxy'].append({
            'name': f'Wireproxy {i}',
            'port': port,
            'running': running,
            'pid': pid,
            'connection': connection_ok,
            'config': conf
        })
    
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
        
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                    os.kill(pid, 0)
                    running = True
            except (OSError, ValueError):
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
            result = run_command(f'curl -s --max-time 3 -x http://127.0.0.1:{port} https://api.ipify.org')
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
    pid_file = os.path.join(LOG_DIR, f'wireproxy{instance}.pid')
    
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
PersistentKeepalive = 25

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
    
    # Check for wireproxy logs (wireproxy1, wireproxy2, wireproxy3, ...)
    if service.startswith('wireproxy'):
        log_file = f'{service}.log'
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
        
        # Try to get private key from current config, otherwise use default
        private_key = None
        current_config = parse_wireproxy_config(config_path)
        if current_config and 'PrivateKey' in current_config.get('interface', {}):
            private_key = current_config['interface']['PrivateKey']
        
        # Generate new config with NordVPN server
        # If private_key is None, nordvpn_api will use DEFAULT_PRIVATE_KEY
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
        
        # Try to get private key from current config, otherwise use default
        private_key = None
        current_config = parse_wireproxy_config(config_path)
        if current_config and 'PrivateKey' in current_config.get('interface', {}):
            private_key = current_config['interface']['PrivateKey']
        
        # Generate new config with ProtonVPN server
        # If private_key is None, protonvpn_api will use DEFAULT_PRIVATE_KEY
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
