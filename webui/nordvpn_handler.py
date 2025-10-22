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
            
            if not server_name:
                return jsonify({'success': False, 'error': 'No server name provided'}), 400
            
            if not proxy_host or not proxy_port:
                return jsonify({'success': False, 'error': 'proxy_host and proxy_port are required'}), 400
            
            # Get server info
            server = nordvpn_api.get_server_by_name(server_name)
            if not server:
                return jsonify({'success': False, 'error': 'Server not found'}), 404
            
            # Validate port - check if it's a valid gost port (18181-18999 range)
            try:
                port_num = int(port)
                if port_num < 18181 or port_num > 18999:
                    return jsonify({
                        'success': False, 
                        'error': f'Invalid port. Port must be between 18181-18999'
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
