"""
Chrome Handler
Xử lý các API endpoints liên quan đến Chrome proxy
"""

from flask import request, jsonify
import os
import sys
import glob
import random

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def register_chrome_routes(app, BASE_DIR, get_available_haproxy_ports, _get_proxy_port):
    """Đăng ký các routes Chrome với Flask app"""
    
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
                for cfg_file in glob.glob(os.path.join(BASE_DIR, 'config', 'haproxy_*.cfg')):
                    try:
                        port = int(cfg_file.split('_')[-1].replace('.cfg', ''))
                        existing_ports.add(port)
                    except (ValueError, IndexError):
                        pass
                
                # Find next available port dynamically
                available_ports = get_available_haproxy_ports()
                new_port = None
                
                # Try to find an available port dynamically
                # Start from 7891 and go up to find available port
                base_port = 7891
                for offset in range(100):  # Safety limit: 100 ports
                    test_port = base_port + offset
                    if test_port not in existing_ports and test_port != int(check_port):
                        new_port = test_port
                        break
                
                if new_port is None:
                    return jsonify({
                        'success': False,
                        'error': f'No available ports found (tried {base_port}-{base_port + 99})'
                    }), 500
                
                # Verify the corresponding wireproxy port is also available
                expected_wireproxy_port = 18181 + (new_port - base_port)
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
