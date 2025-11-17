"""
ProtonVPN API Handler
Xử lý các API endpoints liên quan đến ProtonVPN
"""

from flask import request, jsonify
import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from protonvpn_api import ProtonVPNAPI
from proxy_api import ProxyAPI

# Initialize APIs
protonvpn_api = None
proxy_api = None

def register_protonvpn_routes(app, save_gost_config, run_command, trigger_health_check, protonvpn_api_instance, proxy_api_instance):
    """Đăng ký các routes ProtonVPN với Flask app"""
    global protonvpn_api, proxy_api
    protonvpn_api = protonvpn_api_instance
    proxy_api = proxy_api_instance
    

    @app.route('/api/protonvpn/servers/formatted')
    def api_protonvpn_servers_formatted():
        """Lấy danh sách ProtonVPN servers với format thống nhất"""
        try:
            if not protonvpn_api:
                return jsonify({
                    'success': False,
                    'error': 'ProtonVPN API not configured. Please create protonvpn_credentials.json'
                }), 400
            
            force_refresh = request.args.get('refresh', 'false').lower() == 'true'
            country_filter = request.args.get('country', None)
            servers = protonvpn_api.fetch_servers(force_refresh=force_refresh)
            
            # Format lại dữ liệu
            formatted_servers = []
            for server in servers:
                # Tính proxy port từ label
                proxy_port = 4443
                if 'servers' in server and len(server['servers']) > 0:
                    try:
                        label = int(server['servers'][0].get('label', '0'))
                        proxy_port = 4443 + label
                    except (ValueError, TypeError):
                        pass
                
                formatted_server = {
                    'name': server.get('name', ''),
                    'hostname': server.get('domain', ''),
                    'country': server.get('country_name', ''),
                    'country_code': server.get('country_code', ''),
                    'city': server.get('city', ''),
                    'ip': server.get('entry_ip', ''),
                    'load': server.get('load', 0),
                    'status': '✅ Online' if server.get('load', 0) < 100 else '❌ Offline',
                    'proxyhost': server.get('domain', ''),
                    'proxyport': proxy_port
                }
                
                # Filter by country if specified
                if country_filter:
                    if formatted_server['country_code'].lower() == country_filter.lower():
                        formatted_servers.append(formatted_server)
                else:
                    formatted_servers.append(formatted_server)
            
            return jsonify({
                'success': True,
                'servers': formatted_servers,
                'count': len(formatted_servers)
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
            proxy_host = data.get('proxy_host')
            proxy_port = data.get('proxy_port')
            country_code = data.get('country_code')
            
            # Determine which case we're handling
            if country_code and not proxy_host and not proxy_port:
                # Case 1: Only country_code provided - get random server from country
                servers = protonvpn_api.get_servers_by_country(country_code)
                if not servers:
                    return jsonify({'success': False, 'error': f'No servers found for country {country_code}'}), 404
                
                import random
                server = random.choice(servers)
                proxy_host = server.get('domain', '')
                # Calculate proxy port from label
                proxy_port = 4443
                if 'servers' in server and len(server['servers']) > 0:
                    try:
                        label = int(server['servers'][0].get('label', '0'))
                        proxy_port = 4443 + label
                    except (ValueError, TypeError):
                        pass
                server_name = server.get('name', '')
                
            elif proxy_host and proxy_port:
                # Case 2: proxy_host and proxy_port provided - use directly
                # Find server by proxy_host to get server info
                all_servers = protonvpn_api.get_all_servers()
                server = None
                for s in all_servers:
                    if s.get('domain', '').lower() == proxy_host.lower():
                        server = s
                        break
                
                if not server:
                    return jsonify({'success': False, 'error': f'Server with domain {proxy_host} not found'}), 404
                
                server_name = server.get('name', '')
                    
            elif not country_code and not proxy_host and not proxy_port:
                # Case 3: Null/empty - random server from any country
                all_servers = protonvpn_api.get_all_servers()
                if not all_servers:
                    return jsonify({'success': False, 'error': 'No servers available'}), 404
                
                # Get list of currently used proxies to avoid duplicates
                used_proxies = set()
                try:
                    import requests
                    response = requests.get("http://localhost:18112/api/profiles/list-proxy", timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, dict) and 'data' in data:
                            # API returns {"success": true, "data": ["host:port", ...]}
                            proxy_list = data.get('data', [])
                            for proxy_string in proxy_list:
                                if ':' in proxy_string:
                                    used_proxies.add(proxy_string)
                        elif isinstance(data, list):
                            # Fallback: API returns list of profiles
                            for profile in data:
                                proxy = profile.get('proxy', '')
                                if proxy and ':' in proxy:
                                    # Extract host:port from proxy string
                                    parts = proxy.split(':')
                                    if len(parts) >= 2:
                                        try:
                                            host = parts[0].replace('socks5://', '').replace('https://', '')
                                            port = int(parts[1])
                                            used_proxies.add(f"{host}:{port}")
                                        except (ValueError, IndexError):
                                            pass
                except Exception as e:
                    print(f"Warning: Could not get used proxies: {e}")
                
                # Filter out servers that are already in use
                available_servers = []
                for server in all_servers:
                    server_domain = server.get('domain', '')
                    server_port = 4443
                    if 'servers' in server and len(server['servers']) > 0:
                        try:
                            label = int(server['servers'][0].get('label', '0'))
                            server_port = 4443 + label
                        except (ValueError, TypeError):
                            pass
                    
                    proxy_key = f"{server_domain}:{server_port}"
                    if proxy_key not in used_proxies:
                        available_servers.append(server)
                
                # If no available servers, use all servers (fallback)
                if not available_servers:
                    print("Warning: All servers are in use, selecting from all servers")
                    available_servers = all_servers
                
                import random
                server = random.choice(available_servers)
                proxy_host = server.get('domain', '')
                # Calculate proxy port from label
                proxy_port = 4443
                if 'servers' in server and len(server['servers']) > 0:
                    try:
                        label = int(server['servers'][0].get('label', '0'))
                        proxy_port = 4443 + label
                    except (ValueError, TypeError):
                        pass
                server_name = server.get('name', '')
                
            else:
                return jsonify({'success': False, 'error': 'Invalid parameters. Provide either country_code, or proxy_host+proxy_port, or leave all empty for random'}), 400
            
            # Validate port - check if it's a valid gost port (7891-7999 range)
            try:
                port_num = int(port)
                if port_num < 7891 or port_num > 7999:
                    return jsonify({
                        'success': False, 
                        'error': f'Invalid port. Port must be between 7891-7999'
                    }), 400
            except ValueError:
                return jsonify({
                    'success': False, 
                    'error': 'Invalid port format. Must be a number'
                }), 400
            
            # Use port-based management
            
            # Get ProtonVPN auth using dedicated script
            import subprocess
            try:
                # Auto-detect base directory - use BASE_DIR from app.py if available
                # Otherwise detect from current file location
                try:
                    # Try to get BASE_DIR from app module
                    import webui.app as app_module
                    base_dir = getattr(app_module, 'BASE_DIR', None)
                except:
                    base_dir = None
                
                if not base_dir:
                    # Auto-detect base directory from current file
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    base_dir = os.path.dirname(script_dir)  # webui -> parent
                
                # Verify this is the right directory
                if not os.path.exists(base_dir) or not os.path.exists(os.path.join(base_dir, 'get_protonvpn_auth.sh')):
                    # Try to find mac_proxy directory
                    current = base_dir
                    found = False
                    while current != os.path.dirname(current):
                        if os.path.exists(os.path.join(current, 'get_protonvpn_auth.sh')):
                            base_dir = current
                            found = True
                            break
                        current = os.path.dirname(current)
                    
                    # Fallback to home directory
                    if not found:
                        base_dir = os.path.expanduser("~/mac_proxy")
                
                # Verify base_dir exists
                if not os.path.exists(base_dir):
                    return jsonify({
                        'success': False,
                        'error': f'Base directory does not exist: {base_dir}. Please ensure mac_proxy is installed correctly.'
                    }), 500
                
                # Verify auth script exists
                auth_script = os.path.join(base_dir, 'get_protonvpn_auth.sh')
                if not os.path.exists(auth_script):
                    return jsonify({
                        'success': False,
                        'error': f'Auth script not found: {auth_script}. Please ensure mac_proxy is installed correctly.'
                    }), 500
                
                # Call get_protonvpn_auth.sh script
                result = subprocess.run(['bash', auth_script], 
                                      capture_output=True, text=True, timeout=10, 
                                      cwd=base_dir)
                if result.returncode == 0 and result.stdout.strip():
                    auth_token = result.stdout.strip()
                    proxy_url = f"https://{auth_token}@{proxy_host}:{proxy_port}"
                else:
                    error_msg = result.stderr.strip() if result.stderr else 'Unknown error'
                    return jsonify({
                        'success': False,
                        'error': f'Failed to get ProtonVPN auth token: {error_msg}'
                    }), 500
            except FileNotFoundError as e:
                return jsonify({
                    'success': False,
                    'error': f'File not found: {str(e)}. Please ensure mac_proxy is installed correctly.'
                }), 500
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                return jsonify({
                    'success': False,
                    'error': f'Failed to get ProtonVPN auth: {str(e)}',
                    'detail': error_detail if 'DEBUG' in os.environ else None
                }), 500
            
            # Save gost config
            config = {
                'provider': 'protonvpn',
                'country': server['domain'],
                'proxy_url': proxy_url,
                'port': str(proxy_port)
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
