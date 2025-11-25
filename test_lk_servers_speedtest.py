#!/usr/bin/env python3
"""
Script test tốc độ và độ ổn định cho 52 server LK của ProtonVPN
Test cả HTTPS và SOCKS5 proxy của gost
"""

import time
import requests
import socket
import statistics
import sys
import os
import json
import subprocess
import tempfile
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

# Import ProtonVPN service để lấy credentials
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from protonvpn_service import Instance as ProtonVpnServiceInstance
    from protonvpn_api import ProtonVPNAPI
except ImportError:
    ProtonVpnServiceInstance = None
    ProtonVPNAPI = None
    print("⚠️  Warning: Cannot import ProtonVPN modules")

# Test URLs
TEST_URLS = {
    'small': 'https://ipinfo.io/ip',  # ~20 bytes
    'medium': 'https://speed.cloudflare.com/__down?bytes=1048576',  # 1MB
    'large': 'https://speed.cloudflare.com/__down?bytes=10485760',  # 10MB
}

# Gost binary path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GOST_BIN = os.path.join(SCRIPT_DIR, "bin", "gost")
if not os.path.exists(GOST_BIN):
    GOST_BIN = "gost"  # Fallback to system gost

LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Port ranges for testing
HTTP_PORT_START = 8000
SOCKS5_PORT_START = 8100

def get_protonvpn_proxy_url(server_host, server_port):
    """Lấy ProtonVPN proxy URL từ credentials"""
    if not ProtonVpnServiceInstance:
        return None
    
    try:
        username = ProtonVpnServiceInstance.user_name
        password = ProtonVpnServiceInstance.password
        
        if not username or not password:
            print("⚠️  ProtonVPN credentials not available")
            return None
        
        # Format: https://username:password@host:port
        proxy_url = f"https://{username}:{password}@{server_host}:{server_port}"
        return proxy_url
    except Exception as e:
        print(f"⚠️  Error getting ProtonVPN credentials: {e}")
        return None

def get_lk_servers(limit=52):
    """Lấy danh sách server LK từ ProtonVPN API"""
    try:
        # Try API first
        try:
            response = requests.get("http://localhost:5000/api/protonvpn/servers/LK", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    servers = data.get('servers', [])
                    print(f"✅ Got {len(servers)} LK servers from API")
                    return servers[:limit]
        except Exception as e:
            print(f"⚠️  API request failed: {e}, trying direct API...")
        
        # Fallback: use ProtonVPN API directly
        if ProtonVPNAPI:
            api = ProtonVPNAPI()
            servers = api.get_servers_by_country("LK")
            print(f"✅ Got {len(servers)} LK servers from direct API")
            return servers[:limit]
        
        print("❌ Cannot get LK servers")
        return []
    except Exception as e:
        print(f"❌ Error getting LK servers: {e}")
        return []

def start_gost_proxy(proxy_type, port, proxy_url):
    """Khởi động gost proxy (HTTP hoặc SOCKS5)"""
    try:
        if proxy_type == "http":
            listener = f"http://:{port}"
        elif proxy_type == "socks5":
            listener = f"socks5://:{port}"
        else:
            return False
        
        # Check if port is already in use
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result == 0:
            # Port in use, try to kill existing process
            try:
                subprocess.run(['pkill', '-f', f'gost.*{proxy_type}.*:{port}'], 
                             capture_output=True, timeout=5)
                time.sleep(1)
            except:
                pass
        
        # Start gost
        log_file = os.path.join(LOG_DIR, f"gost_{proxy_type}_{port}.log")
        cmd = [GOST_BIN, '-D', '-L', listener, '-F', proxy_url]
        
        with open(log_file, 'w') as f:
            process = subprocess.Popen(cmd, stdout=f, stderr=f)
        
        # Wait a bit for gost to start
        time.sleep(2)
        
        # Check if process is still running
        if process.poll() is None:
            return True
        else:
            return False
    except Exception as e:
        print(f"⚠️  Error starting gost {proxy_type} on port {port}: {e}")
        return False

def stop_gost_proxy(proxy_type, port):
    """Dừng gost proxy"""
    try:
        subprocess.run(['pkill', '-f', f'gost.*{proxy_type}.*:{port}'], 
                      capture_output=True, timeout=5)
        time.sleep(1)
    except:
        pass

def test_connection_https(proxy_host, proxy_port):
    """Test kết nối qua HTTPS proxy"""
    try:
        proxies = {
            'http': f'http://{proxy_host}:{proxy_port}',
            'https': f'http://{proxy_host}:{proxy_port}'
        }
        
        start_time = time.time()
        response = requests.get('https://ipinfo.io/ip', proxies=proxies, timeout=15)
        end_time = time.time()
        
        if response.status_code == 200:
            return {
                'success': True,
                'ip': response.text.strip(),
                'latency': (end_time - start_time) * 1000
            }
        else:
            return {'success': False, 'error': f'HTTP {response.status_code}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_connection_socks5(proxy_host, proxy_port):
    """Test kết nối qua SOCKS5 proxy"""
    try:
        proxies = {
            'http': f'socks5h://{proxy_host}:{proxy_port}',
            'https': f'socks5h://{proxy_host}:{proxy_port}'
        }
        
        start_time = time.time()
        response = requests.get('https://ipinfo.io/ip', proxies=proxies, timeout=15)
        end_time = time.time()
        
        if response.status_code == 200:
            return {
                'success': True,
                'ip': response.text.strip(),
                'latency': (end_time - start_time) * 1000
            }
        else:
            return {'success': False, 'error': f'HTTP {response.status_code}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_ping_https(proxy_host, proxy_port, test_url, num_tests=10):
    """Test ping/latency qua HTTPS proxy"""
    proxies = {
        'http': f'http://{proxy_host}:{proxy_port}',
        'https': f'http://{proxy_host}:{proxy_port}'
    }
    
    latencies = []
    success_count = 0
    
    def single_test(i):
        try:
            start_time = time.time()
            response = requests.get(test_url, proxies=proxies, timeout=15)
            end_time = time.time()
            
            if response.status_code == 200:
                latency = (end_time - start_time) * 1000
                return {'success': True, 'latency': latency}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(single_test, i) for i in range(num_tests)]
        for future in as_completed(futures):
            result = future.result()
            if result['success']:
                latencies.append(result['latency'])
                success_count += 1
    
    if latencies:
        return {
            'success': True,
            'avg': statistics.mean(latencies),
            'min': min(latencies),
            'max': max(latencies),
            'median': statistics.median(latencies),
            'success_rate': success_count / num_tests * 100,
            'total_tests': num_tests,
            'success_tests': success_count
        }
    else:
        return {
            'success': False,
            'success_rate': 0,
            'total_tests': num_tests,
            'success_tests': 0
        }

def test_ping_socks5(proxy_host, proxy_port, test_url, num_tests=10):
    """Test ping/latency qua SOCKS5 proxy"""
    proxies = {
        'http': f'socks5h://{proxy_host}:{proxy_port}',
        'https': f'socks5h://{proxy_host}:{proxy_port}'
    }
    
    latencies = []
    success_count = 0
    
    def single_test(i):
        try:
            start_time = time.time()
            response = requests.get(test_url, proxies=proxies, timeout=15)
            end_time = time.time()
            
            if response.status_code == 200:
                latency = (end_time - start_time) * 1000
                return {'success': True, 'latency': latency}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(single_test, i) for i in range(num_tests)]
        for future in as_completed(futures):
            result = future.result()
            if result['success']:
                latencies.append(result['latency'])
                success_count += 1
    
    if latencies:
        return {
            'success': True,
            'avg': statistics.mean(latencies),
            'min': min(latencies),
            'max': max(latencies),
            'median': statistics.median(latencies),
            'success_rate': success_count / num_tests * 100,
            'total_tests': num_tests,
            'success_tests': success_count
        }
    else:
        return {
            'success': False,
            'success_rate': 0,
            'total_tests': num_tests,
            'success_tests': 0
        }

def test_download_speed_https(proxy_host, proxy_port, test_url, duration=10):
    """Test download speed qua HTTPS proxy"""
    proxies = {
        'http': f'http://{proxy_host}:{proxy_port}',
        'https': f'http://{proxy_host}:{proxy_port}'
    }
    
    try:
        start_time = time.time()
        end_time = start_time + duration
        
        total_bytes = 0
        chunk_size = 8192
        
        response = requests.get(test_url, proxies=proxies, stream=True, timeout=30)
        
        if response.status_code != 200:
            return {'success': False, 'error': f'HTTP {response.status_code}'}
        
        for chunk in response.iter_content(chunk_size=chunk_size):
            if time.time() >= end_time:
                break
            if chunk:
                total_bytes += len(chunk)
        
        elapsed_time = time.time() - start_time
        
        if elapsed_time > 0:
            speed_mbps = (total_bytes * 8) / (elapsed_time * 1024 * 1024)
            speed_mb_s = total_bytes / (elapsed_time * 1024 * 1024)
            
            return {
                'success': True,
                'bytes': total_bytes,
                'time': elapsed_time,
                'speed_mbps': speed_mbps,
                'speed_mb_s': speed_mb_s
            }
        else:
            return {'success': False, 'error': 'No data received'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_download_speed_socks5(proxy_host, proxy_port, test_url, duration=10):
    """Test download speed qua SOCKS5 proxy"""
    proxies = {
        'http': f'socks5h://{proxy_host}:{proxy_port}',
        'https': f'socks5h://{proxy_host}:{proxy_port}'
    }
    
    try:
        start_time = time.time()
        end_time = start_time + duration
        
        total_bytes = 0
        chunk_size = 8192
        
        response = requests.get(test_url, proxies=proxies, stream=True, timeout=30)
        
        if response.status_code != 200:
            return {'success': False, 'error': f'HTTP {response.status_code}'}
        
        for chunk in response.iter_content(chunk_size=chunk_size):
            if time.time() >= end_time:
                break
            if chunk:
                total_bytes += len(chunk)
        
        elapsed_time = time.time() - start_time
        
        if elapsed_time > 0:
            speed_mbps = (total_bytes * 8) / (elapsed_time * 1024 * 1024)
            speed_mb_s = total_bytes / (elapsed_time * 1024 * 1024)
            
            return {
                'success': True,
                'bytes': total_bytes,
                'time': elapsed_time,
                'speed_mbps': speed_mbps,
                'speed_mb_s': speed_mb_s
            }
        else:
            return {'success': False, 'error': 'No data received'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_server(server, index, http_port, socks5_port):
    """Test một server với cả HTTP và SOCKS5"""
    server_name = server.get('domain', server.get('name', f'Server-{index}'))
    server_host = server.get('domain', '')
    
    # Calculate port from server label (port = label + 4443)
    server_port = 4443  # Default
    if server.get('servers') and len(server['servers']) > 0:
        try:
            label = int(server['servers'][0].get('label', '0'))
            server_port = 4443 + label
        except (ValueError, TypeError):
            pass
    
    if not server_host:
        return None
    
    print(f"\n{'='*70}")
    print(f"🧪 Testing Server {index + 1}: {server_name}")
    print(f"   Host: {server_host}:{server_port}")
    print(f"{'='*70}")
    
    # Get proxy URL
    proxy_url = get_protonvpn_proxy_url(server_host, server_port)
    if not proxy_url:
        print(f"  ❌ Cannot get proxy URL")
        return None
    
    results = {
        'server': server_name,
        'host': server_host,
        'port': server_port,
        'http': {},
        'socks5': {}
    }
    
    # Test HTTP proxy
    print(f"\n📡 Testing HTTP Proxy (port {http_port})...")
    if start_gost_proxy("http", http_port, proxy_url):
        print(f"  ✅ Gost HTTP started")
        
        # Test connection
        conn_result = test_connection_https("127.0.0.1", http_port)
        if conn_result['success']:
            print(f"  ✅ Connected! IP: {conn_result['ip']}, Latency: {conn_result['latency']:.2f}ms")
            results['http']['connection'] = conn_result
            
            # Test ping
            print(f"  📍 Testing ping...")
            ping_result = test_ping_https("127.0.0.1", http_port, TEST_URLS['small'], num_tests=10)
            if ping_result['success']:
                print(f"     Avg: {ping_result['avg']:.2f}ms, Min: {ping_result['min']:.2f}ms, Max: {ping_result['max']:.2f}ms")
                print(f"     Success Rate: {ping_result['success_rate']:.1f}%")
                results['http']['ping'] = ping_result
            else:
                print(f"     ❌ Ping test failed")
                results['http']['ping'] = ping_result
            
            # Test download speed
            print(f"  ⬇️  Testing download speed...")
            speed_result = test_download_speed_https("127.0.0.1", http_port, TEST_URLS['large'], duration=10)
            if speed_result['success']:
                print(f"     Speed: {speed_result['speed_mbps']:.2f} Mbps ({speed_result['speed_mb_s']:.2f} MB/s)")
                results['http']['speed'] = speed_result
            else:
                print(f"     ❌ Speed test failed: {speed_result.get('error', 'Unknown')}")
                results['http']['speed'] = speed_result
        else:
            print(f"  ❌ Connection failed: {conn_result.get('error', 'Unknown')}")
            results['http']['connection'] = conn_result
        
        stop_gost_proxy("http", http_port)
    else:
        print(f"  ❌ Failed to start Gost HTTP")
        results['http'] = {'error': 'Failed to start'}
    
    time.sleep(2)
    
    # Test SOCKS5 proxy
    print(f"\n📡 Testing SOCKS5 Proxy (port {socks5_port})...")
    if start_gost_proxy("socks5", socks5_port, proxy_url):
        print(f"  ✅ Gost SOCKS5 started")
        
        # Test connection
        conn_result = test_connection_socks5("127.0.0.1", socks5_port)
        if conn_result['success']:
            print(f"  ✅ Connected! IP: {conn_result['ip']}, Latency: {conn_result['latency']:.2f}ms")
            results['socks5']['connection'] = conn_result
            
            # Test ping
            print(f"  📍 Testing ping...")
            ping_result = test_ping_socks5("127.0.0.1", socks5_port, TEST_URLS['small'], num_tests=10)
            if ping_result['success']:
                print(f"     Avg: {ping_result['avg']:.2f}ms, Min: {ping_result['min']:.2f}ms, Max: {ping_result['max']:.2f}ms")
                print(f"     Success Rate: {ping_result['success_rate']:.1f}%")
                results['socks5']['ping'] = ping_result
            else:
                print(f"     ❌ Ping test failed")
                results['socks5']['ping'] = ping_result
            
            # Test download speed
            print(f"  ⬇️  Testing download speed...")
            speed_result = test_download_speed_socks5("127.0.0.1", socks5_port, TEST_URLS['large'], duration=10)
            if speed_result['success']:
                print(f"     Speed: {speed_result['speed_mbps']:.2f} Mbps ({speed_result['speed_mb_s']:.2f} MB/s)")
                results['socks5']['speed'] = speed_result
            else:
                print(f"     ❌ Speed test failed: {speed_result.get('error', 'Unknown')}")
                results['socks5']['speed'] = speed_result
        else:
            print(f"  ❌ Connection failed: {conn_result.get('error', 'Unknown')}")
            results['socks5']['connection'] = conn_result
        
        stop_gost_proxy("socks5", socks5_port)
    else:
        print(f"  ❌ Failed to start Gost SOCKS5")
        results['socks5'] = {'error': 'Failed to start'}
    
    return results

def print_summary(all_results):
    """In tóm tắt kết quả"""
    print(f"\n{'='*70}")
    print(f"📊 SUMMARY - Tổng hợp kết quả test")
    print(f"{'='*70}")
    
    successful_servers = [r for r in all_results if r and (r.get('http', {}).get('connection', {}).get('success') or 
                                                           r.get('socks5', {}).get('connection', {}).get('success'))]
    
    print(f"\n✅ Servers tested successfully: {len(successful_servers)}/{len(all_results)}")
    
    # HTTP stats
    http_working = [r for r in successful_servers if r.get('http', {}).get('connection', {}).get('success')]
    if http_working:
        http_pings = [r['http']['ping']['avg'] for r in http_working 
                      if r.get('http', {}).get('ping', {}).get('success')]
        http_speeds = [r['http']['speed']['speed_mbps'] for r in http_working 
                       if r.get('http', {}).get('speed', {}).get('success')]
        
        print(f"\n📡 HTTP Proxy:")
        print(f"   Working: {len(http_working)}/{len(all_results)}")
        if http_pings:
            print(f"   Ping - Avg: {statistics.mean(http_pings):.2f}ms, Min: {min(http_pings):.2f}ms, Max: {max(http_pings):.2f}ms")
        if http_speeds:
            print(f"   Speed - Avg: {statistics.mean(http_speeds):.2f} Mbps, Min: {min(http_speeds):.2f} Mbps, Max: {max(http_speeds):.2f} Mbps")
    
    # SOCKS5 stats
    socks5_working = [r for r in successful_servers if r.get('socks5', {}).get('connection', {}).get('success')]
    if socks5_working:
        socks5_pings = [r['socks5']['ping']['avg'] for r in socks5_working 
                       if r.get('socks5', {}).get('ping', {}).get('success')]
        socks5_speeds = [r['socks5']['speed']['speed_mbps'] for r in socks5_working 
                        if r.get('socks5', {}).get('speed', {}).get('success')]
        
        print(f"\n📡 SOCKS5 Proxy:")
        print(f"   Working: {len(socks5_working)}/{len(all_results)}")
        if socks5_pings:
            print(f"   Ping - Avg: {statistics.mean(socks5_pings):.2f}ms, Min: {min(socks5_pings):.2f}ms, Max: {max(socks5_pings):.2f}ms")
        if socks5_speeds:
            print(f"   Speed - Avg: {statistics.mean(socks5_speeds):.2f} Mbps, Min: {min(socks5_speeds):.2f} Mbps, Max: {max(socks5_speeds):.2f} Mbps")
    
    # Comparison
    if http_working and socks5_working:
        common_servers = [r for r in successful_servers 
                         if r.get('http', {}).get('connection', {}).get('success') and 
                            r.get('socks5', {}).get('connection', {}).get('success')]
        
        if common_servers:
            print(f"\n📊 Comparison (servers with both working):")
            http_common_pings = [r['http']['ping']['avg'] for r in common_servers 
                                 if r.get('http', {}).get('ping', {}).get('success')]
            socks5_common_pings = [r['socks5']['ping']['avg'] for r in common_servers 
                                  if r.get('socks5', {}).get('ping', {}).get('success')]
            http_common_speeds = [r['http']['speed']['speed_mbps'] for r in common_servers 
                                  if r.get('http', {}).get('speed', {}).get('success')]
            socks5_common_speeds = [r['socks5']['speed']['speed_mbps'] for r in common_servers 
                                   if r.get('socks5', {}).get('speed', {}).get('success')]
            
            if http_common_pings and socks5_common_pings:
                avg_diff = statistics.mean(socks5_common_pings) - statistics.mean(http_common_pings)
                print(f"   Ping: HTTP {statistics.mean(http_common_pings):.2f}ms vs SOCKS5 {statistics.mean(socks5_common_pings):.2f}ms (diff: {avg_diff:+.2f}ms)")
            
            if http_common_speeds and socks5_common_speeds:
                avg_diff = statistics.mean(socks5_common_speeds) - statistics.mean(http_common_speeds)
                print(f"   Speed: HTTP {statistics.mean(http_common_speeds):.2f} Mbps vs SOCKS5 {statistics.mean(socks5_common_speeds):.2f} Mbps (diff: {avg_diff:+.2f} Mbps)")

def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    print("🚀 ProtonVPN LK Servers Speed Test")
    print("   Testing HTTP and SOCKS5 proxies of gost")
    print("=" * 70)
    
    # Get LK servers
    servers = get_lk_servers(limit=52)
    if not servers:
        print("❌ No LK servers found")
        sys.exit(1)
    
    print(f"\n📋 Found {len(servers)} LK servers to test")
    
    # Test each server
    all_results = []
    for i, server in enumerate(servers):
        http_port = HTTP_PORT_START + i
        socks5_port = SOCKS5_PORT_START + i
        
        result = test_server(server, i, http_port, socks5_port)
        if result:
            all_results.append(result)
        
        # Small delay between servers
        if i < len(servers) - 1:
            time.sleep(1)
    
    # Print summary
    print_summary(all_results)
    
    # Save results to file
    results_file = os.path.join(LOG_DIR, f"lk_servers_test_{int(time.time())}.json")
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\n💾 Results saved to: {results_file}")
    
    print(f"\n{'='*70}")
    print("✅ Test completed!")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()

