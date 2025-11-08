"""
NordVPN API Handler
Xử lý các API endpoints liên quan đến NordVPN
"""

from flask import request, jsonify
import sys
import os

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nordvpn_api import NordVPNAPI
from proxy_api import ProxyAPI

# Initialize APIs
nordvpn_api = None
proxy_api = None

def register_nordvpn_routes(app, save_gost_config, run_command, trigger_health_check, nordvpn_api_instance, proxy_api_instance):
    """Đăng ký các routes NordVPN với Flask app"""
    global nordvpn_api, proxy_api
    nordvpn_api = nordvpn_api_instance
    proxy_api = proxy_api_instance
    

    @app.route('/api/nordvpn/servers/formatted')
    def api_nordvpn_servers_formatted():
        """Lấy danh sách server NordVPN với format thống nhất"""
        try:
            force_refresh = request.args.get('refresh', 'false').lower() == 'true'
            country_filter = request.args.get('country', None)
            servers = nordvpn_api.fetch_servers(force_refresh=force_refresh)
            
            # Format lại dữ liệu
            formatted_servers = []
            for server in servers:
                formatted_server = {
                    'name': server.get('name', ''),
                    'hostname': server.get('hostname', ''),
                    'country': server.get('country', {}).get('name', ''),
                    'country_code': server.get('country', {}).get('code', ''),
                    'city': server.get('country', {}).get('city', ''),
                    'ip': server.get('station', ''),
                    'load': server.get('load', 0),
                    'status': '✅ Online' if server.get('status') == 'online' else '❌ Offline',
                    'proxyhost': server.get('hostname', ''),
                    'proxyport': 89  # NordVPN standard port
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
            proxy_host = data.get('proxy_host')
            proxy_port = data.get('proxy_port')
            country_code = data.get('country_code')
            
            # Determine which case we're handling
            if country_code and not proxy_host and not proxy_port:
                # Case 1: Only country_code provided - get random server from country
                servers = nordvpn_api.get_servers_by_country(country_code)
                if not servers:
                    return jsonify({'success': False, 'error': f'No servers found for country {country_code}'}), 404
                
                import random
                server = random.choice(servers)
                proxy_host = server.get('hostname', '')
                proxy_port = 89  # NordVPN standard port
                server_name = server.get('name', '')
                
            elif proxy_host and proxy_port:
                # Case 2: proxy_host and proxy_port provided - use directly
                # Find server by proxy_host to get server info
                all_servers = nordvpn_api.get_all_servers()
                server = None
                for s in all_servers:
                    if s.get('hostname', '').lower() == proxy_host.lower():
                        server = s
                        break
                
                if not server:
                    return jsonify({'success': False, 'error': f'Server with hostname {proxy_host} not found'}), 404
                
                server_name = server.get('name', '')
                    
            elif not country_code and not proxy_host and not proxy_port:
                # Case 3: Null/empty - random server from any country
                all_servers = nordvpn_api.get_all_servers()
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
                    server_hostname = server.get('hostname', '')
                    server_port = 89  # NordVPN standard port
                    
                    proxy_key = f"{server_hostname}:{server_port}"
                    if proxy_key not in used_proxies:
                        available_servers.append(server)
                
                # If no available servers, use all servers (fallback)
                if not available_servers:
                    print("Warning: All NordVPN servers are in use, selecting from all servers")
                    available_servers = all_servers
                
                import random
                server = random.choice(available_servers)
                proxy_host = server.get('hostname', '')
                proxy_port = 89  # NordVPN standard port
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
            
            # Create proxy URL with auth for NordVPN
            proxy_url = f"https://USMbUonbFpF9xEx8xR3MHSau:buKKKPURZNMTW7A6rwm3qtBn@{proxy_host}:{proxy_port}"
            
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
