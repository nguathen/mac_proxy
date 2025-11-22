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
import time
from functools import lru_cache

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cache cho API status calls (5 giây TTL)
_status_cache = {}
_status_cache_ttl = 5

def _apply_server_with_fallback(gost_port, apply_data, vpn_provider):
    """
    Apply server với fallback logic:
    1. Try primary provider với specific data
    2. Try primary provider với random server
    3. Try alternative provider với specific data
    4. Try alternative provider với random server
    """
    errors = []
    
    # Validate port
    try:
        port_num = int(gost_port)
        if port_num < 7891 or port_num > 7999:
            error_msg = f"Invalid port {port_num}. Port must be between 7891-7999"
            logging.error(f"[APPLY_FALLBACK] {error_msg}")
            return None, error_msg
    except (ValueError, TypeError) as e:
        error_msg = f"Invalid port format: {gost_port} ({str(e)})"
        logging.error(f"[APPLY_FALLBACK] {error_msg}")
        return None, error_msg
    
    # Primary provider
    if vpn_provider == 'nordvpn':
        apply_url = f'http://127.0.0.1:5000/api/nordvpn/apply/{port_num}'
    else:
        apply_url = f'http://127.0.0.1:5000/api/protonvpn/apply/{port_num}'
    
    # Try primary provider với specific data
    try:
        logging.info(f"[APPLY_FALLBACK] Trying {vpn_provider} with specific data: {apply_data}")
        apply_response = requests.post(apply_url, json=apply_data, timeout=15)
        if apply_response.status_code == 200:
            logging.info(f"[APPLY_FALLBACK] ✅ {vpn_provider} succeeded with specific data")
            return apply_response, vpn_provider
        else:
            error_msg = f"{vpn_provider} returned {apply_response.status_code}"
            try:
                error_body = apply_response.json()
                error_msg += f": {error_body.get('error', 'Unknown error')}"
            except:
                error_msg += f": {apply_response.text[:200]}"
            errors.append(error_msg)
            logging.warning(f"[APPLY_FALLBACK] {error_msg}")
    except requests.exceptions.RequestException as e:
        error_msg = f"{vpn_provider} request failed: {str(e)}"
        errors.append(error_msg)
        logging.error(f"[APPLY_FALLBACK] {error_msg}")
    
    # Try primary provider với random server
    try:
        logging.info(f"[APPLY_FALLBACK] Trying {vpn_provider} with random server...")
        fallback_data = {}  # Empty data for random server
        fallback_response = requests.post(apply_url, json=fallback_data, timeout=15)
        if fallback_response.status_code == 200:
            logging.info(f"[APPLY_FALLBACK] ✅ {vpn_provider} succeeded with random server")
            return fallback_response, vpn_provider
        else:
            error_msg = f"{vpn_provider} random returned {fallback_response.status_code}"
            try:
                error_body = fallback_response.json()
                error_msg += f": {error_body.get('error', 'Unknown error')}"
            except:
                error_msg += f": {fallback_response.text[:200]}"
            errors.append(error_msg)
            logging.warning(f"[APPLY_FALLBACK] {error_msg}")
    except requests.exceptions.RequestException as e:
        error_msg = f"{vpn_provider} random request failed: {str(e)}"
        errors.append(error_msg)
        logging.error(f"[APPLY_FALLBACK] {error_msg}")
    
    # Try alternative provider
    alternative_provider = 'protonvpn' if vpn_provider == 'nordvpn' else 'nordvpn'
    alternative_url = f'http://127.0.0.1:5000/api/{alternative_provider}/apply/{port_num}'
    
    # Try alternative provider với specific data
    try:
        logging.info(f"[APPLY_FALLBACK] Trying alternative {alternative_provider} with specific data: {apply_data}")
        alt_response = requests.post(alternative_url, json=apply_data, timeout=15)
        if alt_response.status_code == 200:
            logging.info(f"[APPLY_FALLBACK] ✅ Alternative provider {alternative_provider} succeeded")
            return alt_response, alternative_provider
        else:
            error_msg = f"{alternative_provider} returned {alt_response.status_code}"
            try:
                error_body = alt_response.json()
                error_msg += f": {error_body.get('error', 'Unknown error')}"
            except:
                error_msg += f": {alt_response.text[:200]}"
            errors.append(error_msg)
            logging.warning(f"[APPLY_FALLBACK] {error_msg}")
    except requests.exceptions.RequestException as e:
        error_msg = f"{alternative_provider} request failed: {str(e)}"
        errors.append(error_msg)
        logging.error(f"[APPLY_FALLBACK] {error_msg}")
    
    # Try alternative provider với random server
    try:
        logging.info(f"[APPLY_FALLBACK] Trying alternative {alternative_provider} with random server...")
        alt_random_response = requests.post(alternative_url, json={}, timeout=15)
        if alt_random_response.status_code == 200:
            logging.info(f"[APPLY_FALLBACK] ✅ Alternative provider {alternative_provider} random server succeeded")
            return alt_random_response, alternative_provider
        else:
            error_msg = f"{alternative_provider} random returned {alt_random_response.status_code}"
            try:
                error_body = alt_random_response.json()
                error_msg += f": {error_body.get('error', 'Unknown error')}"
            except:
                error_msg += f": {alt_random_response.text[:200]}"
            errors.append(error_msg)
            logging.warning(f"[APPLY_FALLBACK] {error_msg}")
    except requests.exceptions.RequestException as e:
        error_msg = f"{alternative_provider} random request failed: {str(e)}"
        errors.append(error_msg)
        logging.error(f"[APPLY_FALLBACK] {error_msg}")
    
    # All failed - log all errors
    error_summary = "; ".join(errors)
    logging.error(f"[APPLY_FALLBACK] All attempts failed. Errors: {error_summary}")
    return None, error_summary

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
    
    # Kiểm tra Gost config file có tồn tại không
    config_file = os.path.join(BASE_DIR, 'config', f'gost_{port}.config')
    if os.path.exists(config_file):
        return False
    
    return True

def _find_available_port(start_port, used_ports, BASE_DIR, max_port=7999):
    """Tìm port available đầu tiên từ start_port, kiểm tra cả config file và used_ports"""
    for port in range(start_port, max_port + 1):
        if _is_port_available(port, used_ports, BASE_DIR):
            return port
    return None

def _check_gost_running(port, BASE_DIR, max_wait=5):
    """
    Kiểm tra xem Gost có thực sự đang chạy không sau khi restart
    Returns: (is_running, error_message)
    """
    try:
        import subprocess
        
        # Đợi một chút để Gost khởi động
        time.sleep(2)
        
        # Kiểm tra PID file
        pid_file = os.path.join(BASE_DIR, 'logs', f'gost_{port}.pid')
        if not os.path.exists(pid_file):
            return False, f"PID file not found for port {port}"
        
        try:
            with open(pid_file, 'r') as f:
                pid = f.read().strip()
            
            if not pid:
                return False, f"PID file is empty for port {port}"
            
            # Kiểm tra process có đang chạy không
            try:
                result = subprocess.run(
                    f'kill -0 {pid}',
                    shell=True,
                    capture_output=True,
                    timeout=2
                )
            except Exception as e:
                return False, f"Error checking process: {str(e)}"
            
            if result.returncode == 0:
                # Process đang chạy, kiểm tra thêm port có đang listen không
                time.sleep(1)  # Đợi thêm một chút để port được bind
                
                # Kiểm tra port có đang listen không (optional check)
                try:
                    # Try lsof first
                    port_check = subprocess.run(
                        f'lsof -ti :{port}',
                        shell=True,
                        capture_output=True,
                        timeout=2
                    )
                    if port_check.returncode == 0:
                        try:
                            stdout_text = port_check.stdout.decode('utf-8', errors='ignore')
                            if pid in stdout_text.split():
                                return True, None
                        except Exception:
                            pass
                    # Fallback: nếu không có lsof hoặc không match, chỉ cần process đang chạy là đủ
                    return True, None
                except Exception:
                    # Nếu không kiểm tra được port, chỉ cần process đang chạy là đủ
                    return True, None
            else:
                return False, f"Process {pid} is not running for port {port}"
        except Exception as e:
            return False, f"Error reading PID file: {str(e)}"
    except Exception as e:
        return False, f"Error checking Gost status: {str(e)}"

def _get_cached_status():
    """Lấy status với caching để giảm API calls"""
    global _status_cache
    current_time = time.time()
    
    # Kiểm tra cache
    if 'data' in _status_cache and 'timestamp' in _status_cache:
        if current_time - _status_cache['timestamp'] < _status_cache_ttl:
            return _status_cache['data']
    
    # Fetch mới
    try:
        status_response = requests.get('http://127.0.0.1:5000/api/status', timeout=10)
        if status_response.status_code == 200:
            status_data = status_response.json()
            _status_cache = {
                'data': status_data,
                'timestamp': current_time
            }
            return status_data
    except Exception as e:
        logging.warning(f"[CACHE] Failed to fetch status: {e}")
        # Return cached data nếu có, dù đã hết hạn
        if 'data' in _status_cache:
            return _status_cache['data']
    
    return None

def _find_orphaned_gost_for_port(requested_port):
    """Tìm Gost đang chạy với port yêu cầu"""
    try:
        # Lấy danh sách services với cache
        status_data = _get_cached_status()
        if status_data is None:
            return None
        
        gost_services = status_data.get('gost', [])
        
        # Tìm Gost đang chạy với port yêu cầu (Gost giờ chạy trực tiếp trên 789x)
        # Chỉ tìm port hợp lệ (7891-7999)
        if requested_port < 7891 or requested_port > 7999:
            return None
            
        for gost in gost_services:
            if gost.get('running') and int(gost['port']) == requested_port:
                return {
                    'port': requested_port,
                    'gost_port': requested_port,
                    'orphaned': False
                }
        
        return None
    except Exception as e:
        print(f"Error finding Gost: {e}")
        return None

def _find_available_gost(profiles, check_server, vpn_provider, check_proxy_port):
    """Tìm Gost đang rảnh (không được sử dụng bởi profiles) hoặc có cùng server và port"""
    try:
        # Lấy danh sách Gost đang chạy với cache
        status_data = _get_cached_status()
        if status_data is None:
            return None
        
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
                
                # Skip port không hợp lệ (phải trong khoảng 7891-7999)
                if gost_port < 7891 or gost_port > 7999:
                    continue
                
                # Kiểm tra server info từ gost
                server_info = gost.get('server_info', '')
                if server_info and ':' in server_info:
                    gost_server, gost_proxy_port = server_info.split(':', 1)
                    # Nếu cùng server và proxy port, tái sử dụng
                    if (gost_server == check_server and 
                        gost_proxy_port == check_proxy_port and 
                        gost_port not in used_ports):
                        return {
                            'port': gost_port,
                            'gost_port': gost_port,
                            'server': check_server,
                            'vpn_provider': vpn_provider,
                            'same_server': True
                        }
        
        # Nếu không tìm thấy cùng server/port, tìm Gost rảnh
        for gost in gost_services:
            if gost.get('running'):
                gost_port = int(gost['port'])
                
                # Skip port không hợp lệ (phải trong khoảng 7891-7999)
                if gost_port < 7891 or gost_port > 7999:
                    continue
                
                # Kiểm tra xem Gost port này có đang được sử dụng bởi profiles không
                if gost_port not in used_ports:
                    return {
                        'port': gost_port,
                        'gost_port': gost_port,
                        'server': check_server,
                        'vpn_provider': vpn_provider
                    }
        
        return None
    except Exception as e:
        print(f"Error finding available Gost: {e}")
        return None

def register_chrome_routes(app, BASE_DIR, get_available_gost_ports, _get_proxy_port):
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
            
            # Validate check_port is in valid range (7891-7999)
            check_port_num = int(check_port)
            if check_port_num < 7891 or check_port_num > 7999:
                logging.warning(f"[CHROME_PROXY_CHECK] check_port {check_port_num} is out of valid range (7891-7999), will find new port")
                # Không return error, chỉ log warning và sẽ tìm port mới sau
            
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
                # 3. Trùng port gost, proxy_host và proxy_port khác nhau thì tạo mới Gost
                logging.info(f"[CHROME_PROXY_CHECK] Case 3: Same port, different server")
                # Trước tiên kiểm tra Gost đang rảnh
                available_gost = _find_available_gost(profiles, check_server, vpn_provider, check_proxy_port)
                if available_gost:
                    # Sử dụng lại Gost đang rảnh
                    gost_port = available_gost['port']
                    logging.info(f"[CHROME_PROXY_CHECK] Case 3: Using available Gost port: {gost_port} (type: {type(gost_port).__name__})")
                    
                    # Apply Gost với dữ liệu đã phân tích
                    logging.info(f"[CHROME_PROXY_CHECK] Case 3: Applying server to port {gost_port} with data: {apply_data}, provider: {vpn_provider}")
                    apply_response, result = _apply_server_with_fallback(gost_port, apply_data, vpn_provider)
                    if apply_response is None:
                        error_msg = result if isinstance(result, str) else 'Failed to apply server to both providers'
                        logging.error(f"[CHROME_PROXY_CHECK] Case 3: Failed to apply server: {error_msg}")
                        return jsonify({
                            'success': False,
                            'error': f'Failed to apply server: {error_msg}'
                        }), 500
                    vpn_provider = result
                    logging.info(f"[CHROME_PROXY_CHECK] Case 3: Successfully applied server, provider: {vpn_provider}")
                    
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
                    
                    return f'socks5://{client_host}:{gost_port}:{actual_proxy_host}:{actual_proxy_port}'
                
                # Nếu không có Gost rảnh, kiểm tra orphaned Gost hoặc tạo mới
                used_ports = []
                for p in existing_proxies:
                    try:
                        port = int(p['port'])
                        used_ports.append(port)
                    except (ValueError, KeyError):
                        continue  # Skip invalid ports
                
                # Kiểm tra xem có Gost phù hợp với port yêu cầu không
                requested_port = int(check_port)
                orphaned_gost = _find_orphaned_gost_for_port(requested_port)
                
                if orphaned_gost and _is_port_available(orphaned_gost['port'], used_ports, BASE_DIR):
                    # Sử dụng Gost đang chạy
                    logging.info(f"[CHROME_PROXY_CHECK] Case 3: Found Gost {orphaned_gost['gost_port']} on port {orphaned_gost['port']}")
                    new_port = orphaned_gost['port']
                    gost_port = orphaned_gost['gost_port']
                else:
                    # Tìm port mới, kiểm tra cả config file và used_ports
                    new_port = _find_available_port(7891, used_ports, BASE_DIR)
                    
                    if new_port is None:
                        return jsonify({
                            'success': False,
                            'error': 'No available Gost ports found'
                        }), 500
                    
                    # Gost port = new_port (chạy trực tiếp trên 789x)
                    gost_port = new_port
                
                logging.info(f"[CHROME_PROXY_CHECK] Case 3: Using new Gost port: {gost_port} (type: {type(gost_port).__name__})")
                
                # Apply Gost với dữ liệu đã phân tích, tự động retry với port tiếp theo nếu port đã tồn tại
                max_retries = 10
                retry_count = 0
                gost_created = False
                
                while retry_count < max_retries:
                    # Apply Gost với port mới
                    logging.info(f"[CHROME_PROXY_CHECK] Case 3: Attempt {retry_count + 1}/{max_retries} - Applying to port {gost_port} with data: {apply_data}, provider: {vpn_provider}")
                    apply_response, result = _apply_server_with_fallback(gost_port, apply_data, vpn_provider)
                    if apply_response is None:
                        error_msg = result if isinstance(result, str) else 'Failed to apply server to both providers'
                        return jsonify({
                            'success': False,
                            'error': f'Failed to apply server: {error_msg}'
                        }), 500
                    vpn_provider = result
                    
                    # Parse response để lấy thông tin server thực tế
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
                    
                    # Kiểm tra xem Gost đã được tạo và chạy chưa
                    try:
                        # Start Gost service
                        import subprocess
                        result = subprocess.run(
                            f'bash manage_gost.sh restart-port {gost_port}',
                            shell=True,
                            cwd=BASE_DIR,
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if result.returncode == 0:
                            # Kiểm tra xem Gost có thực sự đang chạy không
                            is_running, error_msg = _check_gost_running(gost_port, BASE_DIR)
                            if is_running:
                                gost_created = True
                                logging.info(f"[CHROME_PROXY_CHECK] Case 3: Gost on port {gost_port} is running")
                                break
                            else:
                                logging.warning(f"[CHROME_PROXY_CHECK] Case 3: Gost on port {gost_port} failed to start: {error_msg}")
                                # Kiểm tra log để xem có lỗi gì không
                                log_file = os.path.join(BASE_DIR, 'logs', f'gost_{gost_port}.log')
                                if os.path.exists(log_file):
                                    try:
                                        with open(log_file, 'r') as f:
                                            log_lines = f.readlines()
                                            if log_lines:
                                                last_lines = ''.join(log_lines[-10:])
                                                logging.error(f"[CHROME_PROXY_CHECK] Last 10 log lines: {last_lines}")
                                    except:
                                        pass
                                # Retry với port khác
                                retry_count += 1
                                if retry_count < max_retries:
                                    old_port = gost_port
                                    new_port = _find_available_port(old_port + 1, used_ports, BASE_DIR)
                                    if new_port is None:
                                        return jsonify({
                                            'success': False,
                                            'error': f'No available Gost ports found. Last error: {error_msg}'
                                        }), 500
                                    gost_port = new_port
                                    logging.info(f"[CHROME_PROXY_CHECK] Case 3: Retrying with port {new_port}")
                                    continue
                                else:
                                    return jsonify({
                                        'success': False,
                                        'error': f'Failed to start Gost after {max_retries} retries. Last error: {error_msg}'
                                    }), 500
                        else:
                            # Kiểm tra xem có phải lỗi port đã được sử dụng không
                            if 'already' in result.stderr.lower() or 'in use' in result.stderr.lower():
                                retry_count += 1
                                old_port = gost_port
                                new_port = _find_available_port(old_port + 1, used_ports, BASE_DIR)
                                if new_port is None:
                                    return jsonify({
                                        'success': False,
                                        'error': 'No available Gost ports found after retries'
                                    }), 500
                                gost_port = new_port
                                logging.info(f"[CHROME_PROXY_CHECK] Case 3: Port {old_port} already exists, retrying with port {new_port}")
                                continue
                            else:
                                logging.error(f"[CHROME_PROXY_CHECK] Case 3: restart-port failed: {result.stderr}")
                                break
                    except Exception as e:
                        logging.error(f"[CHROME_PROXY_CHECK] Error starting Gost: {e}")
                        break
                
                if not gost_created:
                    return jsonify({
                        'success': False,
                        'error': f'Failed to create Gost on port {gost_port}'
                    }), 500
                
                return f'socks5://{client_host}:{gost_port}:{actual_proxy_host}:{actual_proxy_port}'
            
            else:
                # 4. Port gost, proxy_host và proxy_port khác nhau, tạo mới Gost
                logging.info(f"[CHROME_PROXY_CHECK] Case 4: Different port and server")
                # Trước tiên kiểm tra Gost đang rảnh
                available_gost = _find_available_gost(profiles, check_server, vpn_provider, check_proxy_port)
                if available_gost:
                    # Sử dụng lại Gost đang rảnh
                    gost_port = available_gost['port']
                    logging.info(f"[CHROME_PROXY_CHECK] Case 4: Using available Gost port: {gost_port} (type: {type(gost_port).__name__})")
                    
                    # Kiểm tra xem có phải cùng server không
                    if available_gost.get('same_server'):
                        # Cùng server, tái sử dụng trực tiếp
                        logging.info(f"[CHROME_PROXY_CHECK] Reusing Gost {gost_port} with same server {check_server}")
                        return f'socks5://{client_host}:{gost_port}:{check_server}:{check_proxy_port}'
                    
                    # Khác server, apply Gost với dữ liệu đã phân tích
                    logging.info(f"[CHROME_PROXY_CHECK] Case 4: Applying server to port {gost_port} with data: {apply_data}, provider: {vpn_provider}")
                    apply_response, result = _apply_server_with_fallback(gost_port, apply_data, vpn_provider)
                    if apply_response is None:
                        error_msg = result if isinstance(result, str) else 'Failed to apply server to both providers'
                        logging.error(f"[CHROME_PROXY_CHECK] Case 4: Failed to apply server: {error_msg}")
                        return jsonify({
                            'success': False,
                            'error': f'Failed to apply server: {error_msg}'
                        }), 500
                    vpn_provider = result
                    logging.info(f"[CHROME_PROXY_CHECK] Case 4: Successfully applied server, provider: {vpn_provider}")
                    
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
                    
                    return f'socks5://{client_host}:{gost_port}:{actual_proxy_host}:{actual_proxy_port}'
                
                # Nếu không có Gost rảnh, kiểm tra Gost đang chạy hoặc tạo mới
                used_ports = []
                for p in existing_proxies:
                    try:
                        port = int(p['port'])
                        used_ports.append(port)
                    except (ValueError, KeyError):
                        continue  # Skip invalid ports
                
                # Kiểm tra xem có Gost phù hợp với port yêu cầu không
                requested_port = int(check_port)
                orphaned_gost = _find_orphaned_gost_for_port(requested_port)
                
                if orphaned_gost and _is_port_available(orphaned_gost['port'], used_ports, BASE_DIR):
                    # Sử dụng Gost đang chạy
                    logging.info(f"[CHROME_PROXY_CHECK] Case 4: Found Gost {orphaned_gost['gost_port']} on port {orphaned_gost['port']}")
                    new_port = orphaned_gost['port']
                    gost_port = orphaned_gost['gost_port']
                else:
                    # Tìm port mới, kiểm tra cả config file và used_ports
                    new_port = _find_available_port(7891, used_ports, BASE_DIR)
                    
                    if new_port is None:
                        return jsonify({
                            'success': False,
                            'error': 'No available Gost ports found'
                        }), 500
                    
                    # Gost port = new_port (chạy trực tiếp trên 789x)
                    gost_port = new_port
                
                logging.info(f"[CHROME_PROXY_CHECK] Case 4: Using new Gost port: {gost_port} (type: {type(gost_port).__name__})")
                
                # Apply Gost với dữ liệu đã phân tích, tự động retry với port tiếp theo nếu port đã tồn tại
                max_retries = 10
                retry_count = 0
                gost_created = False
                
                while retry_count < max_retries:
                    # Apply Gost với port mới
                    logging.info(f"[CHROME_PROXY_CHECK] Case 4: Attempt {retry_count + 1}/{max_retries} - Applying to port {gost_port} with data: {apply_data}, provider: {vpn_provider}")
                    apply_response, result = _apply_server_with_fallback(gost_port, apply_data, vpn_provider)
                    if apply_response is None:
                        error_msg = result if isinstance(result, str) else 'Failed to apply server to both providers'
                        return jsonify({
                            'success': False,
                            'error': f'Failed to apply server: {error_msg}'
                        }), 500
                    vpn_provider = result
                    
                    # Parse response để lấy thông tin server thực tế
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
                    
                    # Kiểm tra xem Gost đã được tạo và chạy chưa
                    try:
                        # Start Gost service
                        import subprocess
                        result = subprocess.run(
                            f'bash manage_gost.sh restart-port {gost_port}',
                            shell=True,
                            cwd=BASE_DIR,
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if result.returncode == 0:
                            # Kiểm tra xem Gost có thực sự đang chạy không
                            is_running, error_msg = _check_gost_running(gost_port, BASE_DIR)
                            if is_running:
                                gost_created = True
                                logging.info(f"[CHROME_PROXY_CHECK] Case 4: Gost on port {gost_port} is running")
                                break
                            else:
                                logging.warning(f"[CHROME_PROXY_CHECK] Case 4: Gost on port {gost_port} failed to start: {error_msg}")
                                # Kiểm tra log để xem có lỗi gì không
                                log_file = os.path.join(BASE_DIR, 'logs', f'gost_{gost_port}.log')
                                if os.path.exists(log_file):
                                    try:
                                        with open(log_file, 'r') as f:
                                            log_lines = f.readlines()
                                            if log_lines:
                                                last_lines = ''.join(log_lines[-10:])
                                                logging.error(f"[CHROME_PROXY_CHECK] Last 10 log lines: {last_lines}")
                                    except:
                                        pass
                                # Retry với port khác
                                retry_count += 1
                                if retry_count < max_retries:
                                    old_port = gost_port
                                    new_port = _find_available_port(old_port + 1, used_ports, BASE_DIR)
                                    if new_port is None:
                                        return jsonify({
                                            'success': False,
                                            'error': f'No available Gost ports found. Last error: {error_msg}'
                                        }), 500
                                    gost_port = new_port
                                    logging.info(f"[CHROME_PROXY_CHECK] Case 4: Retrying with port {new_port}")
                                    continue
                                else:
                                    return jsonify({
                                        'success': False,
                                        'error': f'Failed to start Gost after {max_retries} retries. Last error: {error_msg}'
                                    }), 500
                        else:
                            # Kiểm tra xem có phải lỗi port đã được sử dụng không
                            if 'already' in result.stderr.lower() or 'in use' in result.stderr.lower():
                                retry_count += 1
                                old_port = gost_port
                                new_port = _find_available_port(old_port + 1, used_ports, BASE_DIR)
                                if new_port is None:
                                    return jsonify({
                                        'success': False,
                                        'error': 'No available Gost ports found after retries'
                                    }), 500
                                gost_port = new_port
                                logging.info(f"[CHROME_PROXY_CHECK] Case 4: Port {old_port} already exists, retrying with port {new_port}")
                                continue
                            else:
                                logging.error(f"[CHROME_PROXY_CHECK] Case 4: restart-port failed: {result.stderr}")
                                break
                    except Exception as e:
                        logging.error(f"[CHROME_PROXY_CHECK] Error starting Gost: {e}")
                        break
                
                if not gost_created:
                    return jsonify({
                        'success': False,
                        'error': f'Failed to create Gost on port {gost_port}'
                    }), 500
                
                return f'socks5://{client_host}:{gost_port}:{actual_proxy_host}:{actual_proxy_port}'
            
        except Exception as e:
            logging.error(f"[CHROME_PROXY_CHECK] Error: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
