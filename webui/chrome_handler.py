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

def _apply_server_with_fallback(gost_port, apply_data, vpn_provider):
    """
    Apply server với fallback logic:
    1. Try primary provider với specific data
    2. Try primary provider với random server
    3. Try alternative provider với specific data
    4. Try alternative provider với random server
    """
    # Primary provider
    if vpn_provider == 'nordvpn':
        apply_url = f'http://127.0.0.1:5000/api/nordvpn/apply/{gost_port}'
    else:
        apply_url = f'http://127.0.0.1:5000/api/protonvpn/apply/{gost_port}'
    
    # Try primary provider với specific data
    apply_response = requests.post(apply_url, json=apply_data, timeout=15)
    if apply_response.status_code == 200:
        return apply_response, vpn_provider
    
    # Try primary provider với random server
    print(f"Server not found, trying random server fallback...")
    fallback_data = {}  # Empty data for random server
    fallback_response = requests.post(apply_url, json=fallback_data, timeout=15)
    if fallback_response.status_code == 200:
        return fallback_response, vpn_provider
    
    # Try alternative provider
    print(f"Primary provider failed, trying alternative provider...")
    alternative_provider = 'protonvpn' if vpn_provider == 'nordvpn' else 'nordvpn'
    alternative_url = f'http://127.0.0.1:5000/api/{alternative_provider}/apply/{gost_port}'
    
    # Try alternative provider với specific data
    alt_response = requests.post(alternative_url, json=apply_data, timeout=15)
    if alt_response.status_code == 200:
        print(f"✅ Alternative provider {alternative_provider} succeeded")
        return alt_response, alternative_provider
    
    # Try alternative provider với random server
    alt_random_response = requests.post(alternative_url, json={}, timeout=15)
    if alt_random_response.status_code == 200:
        print(f"✅ Alternative provider {alternative_provider} random server succeeded")
        return alt_random_response, alternative_provider
    
    # Final fallback: Try both providers with random server from any country
    print(f"All specific attempts failed, trying random server from any country...")
    
    # Try primary provider with random server from any country
    primary_random_response = requests.post(apply_url, json={}, timeout=15)
    if primary_random_response.status_code == 200:
        print(f"✅ Primary provider {vpn_provider} random server from any country succeeded")
        return primary_random_response, vpn_provider
    
    # Try alternative provider with random server from any country
    alt_any_random_response = requests.post(alternative_url, json={}, timeout=15)
    if alt_any_random_response.status_code == 200:
        print(f"✅ Alternative provider {alternative_provider} random server from any country succeeded")
        return alt_any_random_response, alternative_provider
    
    # All failed
    return None, None

def _determine_smart_vpn_provider(check_server, profiles):
    """
    Xác định VPN provider thông minh dựa trên:
    1. Server name pattern
    2. Số lượng kết nối hiện tại
    3. Giới hạn kết nối (NordVPN: 10, ProtonVPN: unlimited)
    """
    return 'protonvpn'
    try:
        # Đếm số lượng kết nối hiện tại cho mỗi provider
        nordvpn_connections = 0
        protonvpn_connections = 0
        
        for profile in profiles:
            if profile.get('proxy'):
                proxy_str = profile['proxy']
                if proxy_str.startswith('socks5://'):
                    proxy_str = proxy_str[9:]
                
                parts = proxy_str.split(':')
                if len(parts) >= 3:
                    server = parts[2]
                    # Kiểm tra pattern để xác định provider
                    if any(pattern in server.lower() for pattern in ['nordvpn', '.nordvpn.com']):
                        nordvpn_connections += 1
                    elif any(pattern in server.lower() for pattern in ['protonvpn', '.protonvpn.net']):
                        protonvpn_connections += 1
        
        # Logic thông minh:
        # 1. Nếu server name có pattern rõ ràng, sử dụng provider tương ứng
        if check_server:
            if any(pattern in check_server.lower() for pattern in ['nordvpn', '.nordvpn.com']):
                return 'nordvpn'
            elif any(pattern in check_server.lower() for pattern in ['protonvpn', '.protonvpn.net']):
                return 'protonvpn'
        
        # 2. Nếu là country code (2 ký tự), cân bằng theo tỉ lệ 7:3
        if check_server and len(check_server) == 2 and check_server.isalpha():
            # Kiểm tra giới hạn kết nối trước
            if nordvpn_connections >= 10:  # NordVPN đã đạt giới hạn
                return 'protonvpn'
            elif protonvpn_connections >= 15:  # ProtonVPN có quá nhiều kết nối
                return 'nordvpn'
            
            # Cân bằng theo tỉ lệ 7:3 (ProtonVPN:NordVPN)
            import random
            if random.random() < 0.7:  # 70% chance cho ProtonVPN
                return 'protonvpn'
            else:  # 30% chance cho NordVPN
                return 'nordvpn'
        
        # 3. Random server case - cân bằng theo tỉ lệ 7:3
        if not check_server or check_server == '' or check_server is None:
            # Kiểm tra giới hạn kết nối
            if nordvpn_connections >= 10:  # NordVPN đã đạt giới hạn
                return 'protonvpn'
            elif protonvpn_connections >= 15:  # ProtonVPN có quá nhiều kết nối
                return 'nordvpn'
            
            # Cân bằng theo tỉ lệ 7:3 (ProtonVPN:NordVPN)
            import random
            if random.random() < 0.7:  # 70% chance cho ProtonVPN
                return 'protonvpn'
            else:  # 30% chance cho NordVPN
                return 'nordvpn'
        
        # 4. Fallback: Cân bằng theo tỉ lệ 7:3
        import random
        if random.random() < 0.7:  # 70% chance cho ProtonVPN
            return 'protonvpn'
        else:  # 30% chance cho NordVPN
            return 'nordvpn'
        
    except Exception as e:
        print(f"Error determining VPN provider: {e}")
        return 'protonvpn'  # Fallback to ProtonVPN

def _is_port_available(port, used_ports, BASE_DIR):
    """Kiểm tra xem port có available không (không có config file và không trong used_ports)"""
    # Kiểm tra port có trong used_ports không
    if port in used_ports:
        return False
    
    # Kiểm tra config file có tồn tại không
    config_file = os.path.join(BASE_DIR, 'config', f'haproxy_{port}.cfg')
    if os.path.exists(config_file):
        return False
    
    return True

def _find_available_port(start_port, used_ports, BASE_DIR, max_port=7999):
    """Tìm port available đầu tiên từ start_port, kiểm tra cả config file và used_ports"""
    for port in range(start_port, max_port + 1):
        if _is_port_available(port, used_ports, BASE_DIR):
            return port
    return None

def _find_orphaned_gost_for_port(requested_port):
    """Tìm orphaned Gost (Gost đang chạy nhưng không có HAProxy tương ứng) phù hợp với port yêu cầu"""
    try:
        # Lấy danh sách services
        status_response = requests.get('http://127.0.0.1:5000/api/status', timeout=10)
        if status_response.status_code != 200:
            return None
        
        status_data = status_response.json()
        haproxy_services = status_data.get('haproxy', [])
        gost_services = status_data.get('gost', [])
        
        # Tính Gost port tương ứng với HAProxy port yêu cầu
        expected_gost_port = 18181 + (requested_port - 7891)
        
        # Tìm Gost đang chạy với port tương ứng
        for gost in gost_services:
            if gost.get('running') and int(gost['port']) == expected_gost_port:
                # Kiểm tra xem có HAProxy tương ứng không
                haproxy_exists = False
                for haproxy in haproxy_services:
                    if int(haproxy.get('port')) == requested_port:
                        haproxy_exists = True
                        break
                
                # Nếu không có HAProxy tương ứng, đây là orphaned Gost
                if not haproxy_exists:
                    return {
                        'port': requested_port,
                        'gost_port': expected_gost_port,
                        'orphaned': True
                    }
        
        return None
    except Exception as e:
        print(f"Error finding orphaned Gost: {e}")
        return None

def _find_available_haproxy_and_gost(profiles, check_server, vpn_provider, check_proxy_port):
    """Tìm HAProxy và Gost đang rảnh (không được sử dụng bởi profiles) hoặc có cùng server và port"""
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
        
        # Tìm Gost đang chạy với cùng server và port (ưu tiên cao nhất)
        for gost in gost_services:
            if gost.get('running'):
                gost_port = int(gost['port'])
                haproxy_port = 7891 + (gost_port - 18181)
                
                # QUAN TRỌNG: Kiểm tra xem HAProxy tương ứng có tồn tại và đang chạy không
                haproxy_exists = False
                haproxy_running = False
                for haproxy in haproxy_services:
                    if haproxy.get('port') == str(haproxy_port):
                        haproxy_exists = True
                        haproxy_running = haproxy.get('running', False)
                        break
                
                # Chỉ xử lý nếu HAProxy tồn tại và đang chạy
                if not haproxy_exists or not haproxy_running:
                    continue  # Bỏ qua orphaned Gost (Gost không có HAProxy tương ứng)
                
                # Kiểm tra server info từ gost
                server_info = gost.get('server_info', '')
                if server_info and ':' in server_info:
                    gost_server, gost_proxy_port = server_info.split(':', 1)
                    # Nếu cùng server và proxy port, tái sử dụng
                    if (gost_server == check_server and 
                        gost_proxy_port == check_proxy_port and 
                        haproxy_port not in used_ports):
                        return {
                            'port': haproxy_port,
                            'gost_port': gost_port,
                            'server': check_server,
                            'vpn_provider': vpn_provider,
                            'same_server': True
                        }
        
        # Nếu không tìm thấy cùng server/port, tìm HAProxy rảnh
        for haproxy in haproxy_services:
            if haproxy.get('running'):
                haproxy_port = int(haproxy.get('port'))
                
                # Kiểm tra xem HAProxy port này có đang được sử dụng bởi profiles không
                if haproxy_port not in used_ports:
                    # Tìm Gost backend tương ứng
                    gost_backend = haproxy.get('gost_backend')
                    if gost_backend:
                        gost_port = int(gost_backend)
                        # Kiểm tra Gost có đang chạy không
                        for gost in gost_services:
                            if int(gost['port']) == gost_port and gost.get('running'):
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
            
            # Validate check_port is a valid integer
            if not check_port or not check_port.isdigit():
                return jsonify({
                    'success': False,
                    'error': f'Invalid port in proxy_check: {check_port}'
                }), 400
            
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
            
            # Determine VPN provider intelligently
            vpn_provider = _determine_smart_vpn_provider(check_server, profiles)
            
            # Lấy danh sách proxy từ profiles
            existing_proxies = []
            for profile in profiles:
                if profile.get('proxy'):
                    proxy_str = profile['proxy']
                    # Skip invalid proxy strings (empty or just colon)
                    if not proxy_str or proxy_str.strip() == ':':
                        continue
                    
                    # Parse socks5://host:port:server:proxy_port format
                    if proxy_str.startswith('socks5://'):
                        proxy_str = proxy_str[9:]
                    
                    parts = proxy_str.split(':')
                    if len(parts) >= 2:
                        # Validate port is a valid integer before adding
                        port = parts[1].strip()
                        if port and port.isdigit():
                            existing_proxies.append({
                                'host': parts[0],
                                'port': port,
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
                available_haproxy = _find_available_haproxy_and_gost(profiles, check_server, vpn_provider, check_proxy_port)
                if available_haproxy:
                    # Sử dụng lại HAProxy đang rảnh
                    haproxy_port = available_haproxy['port']
                    gost_port = available_haproxy['gost_port']
                    
                    # Apply Gost với dữ liệu đã phân tích
                    apply_response, vpn_provider = _apply_server_with_fallback(gost_port, apply_data, vpn_provider)
                    if apply_response is None:
                        return jsonify({
                            'success': False,
                            'error': 'Failed to apply server to both providers'
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
                    
                    return f'socks5://{client_host}:{haproxy_port}:{actual_proxy_host}:{actual_proxy_port}'
                
                # Nếu không có HAProxy rảnh, kiểm tra orphaned Gost hoặc tạo mới
                used_ports = []
                for p in existing_proxies:
                    try:
                        port = int(p['port'])
                        used_ports.append(port)
                    except (ValueError, KeyError):
                        continue  # Skip invalid ports
                
                # Kiểm tra xem có orphaned Gost phù hợp với port yêu cầu không
                requested_port = int(check_port)
                orphaned_gost = _find_orphaned_gost_for_port(requested_port)
                
                if orphaned_gost and _is_port_available(orphaned_gost['port'], used_ports, BASE_DIR):
                    # Sử dụng orphaned Gost và tạo HAProxy mới cho nó
                    logging.info(f"[CHROME_PROXY_CHECK] Case 3: Found orphaned Gost {orphaned_gost['gost_port']}, creating HAProxy {orphaned_gost['port']} for it")
                    new_port = orphaned_gost['port']
                    gost_port = orphaned_gost['gost_port']
                else:
                    # Tìm port mới, kiểm tra cả config file và used_ports
                    new_port = _find_available_port(7891, used_ports, BASE_DIR)
                    
                    if new_port is None:
                        return jsonify({
                            'success': False,
                            'error': 'No available HAProxy ports found'
                        }), 500
                    
                    # Tính Gost port tương ứng
                    gost_port = 18181 + (new_port - 7891)
                
                # Apply Gost với dữ liệu đã phân tích trước
                apply_response, vpn_provider = _apply_server_with_fallback(gost_port, apply_data, vpn_provider)
                if apply_response is None:
                    return jsonify({
                        'success': False,
                        'error': 'Failed to apply server to both providers'
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
                
                # Tạo HAProxy với Gost backend, tự động retry với port tiếp theo nếu port đã tồn tại
                stats_port = new_port + 200
                haproxy_data = {
                    'sock_port': new_port,
                    'stats_port': stats_port,
                    'wg_ports': [gost_port],
                    'host_proxy': '127.0.0.1:8111',
                    'stats_auth': 'admin:admin123',
                    'health_interval': 10
                }
                
                # Retry với port tiếp theo nếu port đã tồn tại
                max_retries = 10
                retry_count = 0
                haproxy_created = False
                
                while retry_count < max_retries:
                    haproxy_response = requests.post('http://127.0.0.1:5000/api/haproxy/create', json=haproxy_data, timeout=20)
                    if haproxy_response.status_code == 200:
                        haproxy_created = True
                        break
                    
                    # Kiểm tra xem có phải lỗi "already exists" không
                    try:
                        error_data = haproxy_response.json()
                        error_msg = error_data.get('error', '')
                        if 'already exists' in error_msg.lower():
                            # Tìm port tiếp theo
                            retry_count += 1
                            old_port = haproxy_data['sock_port']
                            new_port = _find_available_port(old_port + 1, used_ports, BASE_DIR)
                            if new_port is None:
                                return jsonify({
                                    'success': False,
                                    'error': 'No available HAProxy ports found after retries'
                                }), 500
                            
                            # Cập nhật port và gost_port
                            gost_port = 18181 + (new_port - 7891)
                            stats_port = new_port + 200
                            haproxy_data['sock_port'] = new_port
                            haproxy_data['stats_port'] = stats_port
                            haproxy_data['wg_ports'] = [gost_port]
                            
                            # Apply lại Gost với port mới
                            apply_response, vpn_provider = _apply_server_with_fallback(gost_port, apply_data, vpn_provider)
                            if apply_response is None:
                                return jsonify({
                                    'success': False,
                                    'error': 'Failed to apply server to both providers after port change'
                                }), 500
                            
                            # Parse lại response để lấy thông tin server thực tế
                            apply_result = apply_response.json()
                            if apply_result.get('success'):
                                actual_server = apply_result.get('server', {})
                                actual_proxy_host = actual_server.get('hostname') or actual_server.get('domain', check_server if check_server else 'random-server')
                                proxy_url = apply_result.get('proxy_url', '')
                                if proxy_url and ':' in proxy_url:
                                    try:
                                        port_part = proxy_url.split('@')[-1].split(':')[-1]
                                        actual_proxy_port = port_part
                                    except:
                                        actual_proxy_port = '89'
                                else:
                                    actual_proxy_port = '89'
                            else:
                                actual_proxy_host = check_server if check_server else 'random-server'
                                actual_proxy_port = '89'
                            
                            logging.info(f"[CHROME_PROXY_CHECK] Case 3: Port {old_port} already exists, retrying with port {new_port}")
                            continue
                        else:
                            # Lỗi khác, không retry
                            break
                    except:
                        # Không parse được JSON, không retry
                        break
                
                if not haproxy_created:
                    return jsonify({
                        'success': False,
                        'error': f'Failed to create HAProxy: {haproxy_response.text}'
                    }), 500
                
                return f'socks5://{client_host}:{new_port}:{actual_proxy_host}:{actual_proxy_port}'
            
            else:
                # 4. Port gost, proxy_host và proxy_port khác nhau, tạo mới HA và apply gost
                logging.info(f"[CHROME_PROXY_CHECK] Case 4: Different port and server")
                # Trước tiên kiểm tra HAProxy và Gost đang rảnh
                available_haproxy = _find_available_haproxy_and_gost(profiles, check_server, vpn_provider, check_proxy_port)
                if available_haproxy:
                    # Sử dụng lại HAProxy đang rảnh
                    haproxy_port = available_haproxy['port']
                    gost_port = available_haproxy['gost_port']
                    
                    # Kiểm tra xem có phải cùng server không
                    if available_haproxy.get('same_server'):
                        # Cùng server, tái sử dụng trực tiếp
                        logging.info(f"[CHROME_PROXY_CHECK] Reusing HAProxy {haproxy_port} with same server {check_server}")
                        return f'socks5://{client_host}:{haproxy_port}:{check_server}:{check_proxy_port}'
                    
                    # Khác server, apply Gost với dữ liệu đã phân tích
                    apply_response, vpn_provider = _apply_server_with_fallback(gost_port, apply_data, vpn_provider)
                    if apply_response is None:
                        return jsonify({
                            'success': False,
                            'error': 'Failed to apply server to both providers'
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
                    
                    return f'socks5://{client_host}:{haproxy_port}:{actual_proxy_host}:{actual_proxy_port}'
                
                # Nếu không có HAProxy rảnh, kiểm tra orphaned Gost hoặc tạo mới
                used_ports = []
                for p in existing_proxies:
                    try:
                        port = int(p['port'])
                        used_ports.append(port)
                    except (ValueError, KeyError):
                        continue  # Skip invalid ports
                
                # Kiểm tra xem có orphaned Gost phù hợp với port yêu cầu không
                requested_port = int(check_port)
                orphaned_gost = _find_orphaned_gost_for_port(requested_port)
                
                if orphaned_gost and _is_port_available(orphaned_gost['port'], used_ports, BASE_DIR):
                    # Sử dụng orphaned Gost và tạo HAProxy mới cho nó
                    logging.info(f"[CHROME_PROXY_CHECK] Case 4: Found orphaned Gost {orphaned_gost['gost_port']}, creating HAProxy {orphaned_gost['port']} for it")
                    new_port = orphaned_gost['port']
                    gost_port = orphaned_gost['gost_port']
                else:
                    # Tìm port mới, kiểm tra cả config file và used_ports
                    new_port = _find_available_port(7891, used_ports, BASE_DIR)
                    
                    if new_port is None:
                        return jsonify({
                            'success': False,
                            'error': 'No available HAProxy ports found'
                        }), 500
                    
                    # Tính Gost port tương ứng
                    gost_port = 18181 + (new_port - 7891)
                
                # Apply Gost với dữ liệu đã phân tích trước
                apply_response, vpn_provider = _apply_server_with_fallback(gost_port, apply_data, vpn_provider)
                if apply_response is None:
                    return jsonify({
                        'success': False,
                        'error': 'Failed to apply server to both providers'
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
                
                # Tạo HAProxy với Gost backend, tự động retry với port tiếp theo nếu port đã tồn tại
                stats_port = new_port + 200
                haproxy_data = {
                    'sock_port': new_port,
                    'stats_port': stats_port,
                    'wg_ports': [gost_port],
                    'host_proxy': '127.0.0.1:8111',
                    'stats_auth': 'admin:admin123',
                    'health_interval': 10
                }
                
                # Retry với port tiếp theo nếu port đã tồn tại
                max_retries = 10
                retry_count = 0
                haproxy_created = False
                
                while retry_count < max_retries:
                    haproxy_response = requests.post('http://127.0.0.1:5000/api/haproxy/create', json=haproxy_data, timeout=20)
                    if haproxy_response.status_code == 200:
                        haproxy_created = True
                        break
                    
                    # Kiểm tra xem có phải lỗi "already exists" không
                    try:
                        error_data = haproxy_response.json()
                        error_msg = error_data.get('error', '')
                        if 'already exists' in error_msg.lower():
                            # Tìm port tiếp theo
                            retry_count += 1
                            old_port = haproxy_data['sock_port']
                            new_port = _find_available_port(old_port + 1, used_ports, BASE_DIR)
                            if new_port is None:
                                return jsonify({
                                    'success': False,
                                    'error': 'No available HAProxy ports found after retries'
                                }), 500
                            
                            # Cập nhật port và gost_port
                            gost_port = 18181 + (new_port - 7891)
                            stats_port = new_port + 200
                            haproxy_data['sock_port'] = new_port
                            haproxy_data['stats_port'] = stats_port
                            haproxy_data['wg_ports'] = [gost_port]
                            
                            # Apply lại Gost với port mới
                            apply_response, vpn_provider = _apply_server_with_fallback(gost_port, apply_data, vpn_provider)
                            if apply_response is None:
                                return jsonify({
                                    'success': False,
                                    'error': 'Failed to apply server to both providers after port change'
                                }), 500
                            
                            # Parse lại response để lấy thông tin server thực tế
                            apply_result = apply_response.json()
                            if apply_result.get('success'):
                                actual_server = apply_result.get('server', {})
                                actual_proxy_host = actual_server.get('hostname') or actual_server.get('domain', check_server if check_server else 'random-server')
                                proxy_url = apply_result.get('proxy_url', '')
                                if proxy_url and ':' in proxy_url:
                                    try:
                                        port_part = proxy_url.split('@')[-1].split(':')[-1]
                                        actual_proxy_port = port_part
                                    except:
                                        actual_proxy_port = '89'
                                else:
                                    actual_proxy_port = '89'
                            else:
                                actual_proxy_host = check_server if check_server else 'random-server'
                                actual_proxy_port = '89'
                            
                            logging.info(f"[CHROME_PROXY_CHECK] Case 4: Port {old_port} already exists, retrying with port {new_port}")
                            continue
                        else:
                            # Lỗi khác, không retry
                            break
                    except:
                        # Không parse được JSON, không retry
                        break
                
                if not haproxy_created:
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
