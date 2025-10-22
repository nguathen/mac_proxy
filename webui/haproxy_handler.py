"""
HAProxy Handler
Xử lý các API endpoints liên quan đến HAProxy
"""

from flask import request, jsonify
import os
import json
import sys
import re
from datetime import datetime

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def register_haproxy_routes(app, BASE_DIR, LOG_DIR, run_command, get_available_haproxy_ports, get_available_gost_ports):
    """Đăng ký các routes HAProxy với Flask app"""
    
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
            host_proxy = data.get('host_proxy', '127.0.0.1:8111')
            stats_auth = data.get('stats_auth', 'admin:admin123')
            health_interval = data.get('health_interval', 10)
            
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
                        # Create default Gost config with ProtonVPN
                        # Get random ProtonVPN server
                        server_domain = 'node-uk-29.protonvpn.net'
                        proxy_url = 'socks5://127.0.0.1:8111'  # Default fallback
                        
                        try:
                            from protonvpn_api import ProtonVPNAPI
                            protonvpn_api = ProtonVPNAPI()
                            servers = protonvpn_api.fetch_servers()
                            if servers:
                                import random
                                random.shuffle(servers)
                                selected_server = servers[0]
                                server_domain = selected_server.get('domain', 'node-uk-29.protonvpn.net')
                                proxy_url = protonvpn_api.get_proxy_url(selected_server)
                                print(f"Selected ProtonVPN server: {server_domain}")
                        except Exception as e:
                            print(f"Failed to get ProtonVPN server, using fallback: {e}")
                            # Keep default values
                        
                        default_config = {
                            "port": str(port),
                            "provider": "protonvpn",
                            "country": server_domain,
                            "proxy_url": proxy_url,
                            "created_at": datetime.now().isoformat()
                        }
                        try:
                            with open(gost_config_file, 'w') as f:
                                json.dump(default_config, f, indent=4)
                        except Exception as e:
                            # Log error but continue
                            pass
            
            # Build Gost servers config
            gost_servers = []
            for port in wg_ports:
                gost_servers.append(f"127.0.0.1:{port}")
            
            # Create HAProxy config
            config_content = f"""global
    daemon
    user haproxy
    group haproxy
    log stdout local0
    chroot /var/lib/haproxy
    stats socket /var/run/haproxy.sock mode 660 level admin
    stats timeout 30s
    pidfile /var/run/haproxy.pid

defaults
    mode tcp
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms
    option tcplog
    log global

# Stats interface
listen stats_{sock_port}
    bind 0.0.0.0:{stats_port}
    mode http
    stats enable
    stats uri /
    stats refresh 5s
    stats show-legends
    stats show-node

# Main proxy
listen proxy_{sock_port}
    bind 0.0.0.0:{sock_port}
    mode tcp
    balance roundrobin
    option tcp-check
    tcp-check connect port 80
    tcp-check send-binary 474554202f20485454502f312e310d0a486f73743a206578616d706c652e636f6d0d0a0d0a
    tcp-check expect binary 485454502f
    default-server inter 3s fall 3 rise 2
"""
            
            # Add Gost servers
            for i, server in enumerate(gost_servers):
                config_content += f"    server gost{i+1} {server} check\n"
            
            # Write config file
            with open(config_file, 'w') as f:
                f.write(config_content)
            
            # Start Gost services first
            for port in wg_ports:
                gost_config_file = os.path.join(BASE_DIR, 'config', f'gost_{port}.config')
                if os.path.exists(gost_config_file):
                    # Start Gost service with longer timeout
                    gost_result = run_command(f'bash manage_gost.sh restart-port {port}', timeout=90)
                    if not gost_result['success']:
                        print(f"Warning: Failed to start Gost on port {port}: {gost_result.get('stderr', 'Unknown error')}")
            
            # Start HAProxy service with longer timeout
            command = f'bash setup_haproxy.sh --sock-port {sock_port} --stats-port {stats_port} --gost-ports {",".join(map(str, wg_ports))} --daemon'
            print(f"DEBUG: Running command: {command}")
            result = run_command(command, timeout=90)
            
            if result['success']:
                # Wait a moment for service to start
                import time
                time.sleep(2)
                
                # Check if service is actually running
                pid_file = os.path.join(LOG_DIR, f'haproxy_{sock_port}.pid')
                if os.path.exists(pid_file):
                    try:
                        with open(pid_file) as f:
                            pid = int(f.read().strip())
                        os.kill(pid, 0)  # Check if process exists
                        return jsonify({
                            'success': True,
                            'message': f'HAProxy service created and started on port {sock_port}',
                            'sock_port': sock_port,
                            'stats_port': stats_port,
                            'gost_ports': wg_ports,
                            'pid': pid
                        })
                    except (OSError, ValueError):
                        pass
                
                # If we get here, service didn't start properly
                return jsonify({
                    'success': False,
                    'error': 'HAProxy service failed to start properly'
                }), 500
            else:
                # Clean up config file if start failed
                try:
                    os.remove(config_file)
                except:
                    pass
                
                error_msg = result.get('stderr', 'Unknown error')
                if not error_msg.strip():
                    error_msg = f"Command failed with return code {result.get('returncode', -1)}"
                
                return jsonify({
                    'success': False,
                    'error': f'Failed to start HAProxy: {error_msg}',
                    'stdout': result.get('stdout', ''),
                    'stderr': result.get('stderr', ''),
                    'returncode': result.get('returncode', -1)
                }), 500
                
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/haproxy/delete/<port>', methods=['DELETE'])
    def api_haproxy_delete(port):
        """Xóa HAProxy service triệt để"""
        try:
            # Validate port
            try:
                port = int(port)
                if port < 1024 or port > 65535:
                    raise ValueError("Port out of range")
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid port number'
                }), 400
            
            deleted_files = []
            killed_processes = []
            
            # 1. Dừng tất cả processes liên quan
            print(f"🛑 Stopping all processes for port {port}...")
            
            # Stop HAProxy process
            pid_file = os.path.join(LOG_DIR, f'haproxy_{port}.pid')
            if os.path.exists(pid_file):
                try:
                    with open(pid_file) as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 15)  # SIGTERM
                    killed_processes.append(f"HAProxy process (PID {pid})")
                    print(f"✓ Killed HAProxy process {pid}")
                except (OSError, ValueError):
                    pass
            
            # Stop health monitor process
            health_pid_file = os.path.join(LOG_DIR, f'health_{port}.pid')
            if os.path.exists(health_pid_file):
                try:
                    with open(health_pid_file) as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 15)  # SIGTERM
                    killed_processes.append(f"Health monitor (PID {pid})")
                    print(f"✓ Killed health monitor {pid}")
                except (OSError, ValueError):
                    pass
            
            # Force kill any remaining processes
            import subprocess
            try:
                # Kill any setup_haproxy.sh processes for this port
                result = subprocess.run(['pkill', '-f', f'setup_haproxy.sh.*--sock-port {port}'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    killed_processes.append("setup_haproxy.sh process")
                    print(f"✓ Killed setup_haproxy.sh process for port {port}")
                
                # Kill any haproxy processes for this port
                result = subprocess.run(['pkill', '-f', f'haproxy.*haproxy_{port}.cfg'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    killed_processes.append("HAProxy process")
                    print(f"✓ Force killed HAProxy process for port {port}")
            except Exception as e:
                print(f"⚠️  Error force killing processes: {e}")
            
            # 2. Xóa tất cả files liên quan
            print(f"🗑️  Removing all files for port {port}...")
            
            files_to_remove = [
                (os.path.join(LOG_DIR, f'haproxy_{port}.pid'), 'HAProxy PID file'),
                (os.path.join(LOG_DIR, f'health_{port}.pid'), 'Health monitor PID file'),
                (os.path.join(LOG_DIR, f'haproxy_health_{port}.pid'), 'HAProxy health PID file'),
                (os.path.join(LOG_DIR, f'haproxy_health_{port}.log'), 'HAProxy health log'),
                (os.path.join(LOG_DIR, f'haproxy_{port}.log'), 'HAProxy log'),
                (os.path.join(LOG_DIR, f'last_backend_{port}'), 'Last backend file'),
                (os.path.join(BASE_DIR, 'config', f'haproxy_{port}.cfg'), 'HAProxy config file')
            ]
            
            for file_path, description in files_to_remove:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        deleted_files.append(description)
                        print(f"✓ Removed {description}")
                    except Exception as e:
                        print(f"⚠️  Error removing {description}: {e}")
            
            # 3. Đợi một chút để đảm bảo processes đã dừng
            import time
            time.sleep(1)
            
            # 4. Kiểm tra lại xem còn process nào không
            try:
                result = subprocess.run(['pgrep', '-f', f'haproxy.*{port}'], 
                                      capture_output=True, text=True)
                if result.stdout.strip():
                    print(f"⚠️  Warning: Some processes may still be running for port {port}")
            except Exception:
                pass
            
            # 5. Tạo file lock tạm thời để ngăn chặn tự động tạo lại trong quá trình xóa
            lock_file = os.path.join(LOG_DIR, f'deleted_port_{port}.lock')
            try:
                with open(lock_file, 'w') as f:
                    f.write(f"Port {port} was deleted at {datetime.now().isoformat()}\n")
                    f.write("This file prevents automatic recreation of this port\n")
                deleted_files.append("Created deletion lock file")
                print(f"✓ Created deletion lock file to prevent auto-recreation")
            except Exception as e:
                print(f"⚠️  Error creating lock file: {e}")
            
            # 6. Tự động unlock sau khi xóa xong để cho phép tạo lại
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
                    deleted_files.append("Auto-unlocked port for recreation")
                    print(f"✓ Auto-unlocked port {port} to allow recreation")
            except Exception as e:
                print(f"⚠️  Error auto-unlocking: {e}")
            
            return jsonify({
                'success': True,
                'message': f'HAProxy service on port {port} deleted successfully and unlocked for recreation',
                'deleted_files': deleted_files,
                'killed_processes': killed_processes
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/haproxy/unlock/<port>', methods=['POST'])
    def api_haproxy_unlock(port):
        """Xóa file lock để cho phép tạo lại port"""
        try:
            port = int(port)
            lock_file = os.path.join(LOG_DIR, f'deleted_port_{port}.lock')
            
            if os.path.exists(lock_file):
                os.remove(lock_file)
                return jsonify({
                    'success': True,
                    'message': f'Lock file removed for port {port}. Port can now be recreated.'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'No lock file found for port {port}'
                }), 404
                
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid port number'
            }), 400
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/haproxy/<action>', methods=['POST'])
    def api_haproxy_action(action):
        """Điều khiển HAProxy (start/stop/restart)"""
        if action not in ['start', 'stop', 'restart']:
            return jsonify({'success': False, 'error': 'Invalid action'}), 400
        
        result = run_command(f'bash setup_haproxy.sh {action}', timeout=90)
        
        return jsonify({
            'success': result['success'],
            'output': result['stdout'],
            'error': result['stderr']
        })
