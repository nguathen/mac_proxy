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

def _try_apply_request(provider, port_num, apply_data, is_random=False):
    """
    Thử apply request với provider và data cho trước
    Returns: (response, error_msg) - response là None nếu failed
    """
    apply_url = f'http://127.0.0.1:5000/api/{provider}/apply/{port_num}'
    data_label = "random server" if is_random else "specific data"
    
    try:
        logging.info(f"[APPLY_FALLBACK] Trying {provider} with {data_label}: {apply_data if not is_random else '{}'}")
        response = requests.post(apply_url, json=apply_data, timeout=60)
        if response.status_code == 200:
            logging.info(f"[APPLY_FALLBACK] ✅ {provider} succeeded with {data_label}")
            return response, None
        else:
            error_msg = f"{provider} {data_label} returned {response.status_code}"
            try:
                error_body = response.json()
                error_msg += f": {error_body.get('error', 'Unknown error')}"
            except:
                error_msg += f": {response.text[:200]}"
            logging.warning(f"[APPLY_FALLBACK] {error_msg}")
            return None, error_msg
    except requests.exceptions.RequestException as e:
        error_msg = f"{provider} {data_label} request failed: {str(e)}"
        logging.error(f"[APPLY_FALLBACK] {error_msg}")
        return None, error_msg

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
    
    # Try primary provider với specific data
    response, error = _try_apply_request(vpn_provider, port_num, apply_data, is_random=False)
    if response:
        return response, vpn_provider
    if error:
        errors.append(error)
    
    # Try primary provider với random server
    response, error = _try_apply_request(vpn_provider, port_num, {}, is_random=True)
    if response:
        return response, vpn_provider
    if error:
        errors.append(error)
    
    # Try alternative provider
    alternative_provider = 'protonvpn' if vpn_provider == 'nordvpn' else 'nordvpn'
    
    # Try alternative provider với specific data
    response, error = _try_apply_request(alternative_provider, port_num, apply_data, is_random=False)
    if response:
        return response, alternative_provider
    if error:
        errors.append(error)
    
    # Try alternative provider với random server
    response, error = _try_apply_request(alternative_provider, port_num, {}, is_random=True)
    if response:
        return response, alternative_provider
    if error:
        errors.append(error)
    
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
    return 'protonvpn'  # Simplified: always use ProtonVPN
    
    # Code below is disabled but kept for reference
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
        
        # Đợi một chút để Gost khởi động (giảm từ 2s xuống 1s)
        time.sleep(1)
        
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
                    timeout=1
                )
            except Exception as e:
                return False, f"Error checking process: {str(e)}"
            
            if result.returncode == 0:
                # Process đang chạy, kiểm tra thêm port có đang listen không
                time.sleep(0.5)  # Đợi thêm một chút để port được bind (giảm từ 1s xuống 0.5s)
                
                # Kiểm tra port có đang listen không (optional check)
                try:
                    # Try lsof first
                    port_check = subprocess.run(
                        f'lsof -ti :{port}',
                        shell=True,
                        capture_output=True,
                        timeout=1
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

def _wait_for_gost_ready(port, BASE_DIR, max_wait=30, check_interval=0.5):
    """
    Đợi gost hoạt động sẵn sàng trước khi return
    Kiểm tra process đang chạy và port đang listen
    Returns: (is_ready, error_message)
    """
    try:
        import subprocess
        
        start_time = time.time()
        pid_file = os.path.join(BASE_DIR, 'logs', f'gost_{port}.pid')
        
        # Quick check first - if Gost is already running, return immediately
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid = f.read().strip()
                
                if pid:
                    # Quick process check
                    try:
                        result = subprocess.run(
                            f'kill -0 {pid}',
                            shell=True,
                            capture_output=True,
                            timeout=1
                        )
                        if result.returncode == 0:
                            # Quick port check
                            try:
                                port_check = subprocess.run(
                                    f'lsof -ti :{port}',
                                    shell=True,
                                    capture_output=True,
                                    timeout=1
                                )
                                if port_check.returncode == 0:
                                    try:
                                        stdout_text = port_check.stdout.decode('utf-8', errors='ignore')
                                        if pid in stdout_text.split():
                                            logging.info(f"[WAIT_GOST] Gost on port {port} is ready (quick check)")
                                            return True, None
                                    except Exception:
                                        pass
                                
                                # Fallback: nc check
                                nc_check = subprocess.run(
                                    f'nc -z 127.0.0.1 {port}',
                                    shell=True,
                                    capture_output=True,
                                    timeout=1
                                )
                                if nc_check.returncode == 0:
                                    logging.info(f"[WAIT_GOST] Gost on port {port} is ready (quick check)")
                                    return True, None
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass
        
        # If quick check failed, do full wait loop
        while time.time() - start_time < max_wait:
            # Kiểm tra PID file
            if not os.path.exists(pid_file):
                time.sleep(check_interval)
                continue
            
            try:
                with open(pid_file, 'r') as f:
                    pid = f.read().strip()
                
                if not pid:
                    time.sleep(check_interval)
                    continue
                
                # Kiểm tra process có đang chạy không
                try:
                    result = subprocess.run(
                        f'kill -0 {pid}',
                        shell=True,
                        capture_output=True,
                        timeout=1
                    )
                except Exception:
                    time.sleep(check_interval)
                    continue
                
                if result.returncode == 0:
                    # Process đang chạy, kiểm tra port có đang listen không
                    try:
                        # Try lsof first
                        port_check = subprocess.run(
                            f'lsof -ti :{port}',
                            shell=True,
                            capture_output=True,
                            timeout=1
                        )
                        if port_check.returncode == 0:
                            try:
                                stdout_text = port_check.stdout.decode('utf-8', errors='ignore')
                                if pid in stdout_text.split():
                                    logging.info(f"[WAIT_GOST] Gost on port {port} is ready (PID: {pid})")
                                    return True, None
                            except Exception:
                                pass
                        
                        # Fallback: kiểm tra bằng nc hoặc ss
                        nc_check = subprocess.run(
                            f'nc -z 127.0.0.1 {port}',
                            shell=True,
                            capture_output=True,
                            timeout=1
                        )
                        if nc_check.returncode == 0:
                            logging.info(f"[WAIT_GOST] Gost on port {port} is ready (port listening)")
                            return True, None
                    except Exception:
                        pass
                
            except Exception:
                pass
            
            time.sleep(check_interval)
        
        # Timeout
        return False, f"Timeout waiting for gost on port {port} to be ready (waited {max_wait}s)"
    except Exception as e:
        return False, f"Error waiting for gost: {str(e)}"

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
        status_response = requests.get('http://127.0.0.1:5000/api/status', timeout=30)
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

def _parse_proxy_string(proxy_str):
    """
    Parse proxy string từ format socks5://host:port:server:proxy_port hoặc host:port:server:proxy_port
    Returns: dict với keys: host, port, server, proxy_port hoặc None nếu invalid
    """
    if not proxy_str or proxy_str.strip() == ':':
        return None
    
    # Remove socks5:// prefix if present
    if proxy_str.startswith('socks5://'):
        proxy_str = proxy_str[9:]
    
    parts = proxy_str.split(':')
    if len(parts) < 2:
        return None
    
    port = parts[1].strip()
    if not port or not port.isdigit():
        return None
    
    return {
        'host': parts[0],
        'port': port,
        'server': parts[2] if len(parts) >= 3 else '',
        'proxy_port': parts[3] if len(parts) >= 4 else ''
    }

def _extract_used_ports(existing_proxies):
    """Extract danh sách ports đang được sử dụng từ existing_proxies"""
    used_ports = []
    for p in existing_proxies:
        try:
            port = int(p['port'])
            used_ports.append(port)
        except (ValueError, KeyError):
            continue
    return used_ports

def _parse_apply_result(apply_result, check_server):
    """
    Parse apply_result để lấy actual_proxy_host và actual_proxy_port
    Returns: (actual_proxy_host, actual_proxy_port)
    """
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
    return actual_proxy_host, actual_proxy_port

def _wait_and_log_gost_ready(port, BASE_DIR, case_num, max_wait=30):
    """
    Đợi gost hoạt động và log kết quả
    Returns: is_ready (bool)
    """
    logging.info(f"[CHROME_PROXY_CHECK] Case {case_num}: Waiting for gost on port {port} to be ready...")
    is_ready, error_msg = _wait_for_gost_ready(port, BASE_DIR, max_wait=max_wait)
    if not is_ready:
        logging.warning(f"[CHROME_PROXY_CHECK] Case {case_num}: Gost on port {port} not ready: {error_msg}, but continuing...")
    else:
        logging.info(f"[CHROME_PROXY_CHECK] Case {case_num}: Gost on port {port} is ready")
    return is_ready

def _apply_server_and_parse(port, apply_data, vpn_provider, check_server):
    """
    Apply server và parse response
    Returns: (success, actual_proxy_host, actual_proxy_port, vpn_provider, error_msg)
    """
    apply_response, result = _apply_server_with_fallback(port, apply_data, vpn_provider)
    if apply_response is None:
        error_msg = result if isinstance(result, str) else 'Failed to apply server to both providers'
        return False, None, None, None, error_msg
    
    vpn_provider = result
    apply_result = apply_response.json()
    actual_proxy_host, actual_proxy_port = _parse_apply_result(apply_result, check_server)
    return True, actual_proxy_host, actual_proxy_port, vpn_provider, None

def _create_gost_with_retry(gost_port, apply_data, vpn_provider, check_server, used_ports, BASE_DIR, case_num, max_retries=10):
    """
    Tạo gost mới với retry logic
    Returns: (success, gost_port, actual_proxy_host, actual_proxy_port, vpn_provider, error_msg)
    """
    import subprocess
    
    retry_count = 0
    gost_created = False
    actual_proxy_host = None
    actual_proxy_port = None
    
    while retry_count < max_retries:
        logging.info(f"[CHROME_PROXY_CHECK] Case {case_num}: Attempt {retry_count + 1}/{max_retries} - Applying to port {gost_port} with data: {apply_data}, provider: {vpn_provider}")
        
        # Apply server
        success, actual_proxy_host, actual_proxy_port, vpn_provider, error_msg = _apply_server_and_parse(
            gost_port, apply_data, vpn_provider, check_server
        )
        if not success:
            return False, gost_port, None, None, None, error_msg
        
        # Start Gost service
        try:
            result = subprocess.run(
                f'bash manage_gost.sh restart-port {gost_port}',
                shell=True,
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                is_running, error_msg = _check_gost_running(gost_port, BASE_DIR)
                if is_running:
                    gost_created = True
                    logging.info(f"[CHROME_PROXY_CHECK] Case {case_num}: Gost on port {gost_port} is running")
                    break
                else:
                    logging.warning(f"[CHROME_PROXY_CHECK] Case {case_num}: Gost on port {gost_port} failed to start: {error_msg}")
                    # Check log file
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
            else:
                # Check if port already in use
                if 'already' in result.stderr.lower() or 'in use' in result.stderr.lower():
                    error_msg = f"Port {gost_port} already in use"
                else:
                    error_msg = f"restart-port failed: {result.stderr}"
                    logging.error(f"[CHROME_PROXY_CHECK] Case {case_num}: {error_msg}")
                    break
            
            # Retry with next port
            retry_count += 1
            if retry_count < max_retries:
                old_port = gost_port
                new_port = _find_available_port(old_port + 1, used_ports, BASE_DIR)
                if new_port is None:
                    return False, gost_port, None, None, None, f'No available Gost ports found. Last error: {error_msg}'
                gost_port = new_port
                logging.info(f"[CHROME_PROXY_CHECK] Case {case_num}: Retrying with port {new_port}")
                continue
            else:
                return False, gost_port, None, None, None, f'Failed to start Gost after {max_retries} retries. Last error: {error_msg}'
                
        except Exception as e:
            logging.error(f"[CHROME_PROXY_CHECK] Error starting Gost: {e}")
            return False, gost_port, None, None, None, str(e)
    
    if not gost_created:
        return False, gost_port, None, None, None, f'Failed to create Gost on port {gost_port}'
    
    return True, gost_port, actual_proxy_host, actual_proxy_port, vpn_provider, None

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
                parsed_proxy = _parse_proxy_string(profile['proxy'])
                if parsed_proxy:
                    try:
                        used_ports.add(int(parsed_proxy['port']))
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
                    parsed_proxy = _parse_proxy_string(profile['proxy'])
                    if parsed_proxy:
                        existing_proxies.append(parsed_proxy)
            
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
                # 1. Nếu proxy_check = proxy thì return lại proxy - đợi gost hoạt động
                logging.info(f"[CHROME_PROXY_CHECK] Case 1: Exact match found")
                try:
                    exact_port = int(exact_match["port"])
                    _wait_and_log_gost_ready(exact_port, BASE_DIR, 1, max_wait=3)
                except (ValueError, KeyError):
                    logging.warning(f"[CHROME_PROXY_CHECK] Case 1: Could not parse port, skipping wait")
                return f'socks5://{exact_match["host"]}:{exact_match["port"]}:{exact_match["server"]}:{exact_match["proxy_port"]}'
            
            elif different_gost_port_same_server:
                # 2. Khác port gost, proxy_host và proxy_port giống nhau thì return lại proxy - đợi gost hoạt động
                logging.info(f"[CHROME_PROXY_CHECK] Case 2: Different port, same server")
                try:
                    diff_port = int(different_gost_port_same_server["port"])
                    _wait_and_log_gost_ready(diff_port, BASE_DIR, 2, max_wait=3)
                except (ValueError, KeyError):
                    logging.warning(f"[CHROME_PROXY_CHECK] Case 2: Could not parse port, skipping wait")
                return f'socks5://{different_gost_port_same_server["host"]}:{different_gost_port_same_server["port"]}:{different_gost_port_same_server["server"]}:{different_gost_port_same_server["proxy_port"]}'
            
            elif same_gost_port_different_server:
                # 3. Trùng port gost, proxy_host và proxy_port khác nhau thì tạo mới Gost
                logging.info(f"[CHROME_PROXY_CHECK] Case 3: Same port, different server")
                # Trước tiên kiểm tra Gost đang rảnh
                available_gost = _find_available_gost(profiles, check_server, vpn_provider, check_proxy_port)
                if available_gost:
                    # Sử dụng lại Gost đang rảnh
                    gost_port = available_gost['port']
                    logging.info(f"[CHROME_PROXY_CHECK] Case 3: Using available Gost port: {gost_port}")
                    
                    # Apply Gost với dữ liệu đã phân tích
                    logging.info(f"[CHROME_PROXY_CHECK] Case 3: Applying server to port {gost_port} with data: {apply_data}, provider: {vpn_provider}")
                    success, actual_proxy_host, actual_proxy_port, vpn_provider, error_msg = _apply_server_and_parse(
                        gost_port, apply_data, vpn_provider, check_server
                    )
                    if not success:
                        logging.error(f"[CHROME_PROXY_CHECK] Case 3: Failed to apply server: {error_msg}")
                        return jsonify({
                            'success': False,
                            'error': f'Failed to apply server: {error_msg}'
                        }), 500
                    logging.info(f"[CHROME_PROXY_CHECK] Case 3: Successfully applied server, provider: {vpn_provider}")
                    
                    # Đợi gost hoạt động trước khi return (vì đã apply server mới)
                    _wait_and_log_gost_ready(gost_port, BASE_DIR, 3, max_wait=5)
                    return f'socks5://{client_host}:{gost_port}:{actual_proxy_host}:{actual_proxy_port}'
                
                # Nếu không có Gost rảnh, kiểm tra orphaned Gost hoặc tạo mới
                used_ports = _extract_used_ports(existing_proxies)
                
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
                
                logging.info(f"[CHROME_PROXY_CHECK] Case 3: Using new Gost port: {gost_port}")
                
                # Tạo gost mới với retry logic
                success, gost_port, actual_proxy_host, actual_proxy_port, vpn_provider, error_msg = _create_gost_with_retry(
                    gost_port, apply_data, vpn_provider, check_server, used_ports, BASE_DIR, 3
                )
                if not success:
                    return jsonify({
                        'success': False,
                        'error': error_msg
                    }), 500
                
                # Đợi gost hoạt động trước khi return
                _wait_and_log_gost_ready(gost_port, BASE_DIR, 3, max_wait=8)
                return f'socks5://{client_host}:{gost_port}:{actual_proxy_host}:{actual_proxy_port}'
            
            else:
                # 4. Port gost, proxy_host và proxy_port khác nhau, tạo mới Gost
                logging.info(f"[CHROME_PROXY_CHECK] Case 4: Different port and server")
                # Trước tiên kiểm tra Gost đang rảnh
                available_gost = _find_available_gost(profiles, check_server, vpn_provider, check_proxy_port)
                if available_gost:
                    # Sử dụng lại Gost đang rảnh
                    gost_port = available_gost['port']
                    logging.info(f"[CHROME_PROXY_CHECK] Case 4: Using available Gost port: {gost_port}")
                    
                    # Kiểm tra xem có phải cùng server không
                    if available_gost.get('same_server'):
                        # Cùng server, tái sử dụng trực tiếp - đợi gost hoạt động
                        logging.info(f"[CHROME_PROXY_CHECK] Reusing Gost {gost_port} with same server {check_server}")
                        _wait_and_log_gost_ready(gost_port, BASE_DIR, 4, max_wait=3)
                        return f'socks5://{client_host}:{gost_port}:{check_server}:{check_proxy_port}'
                    
                    # Khác server, apply Gost với dữ liệu đã phân tích
                    logging.info(f"[CHROME_PROXY_CHECK] Case 4: Applying server to port {gost_port} with data: {apply_data}, provider: {vpn_provider}")
                    success, actual_proxy_host, actual_proxy_port, vpn_provider, error_msg = _apply_server_and_parse(
                        gost_port, apply_data, vpn_provider, check_server
                    )
                    if not success:
                        logging.error(f"[CHROME_PROXY_CHECK] Case 4: Failed to apply server: {error_msg}")
                        return jsonify({
                            'success': False,
                            'error': f'Failed to apply server: {error_msg}'
                        }), 500
                    logging.info(f"[CHROME_PROXY_CHECK] Case 4: Successfully applied server, provider: {vpn_provider}")
                    
                    # Đợi gost hoạt động trước khi return (vì đã apply server mới)
                    _wait_and_log_gost_ready(gost_port, BASE_DIR, 4, max_wait=5)
                    return f'socks5://{client_host}:{gost_port}:{actual_proxy_host}:{actual_proxy_port}'
                
                # Nếu không có Gost rảnh, kiểm tra Gost đang chạy hoặc tạo mới
                used_ports = _extract_used_ports(existing_proxies)
                
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
                
                logging.info(f"[CHROME_PROXY_CHECK] Case 4: Using new Gost port: {gost_port}")
                
                # Tạo gost mới với retry logic
                success, gost_port, actual_proxy_host, actual_proxy_port, vpn_provider, error_msg = _create_gost_with_retry(
                    gost_port, apply_data, vpn_provider, check_server, used_ports, BASE_DIR, 4
                )
                if not success:
                    return jsonify({
                        'success': False,
                        'error': error_msg
                    }), 500
                
                # Đợi gost hoạt động trước khi return
                _wait_and_log_gost_ready(gost_port, BASE_DIR, 4, max_wait=8)
                return f'socks5://{client_host}:{gost_port}:{actual_proxy_host}:{actual_proxy_port}'
            
        except Exception as e:
            logging.error(f"[CHROME_PROXY_CHECK] Error: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
