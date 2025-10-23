"""
Chrome Handler
Xử lý các API endpoints liên quan đến Chrome proxy
"""

from flask import request, jsonify
import os
import sys
import glob
import random
import requests
import logging

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _find_available_haproxy_and_gost(profiles, check_server, vpn_provider):
    """Tìm HAProxy và Gost đang rảnh (không được sử dụng bởi profiles)"""
    try:
        # Lấy danh sách HAProxy đang chạy
        status_response = requests.get('http://127.0.0.1:5000/api/status', timeout=10)
        if status_response.status_code != 200:
            return None
        
        status_data = status_response.json()
        haproxy_services = status_data.get('haproxy', [])
        gost_services = status_data.get('gost', [])
        
        # Lấy danh sách ports đang được sử dụng bởi profiles
        used_ports = set()
        for profile in profiles:
            if profile.get('proxy'):
                proxy_str = profile['proxy']
                if proxy_str.startswith('socks5://'):
                    proxy_str = proxy_str[9:]
                parts = proxy_str.split(':')
                if len(parts) >= 2:
                    try:
                        port = int(parts[1])
                        used_ports.add(port)
                    except ValueError:
                        pass
        
        # Tìm Gost đang chạy nhưng không được sử dụng bởi profiles
        for gost in gost_services:
            if gost.get('running'):
                gost_port = int(gost['port'])
                haproxy_port = 7891 + (gost_port - 18181)
                
                # Kiểm tra xem HAProxy port này có đang được sử dụng bởi profiles không
                if haproxy_port not in used_ports:
                    return {
                        'port': haproxy_port,
                        'gost_port': gost_port,
                        'server': check_server,
                        'vpn_provider': vpn_provider
                    }
        
        return None
    except Exception as e:
        print(f"Error finding available HAProxy: {e}")
        return None

def register_chrome_routes(app, BASE_DIR, get_available_haproxy_ports, _get_proxy_port):
    """Đăng ký các routes Chrome với Flask app"""
    
    @app.route('/api/chrome/proxy-check', methods=['POST'])
    def api_chrome_proxy_check():
        """
        API kiểm tra và tạo proxy cho Chrome profiles
        Input format: 
        {
          "proxy_check": "socks5://server:7891:vn42.nordvpn.com:89",
          "data": {
            "count": 3,
            "profiles": [
              {"id": 1, "name": "Profile 1", "proxy": "127.0.0.1:7891:vn42.nordvpn.com:89"},
              {"id": 2, "name": "Profile 2", "proxy": null}
            ]
          }
        }
        """
        try:
            logging.info(f"[CHROME_PROXY_CHECK] Starting request...")
            data = request.json
            proxy_check = data.get('proxy_check', '')
            profiles_data = data.get('data', {})
            profiles = profiles_data.get('profiles', [])
            logging.info(f"[CHROME_PROXY_CHECK] proxy_check: {proxy_check}")
            logging.info(f"[CHROME_PROXY_CHECK] profiles count: {len(profiles)}")
            
            # Parse proxy_check: "socks5://HOST:PORT:SERVER_NAME:PORT"
            if not proxy_check or not proxy_check.startswith('socks5://'):
                return jsonify({
                    'success': False,
                    'error': 'Invalid proxy_check format. Expected: socks5://HOST:PORT:SERVER_NAME:PORT'
                }), 400
            
            # Extract components from proxy_check
            proxy_parts = proxy_check.replace('socks5://', '').rstrip(':').split(':')
            if len(proxy_parts) < 2:
                return jsonify({
                    'success': False,
                    'error': 'Invalid proxy_check format. Expected: socks5://HOST:PORT:SERVER_NAME:PORT'
                }), 400
            
            client_host = proxy_parts[0]  # Extract host from proxy_check
            check_port = proxy_parts[1]
            check_server = proxy_parts[2] if len(proxy_parts) >= 3 else ''
            check_proxy_port = proxy_parts[3] if len(proxy_parts) >= 4 else ''
            
            # Parse proxy_check để map với 3 trường hợp apply
            apply_data = {}
            
            if check_proxy_port and check_proxy_port.isdigit() and check_server and '.' in check_server:
                # Trường hợp 2: Có proxy_host và proxy_port (server phải là domain thực tế)
                apply_data = {
                    "proxy_host": check_server,
                    "proxy_port": int(check_proxy_port)
                }
            elif len(check_server) == 2 and check_server.isalpha():
                # Trường hợp 1: Country code (2 ký tự)
                apply_data = {
                    "country_code": check_server.upper()
                }
            else:
                # Trường hợp 3: Random server (empty hoặc không parse được)
                apply_data = {}
            
            # Determine VPN provider from server name
            vpn_provider = 'protonvpn'
            #if 'nordvpn' in check_server.lower():
            #    vpn_provider = 'nordvpn'
            #elif 'protonvpn' in check_server.lower():
            #    vpn_provider = 'protonvpn'
            #elif len(check_server) == 2:
            #    # For 2-character server names (country codes), random select VPN provider
            #    vpn_provider = random.choice(['nordvpn', 'protonvpn'])
            #else:
            #    # Random VPN provider for empty/unknown cases
            #    vpn_provider = random.choice(['nordvpn', 'protonvpn'])
            
            # Lấy danh sách proxy từ profiles
            existing_proxies = []
            for profile in profiles:
                if profile.get('proxy'):
                    proxy_str = profile['proxy']
                    # Parse socks5://host:port:server:proxy_port format
                    if proxy_str.startswith('socks5://'):
                        proxy_str = proxy_str[9:]
                    
                    parts = proxy_str.split(':')
                    if len(parts) >= 2:
                        existing_proxies.append({
                            'host': parts[0],
                            'port': parts[1],
                            'server': parts[2] if len(parts) >= 3 else '',
                            'proxy_port': parts[3] if len(parts) >= 4 else ''
                        })
            
            # So sánh proxy_check với các proxy của profiles
            exact_match = None
            same_gost_port_different_server = None
            different_gost_port_same_server = None
            
            for existing_proxy in existing_proxies:
                # 1. Nếu proxy_check = proxy thì return lại proxy
                if (existing_proxy['port'] == check_port and 
                    existing_proxy['server'] == check_server and 
                    existing_proxy['proxy_port'] == check_proxy_port):
                    exact_match = existing_proxy
                    break
                
                # 2. Khác port HA, proxy_host và proxy_port giống nhau thì return lại proxy
                # Chỉ match khi có đầy đủ thông tin server và proxy_port (không phải country code)
                # VÀ server phải là domain thực tế (không phải country code)
                if (existing_proxy['port'] != check_port and 
                    existing_proxy['server'] == check_server and 
                    existing_proxy['proxy_port'] == check_proxy_port and
                    check_server != '' and check_proxy_port != '' and
                    existing_proxy['server'] != '' and existing_proxy['proxy_port'] != '' and
                    len(check_server) > 2 and check_proxy_port.isdigit() and
                    '.' in check_server):  # Server phải có domain (không phải country code)
                    different_gost_port_same_server = existing_proxy
            
                
                # 3. Trùng port gost, proxy_host và proxy_port khác nhau
                if (existing_proxy['port'] == check_port and 
                    (existing_proxy['server'] != check_server or existing_proxy['proxy_port'] != check_proxy_port)):
                    same_gost_port_different_server = existing_proxy
            
            # Xử lý 4 trường hợp
            logging.info(f"[CHROME_PROXY_CHECK] Processing cases...")
            
            if exact_match:
                # 1. Nếu proxy_check = proxy thì return lại proxy
                logging.info(f"[CHROME_PROXY_CHECK] Case 1: Exact match found")
                return f'socks5://{exact_match["host"]}:{exact_match["port"]}:{exact_match["server"]}:{exact_match["proxy_port"]}'
            
            elif different_gost_port_same_server:
                # 2. Khác port gost, proxy_host và proxy_port giống nhau thì return lại proxy
                logging.info(f"[CHROME_PROXY_CHECK] Case 2: Different port, same server")
                return f'socks5://{different_gost_port_same_server["host"]}:{different_gost_port_same_server["port"]}:{different_gost_port_same_server["server"]}:{different_gost_port_same_server["proxy_port"]}'
            
            elif same_gost_port_different_server:
                # 3. Trùng port gost, proxy_host và proxy_port khác nhau thì tạo mới HA và apply gost
                logging.info(f"[CHROME_PROXY_CHECK] Case 3: Same port, different server")
                # Trước tiên kiểm tra HAProxy và Gost đang rảnh
                available_haproxy = _find_available_haproxy_and_gost(profiles, check_server, vpn_provider)
                if available_haproxy:
                    # Sử dụng lại HAProxy đang rảnh
                    haproxy_port = available_haproxy['port']
                    gost_port = available_haproxy['gost_port']
                    
                    # Apply Gost với dữ liệu đã phân tích
                    if vpn_provider == 'nordvpn':
                        apply_url = f'http://127.0.0.1:5000/api/nordvpn/apply/{gost_port}'
                    else:
                        apply_url = f'http://127.0.0.1:5000/api/protonvpn/apply/{gost_port}'
                    
                    apply_response = requests.post(apply_url, json=apply_data, timeout=15)
                    if apply_response.status_code != 200:
                        # Fallback: try with random server if specific server not found
                        print(f"Server not found, trying random server fallback...")
                        fallback_data = {}  # Empty data for random server
                        fallback_response = requests.post(apply_url, json=fallback_data, timeout=15)
                        if fallback_response.status_code != 200:
                            return jsonify({
                                'success': False,
                                'error': f'Failed to apply server to Gost: {apply_response.text}'
                            }), 500
                        apply_response = fallback_response
                    
                    # Parse response để lấy thông tin server thực tế
                    apply_result = apply_response.json()
                    if apply_result.get('success'):
                        actual_server = apply_result.get('server', {})
                        # Sử dụng hostname hoặc domain tùy theo VPN provider
                        actual_proxy_host = actual_server.get('hostname') or actual_server.get('domain', check_server if check_server else 'random-server')
                        # Parse port từ proxy_url hoặc sử dụng default
                        proxy_url = apply_result.get('proxy_url', '')
                        if proxy_url and ':' in proxy_url:
                            try:
                                # Parse port từ proxy_url (format: https://user:pass@host:port)
                                port_part = proxy_url.split('@')[-1].split(':')[-1]
                                actual_proxy_port = port_part
                            except:
                                actual_proxy_port = '89'
                        else:
                            actual_proxy_port = '89'
                    else:
                        # Fallback nếu không parse được
                        actual_proxy_host = check_server if check_server else 'random-server'
                        actual_proxy_port = '89'
                    
                    return f'socks5://{client_host}:{haproxy_port}:{actual_proxy_host}:{actual_proxy_port}'
                
                # Nếu không có HAProxy rảnh, tạo mới
                used_ports = [int(p['port']) for p in existing_proxies]
                new_port = None
                
                for port in range(7891, 8000):
                    if port not in used_ports:
                        new_port = port
                        break
                
                if new_port is None:
                    return jsonify({
                        'success': False,
                        'error': 'No available HAProxy ports found'
                    }), 500
                
                # Apply Gost với dữ liệu đã phân tích trước
                gost_port = 18181 + (new_port - 7891)
                if vpn_provider == 'nordvpn':
                    apply_url = f'http://127.0.0.1:5000/api/nordvpn/apply/{gost_port}'
                else:
                    apply_url = f'http://127.0.0.1:5000/api/protonvpn/apply/{gost_port}'
                
                apply_response = requests.post(apply_url, json=apply_data, timeout=15)
                if apply_response.status_code != 200:
                    return jsonify({
                        'success': False,
                        'error': f'Failed to apply server to Gost: {apply_response.text}'
                    }), 500
                
                # Parse response để lấy thông tin server thực tế
                apply_result = apply_response.json()
                if apply_result.get('success'):
                    actual_server = apply_result.get('server', {})
                    # Sử dụng hostname hoặc domain tùy theo VPN provider
                    actual_proxy_host = actual_server.get('hostname') or actual_server.get('domain', check_server if check_server else 'random-server')
                    # Parse port từ proxy_url hoặc sử dụng default
                    proxy_url = apply_result.get('proxy_url', '')
                    if proxy_url and ':' in proxy_url:
                        try:
                            # Parse port từ proxy_url (format: https://user:pass@host:port)
                            port_part = proxy_url.split('@')[-1].split(':')[-1]
                            actual_proxy_port = port_part
                        except:
                            actual_proxy_port = '89'
                    else:
                        actual_proxy_port = '89'
                else:
                    # Fallback nếu không parse được
                    actual_proxy_host = check_server if check_server else 'random-server'
                    actual_proxy_port = '89'
                
                # Tạo HAProxy với Gost backend
                stats_port = new_port + 200
                haproxy_data = {
                    'sock_port': new_port,
                    'stats_port': stats_port,
                    'wg_ports': [gost_port],
                    'host_proxy': '127.0.0.1:8111',
                    'stats_auth': 'admin:admin123',
                    'health_interval': 10
                }
                
                haproxy_response = requests.post('http://127.0.0.1:5000/api/haproxy/create', json=haproxy_data, timeout=20)
                if haproxy_response.status_code != 200:
                    return jsonify({
                        'success': False,
                        'error': f'Failed to create HAProxy: {haproxy_response.text}'
                    }), 500
                
                return f'socks5://{client_host}:{new_port}:{actual_proxy_host}:{actual_proxy_port}'
            
            else:
                # 4. Port gost, proxy_host và proxy_port khác nhau, tạo mới HA và apply gost
                logging.info(f"[CHROME_PROXY_CHECK] Case 4: Different port and server")
                # Trước tiên kiểm tra HAProxy và Gost đang rảnh
                available_haproxy = _find_available_haproxy_and_gost(profiles, check_server, vpn_provider)
                if available_haproxy:
                    # Sử dụng lại HAProxy đang rảnh
                    haproxy_port = available_haproxy['port']
                    gost_port = available_haproxy['gost_port']
                    
                    # Apply Gost với dữ liệu đã phân tích
                    if vpn_provider == 'nordvpn':
                        apply_url = f'http://127.0.0.1:5000/api/nordvpn/apply/{gost_port}'
                    else:
                        apply_url = f'http://127.0.0.1:5000/api/protonvpn/apply/{gost_port}'
                    
                    apply_response = requests.post(apply_url, json=apply_data, timeout=15)
                    if apply_response.status_code != 200:
                        # Fallback: try with random server if specific server not found
                        print(f"Server not found, trying random server fallback...")
                        fallback_data = {}  # Empty data for random server
                        fallback_response = requests.post(apply_url, json=fallback_data, timeout=15)
                        if fallback_response.status_code != 200:
                            return jsonify({
                                'success': False,
                                'error': f'Failed to apply server to Gost: {apply_response.text}'
                            }), 500
                        apply_response = fallback_response
                    
                    # Parse response để lấy thông tin server thực tế
                    apply_result = apply_response.json()
                    if apply_result.get('success'):
                        actual_server = apply_result.get('server', {})
                        # Sử dụng hostname hoặc domain tùy theo VPN provider
                        actual_proxy_host = actual_server.get('hostname') or actual_server.get('domain', check_server if check_server else 'random-server')
                        # Parse port từ proxy_url hoặc sử dụng default
                        proxy_url = apply_result.get('proxy_url', '')
                        if proxy_url and ':' in proxy_url:
                            try:
                                # Parse port từ proxy_url (format: https://user:pass@host:port)
                                port_part = proxy_url.split('@')[-1].split(':')[-1]
                                actual_proxy_port = port_part
                            except:
                                actual_proxy_port = '89'
                        else:
                            actual_proxy_port = '89'
                    else:
                        # Fallback nếu không parse được
                        actual_proxy_host = check_server if check_server else 'random-server'
                        actual_proxy_port = '89'
                    
                    return f'socks5://{client_host}:{haproxy_port}:{actual_proxy_host}:{actual_proxy_port}'
                
                # Nếu không có HAProxy rảnh, tạo mới
                used_ports = [int(p['port']) for p in existing_proxies]
                new_port = None
                
                for port in range(7891, 8000):
                    if port not in used_ports:
                        new_port = port
                        break
                
                if new_port is None:
                    return jsonify({
                        'success': False,
                        'error': 'No available HAProxy ports found'
                    }), 500
                
                # Apply Gost với dữ liệu đã phân tích trước
                gost_port = 18181 + (new_port - 7891)
                if vpn_provider == 'nordvpn':
                    apply_url = f'http://127.0.0.1:5000/api/nordvpn/apply/{gost_port}'
                else:
                    apply_url = f'http://127.0.0.1:5000/api/protonvpn/apply/{gost_port}'
                
                apply_response = requests.post(apply_url, json=apply_data, timeout=15)
                if apply_response.status_code != 200:
                    return jsonify({
                        'success': False,
                        'error': f'Failed to apply server to Gost: {apply_response.text}'
                    }), 500
                
                # Parse response để lấy thông tin server thực tế
                apply_result = apply_response.json()
                if apply_result.get('success'):
                    actual_server = apply_result.get('server', {})
                    # Sử dụng hostname hoặc domain tùy theo VPN provider
                    actual_proxy_host = actual_server.get('hostname') or actual_server.get('domain', check_server if check_server else 'random-server')
                    # Parse port từ proxy_url hoặc sử dụng default
                    proxy_url = apply_result.get('proxy_url', '')
                    if proxy_url and ':' in proxy_url:
                        try:
                            # Parse port từ proxy_url (format: https://user:pass@host:port)
                            port_part = proxy_url.split('@')[-1].split(':')[-1]
                            actual_proxy_port = port_part
                        except:
                            actual_proxy_port = '89'
                    else:
                        actual_proxy_port = '89'
                else:
                    # Fallback nếu không parse được
                    actual_proxy_host = check_server if check_server else 'random-server'
                    actual_proxy_port = '89'
                
                # Tạo HAProxy với Gost backend
                stats_port = new_port + 200
                haproxy_data = {
                    'sock_port': new_port,
                    'stats_port': stats_port,
                    'wg_ports': [gost_port],
                    'host_proxy': '127.0.0.1:8111',
                    'stats_auth': 'admin:admin123',
                    'health_interval': 10
                }
                
                haproxy_response = requests.post('http://127.0.0.1:5000/api/haproxy/create', json=haproxy_data, timeout=20)
                if haproxy_response.status_code != 200:
                    return jsonify({
                        'success': False,
                        'error': f'Failed to create HAProxy: {haproxy_response.text}'
                    }), 500
                
                return f'socks5://{client_host}:{new_port}:{actual_proxy_host}:{actual_proxy_port}'
            
        except Exception as e:
            logging.error(f"[CHROME_PROXY_CHECK] Error: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
