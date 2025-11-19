#!/usr/bin/env python3
"""
Script test tốc độ và ping giữa ProtonVPN HTTPS proxy trực tiếp và Gost SOCKS5 qua ProtonVPN
"""

import time
import requests
import socket
import statistics
import sys
import os
import json
import subprocess
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import ProtonVPN service để lấy credentials
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from protonvpn_service import Instance as ProtonVpnServiceInstance
except ImportError:
    ProtonVpnServiceInstance = None
    print("⚠️  Warning: Cannot import ProtonVPN service")

# Test URLs
TEST_URLS = {
    'small': 'https://api.ipify.org',  # ~20 bytes
    'medium': 'https://speed.cloudflare.com/__down?bytes=1048576',  # 1MB
    'large': 'https://speed.cloudflare.com/__down?bytes=10485760',  # 10MB
}

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

def test_ping_https(proxy_url, test_url, num_tests=10):
    """Test ping/latency qua HTTPS proxy sử dụng curl (parallelized)"""
    latencies = []
    success_count = 0
    
    print(f"  📍 Testing ping ({num_tests} requests, parallelized)...")
    
    def single_test(i):
        try:
            start_time = time.time()
            result = subprocess.run(
                ['curl', '-s', '--proxy', proxy_url, '--max-time', '15', test_url],
                capture_output=True,
                text=True,
                timeout=20
            )
            end_time = time.time()
            
            if result.returncode == 0:
                latency = (end_time - start_time) * 1000  # Convert to ms
                return {'success': True, 'latency': latency}
            else:
                return {'success': False, 'error': f'curl returned {result.returncode}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # Parallelize tests với max 5 concurrent requests để tránh overload
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(single_test, i) for i in range(num_tests)]
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            if result['success']:
                latencies.append(result['latency'])
                success_count += 1
            else:
                print(f"    ⚠️  Request {i+1} failed: {result.get('error', 'Unknown error')}")
    
    if latencies:
        avg_latency = statistics.mean(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        median_latency = statistics.median(latencies)
        
        return {
            'success': True,
            'avg': avg_latency,
            'min': min_latency,
            'max': max_latency,
            'median': median_latency,
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
    """Test ping/latency qua SOCKS5 proxy (parallelized)"""
    proxies = {
        'http': f'socks5h://{proxy_host}:{proxy_port}',
        'https': f'socks5h://{proxy_host}:{proxy_port}'
    }
    
    latencies = []
    success_count = 0
    
    print(f"  📍 Testing ping ({num_tests} requests, parallelized)...")
    
    def single_test(i):
        try:
            start_time = time.time()
            response = requests.get(test_url, proxies=proxies, timeout=15)
            end_time = time.time()
            
            if response.status_code == 200:
                latency = (end_time - start_time) * 1000  # Convert to ms
                return {'success': True, 'latency': latency}
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # Parallelize tests với max 5 concurrent requests để tránh overload
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(single_test, i) for i in range(num_tests)]
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            if result['success']:
                latencies.append(result['latency'])
                success_count += 1
            else:
                print(f"    ⚠️  Request {i+1} failed: {result.get('error', 'Unknown error')}")
    
    if latencies:
        avg_latency = statistics.mean(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)
        median_latency = statistics.median(latencies)
        
        return {
            'success': True,
            'avg': avg_latency,
            'min': min_latency,
            'max': max_latency,
            'median': median_latency,
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

def test_download_speed_https(proxy_url, test_url, duration=10):
    """Test download speed qua HTTPS proxy sử dụng curl"""
    print(f"  ⬇️  Testing download speed ({duration}s)...")
    
    try:
        start_time = time.time()
        end_time = start_time + duration
        
        # Sử dụng curl với output vào /dev/null và đo thời gian
        # Lưu output vào temp file để đo bytes
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Chạy curl với timeout
            process = subprocess.Popen(
                ['curl', '-s', '--proxy', proxy_url, '--max-time', str(duration + 5), '--output', tmp_path, test_url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Đợi đến khi hết thời gian hoặc process kết thúc
            while time.time() < end_time:
                if process.poll() is not None:
                    break
                time.sleep(0.1)
            
            # Nếu vẫn còn thời gian, kill process
            if process.poll() is None:
                process.kill()
            
            process.wait()
            
            elapsed_time = time.time() - start_time
            
            # Đọc file để lấy bytes
            if os.path.exists(tmp_path):
                total_bytes = os.path.getsize(tmp_path)
                os.unlink(tmp_path)
            else:
                total_bytes = 0
            
            if elapsed_time > 0 and total_bytes > 0:
                speed_mbps = (total_bytes * 8) / (elapsed_time * 1024 * 1024)  # Mbps
                speed_mb_s = total_bytes / (elapsed_time * 1024 * 1024)  # MB/s
                
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
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise e
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_download_speed_socks5(proxy_host, proxy_port, test_url, duration=10):
    """Test download speed qua SOCKS5 proxy"""
    proxies = {
        'http': f'socks5h://{proxy_host}:{proxy_port}',
        'https': f'socks5h://{proxy_host}:{proxy_port}'
    }
    
    print(f"  ⬇️  Testing download speed ({duration}s)...")
    
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
            speed_mbps = (total_bytes * 8) / (elapsed_time * 1024 * 1024)  # Mbps
            speed_mb_s = total_bytes / (elapsed_time * 1024 * 1024)  # MB/s
            
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

def test_connection_https(proxy_url):
    """Test kết nối cơ bản qua HTTPS proxy sử dụng curl"""
    print(f"  🔌 Testing connection...")
    
    try:
        # Sử dụng curl để test HTTPS proxy (requests không hỗ trợ tốt TLS in TLS)
        start_time = time.time()
        result = subprocess.run(
            ['curl', '-s', '--proxy', proxy_url, '--max-time', '15', 'https://api.ipify.org'],
            capture_output=True,
            text=True,
            timeout=20
        )
        end_time = time.time()
        
        if result.returncode == 0 and result.stdout.strip():
            return {
                'success': True,
                'ip': result.stdout.strip(),
                'latency': (end_time - start_time) * 1000
            }
        else:
            return {'success': False, 'error': f'curl failed: {result.stderr[:100]}'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_connection_socks5(proxy_host, proxy_port):
    """Test kết nối cơ bản qua SOCKS5 proxy"""
    print(f"  🔌 Testing connection...")
    
    try:
        # Test socket connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((proxy_host, proxy_port))
        sock.close()
        
        if result != 0:
            return {'success': False, 'error': 'Port not accessible'}
        
        # Test proxy with HTTP request
        proxies = {
            'http': f'socks5h://{proxy_host}:{proxy_port}',
            'https': f'socks5h://{proxy_host}:{proxy_port}'
        }
        
        start_time = time.time()
        response = requests.get('https://api.ipify.org', proxies=proxies, timeout=15)
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

def run_test_suite_protonvpn(proxy_url, server_name):
    """Chạy bộ test đầy đủ cho ProtonVPN HTTPS proxy trực tiếp"""
    print(f"\n{'='*60}")
    print(f"🧪 Testing ProtonVPN HTTPS (Direct)")
    print(f"   Server: {server_name}")
    print(f"   Proxy: {proxy_url.split('@')[1] if '@' in proxy_url else proxy_url}")
    print(f"{'='*60}")
    
    results = {
        'name': 'ProtonVPN HTTPS',
        'server': server_name,
        'connection': None,
        'ping': None,
        'download_small': None,
        'download_large': None
    }
    
    # Test connection
    results['connection'] = test_connection_https(proxy_url)
    if not results['connection']['success']:
        print(f"  ❌ Connection failed: {results['connection'].get('error', 'Unknown error')}")
        return results
    
    print(f"  ✅ Connected! IP: {results['connection']['ip']}, Latency: {results['connection']['latency']:.2f}ms")
    
    # Test ping
    results['ping'] = test_ping_https(proxy_url, TEST_URLS['small'], num_tests=10)
    if results['ping']['success']:
        print(f"  ✅ Ping Results:")
        print(f"     Average: {results['ping']['avg']:.2f}ms")
        print(f"     Min: {results['ping']['min']:.2f}ms")
        print(f"     Max: {results['ping']['max']:.2f}ms")
        print(f"     Median: {results['ping']['median']:.2f}ms")
        print(f"     Success Rate: {results['ping']['success_rate']:.1f}%")
    else:
        print(f"  ❌ Ping test failed")
    
    # Test download speed - small
    print(f"\n  📦 Small file test (1MB)...")
    results['download_small'] = test_download_speed_https(proxy_url, TEST_URLS['medium'], duration=10)
    if results['download_small']['success']:
        print(f"     Speed: {results['download_small']['speed_mbps']:.2f} Mbps ({results['download_small']['speed_mb_s']:.2f} MB/s)")
        print(f"     Downloaded: {results['download_small']['bytes'] / 1024 / 1024:.2f} MB in {results['download_small']['time']:.2f}s")
    else:
        print(f"     ❌ Failed: {results['download_small'].get('error', 'Unknown error')}")
    
    # Test download speed - large
    print(f"\n  📦 Large file test (10MB)...")
    results['download_large'] = test_download_speed_https(proxy_url, TEST_URLS['large'], duration=15)
    if results['download_large']['success']:
        print(f"     Speed: {results['download_large']['speed_mbps']:.2f} Mbps ({results['download_large']['speed_mb_s']:.2f} MB/s)")
        print(f"     Downloaded: {results['download_large']['bytes'] / 1024 / 1024:.2f} MB in {results['download_large']['time']:.2f}s")
    else:
        print(f"     ❌ Failed: {results['download_large'].get('error', 'Unknown error')}")
    
    return results

def run_test_suite_gost(proxy_host, proxy_port, server_name):
    """Chạy bộ test đầy đủ cho Gost SOCKS5 qua ProtonVPN"""
    print(f"\n{'='*60}")
    print(f"🧪 Testing Gost SOCKS5 (via ProtonVPN)")
    print(f"   Server: {server_name}")
    print(f"   Proxy: socks5h://{proxy_host}:{proxy_port}")
    print(f"{'='*60}")
    
    results = {
        'name': 'Gost SOCKS5',
        'server': server_name,
        'host': proxy_host,
        'port': proxy_port,
        'connection': None,
        'ping': None,
        'download_small': None,
        'download_large': None
    }
    
    # Test connection
    results['connection'] = test_connection_socks5(proxy_host, proxy_port)
    if not results['connection']['success']:
        print(f"  ❌ Connection failed: {results['connection'].get('error', 'Unknown error')}")
        return results
    
    print(f"  ✅ Connected! IP: {results['connection']['ip']}, Latency: {results['connection']['latency']:.2f}ms")
    
    # Test ping
    results['ping'] = test_ping_socks5(proxy_host, proxy_port, TEST_URLS['small'], num_tests=10)
    if results['ping']['success']:
        print(f"  ✅ Ping Results:")
        print(f"     Average: {results['ping']['avg']:.2f}ms")
        print(f"     Min: {results['ping']['min']:.2f}ms")
        print(f"     Max: {results['ping']['max']:.2f}ms")
        print(f"     Median: {results['ping']['median']:.2f}ms")
        print(f"     Success Rate: {results['ping']['success_rate']:.1f}%")
    else:
        print(f"  ❌ Ping test failed")
    
    # Test download speed - small
    print(f"\n  📦 Small file test (1MB)...")
    results['download_small'] = test_download_speed_socks5(proxy_host, proxy_port, TEST_URLS['medium'], duration=10)
    if results['download_small']['success']:
        print(f"     Speed: {results['download_small']['speed_mbps']:.2f} Mbps ({results['download_small']['speed_mb_s']:.2f} MB/s)")
        print(f"     Downloaded: {results['download_small']['bytes'] / 1024 / 1024:.2f} MB in {results['download_small']['time']:.2f}s")
    else:
        print(f"     ❌ Failed: {results['download_small'].get('error', 'Unknown error')}")
    
    # Test download speed - large
    print(f"\n  📦 Large file test (10MB)...")
    results['download_large'] = test_download_speed_socks5(proxy_host, proxy_port, TEST_URLS['large'], duration=15)
    if results['download_large']['success']:
        print(f"     Speed: {results['download_large']['speed_mbps']:.2f} Mbps ({results['download_large']['speed_mb_s']:.2f} MB/s)")
        print(f"     Downloaded: {results['download_large']['bytes'] / 1024 / 1024:.2f} MB in {results['download_large']['time']:.2f}s")
    else:
        print(f"     ❌ Failed: {results['download_large'].get('error', 'Unknown error')}")
    
    return results

def print_comparison(protonvpn_results, gost_results):
    """In so sánh kết quả"""
    print(f"\n{'='*60}")
    print(f"📊 COMPARISON RESULTS")
    print(f"{'='*60}")
    
    # Connection comparison
    print(f"\n🔌 Connection:")
    if protonvpn_results['connection']['success'] and gost_results['connection']['success']:
        protonvpn_latency = protonvpn_results['connection']['latency']
        gost_latency = gost_results['connection']['latency']
        diff = gost_latency - protonvpn_latency
        diff_pct = (diff / protonvpn_latency) * 100 if protonvpn_latency > 0 else 0
        
        print(f"   ProtonVPN HTTPS:  {protonvpn_latency:.2f}ms")
        print(f"   Gost SOCKS5:      {gost_latency:.2f}ms ({diff:+.2f}ms, {diff_pct:+.1f}%)")
        
        if diff > 0:
            print(f"   ⚠️  Gost slower by {diff:.2f}ms")
        else:
            print(f"   ✅ Gost faster by {abs(diff):.2f}ms")
    
    # Ping comparison
    if protonvpn_results['ping'] and protonvpn_results['ping']['success'] and gost_results['ping'] and gost_results['ping']['success']:
        print(f"\n📍 Ping (Average):")
        protonvpn_avg = protonvpn_results['ping']['avg']
        gost_avg = gost_results['ping']['avg']
        diff = gost_avg - protonvpn_avg
        diff_pct = (diff / protonvpn_avg) * 100 if protonvpn_avg > 0 else 0
        
        print(f"   ProtonVPN HTTPS:  {protonvpn_avg:.2f}ms")
        print(f"   Gost SOCKS5:      {gost_avg:.2f}ms ({diff:+.2f}ms, {diff_pct:+.1f}%)")
        
        print(f"\n📍 Ping (Median):")
        protonvpn_median = protonvpn_results['ping']['median']
        gost_median = gost_results['ping']['median']
        diff_median = gost_median - protonvpn_median
        
        print(f"   ProtonVPN HTTPS:  {protonvpn_median:.2f}ms")
        print(f"   Gost SOCKS5:      {gost_median:.2f}ms ({diff_median:+.2f}ms)")
    
    # Download speed comparison
    if protonvpn_results['download_large'] and protonvpn_results['download_large']['success'] and \
       gost_results['download_large'] and gost_results['download_large']['success']:
        print(f"\n⬇️  Download Speed (Large file):")
        protonvpn_speed = protonvpn_results['download_large']['speed_mbps']
        gost_speed = gost_results['download_large']['speed_mbps']
        diff = gost_speed - protonvpn_speed
        diff_pct = (diff / protonvpn_speed) * 100 if protonvpn_speed > 0 else 0
        
        print(f"   ProtonVPN HTTPS:  {protonvpn_speed:.2f} Mbps")
        print(f"   Gost SOCKS5:      {gost_speed:.2f} Mbps ({diff:+.2f} Mbps, {diff_pct:+.1f}%)")
        
        if diff < 0:
            print(f"   ⚠️  Gost slower by {abs(diff):.2f} Mbps ({abs(diff_pct):.1f}%)")
        else:
            print(f"   ✅ Gost faster by {diff:.2f} Mbps ({diff_pct:.1f}%)")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    
    if protonvpn_results['ping'] and protonvpn_results['ping']['success'] and gost_results['ping'] and gost_results['ping']['success']:
        latency_overhead = gost_results['ping']['avg'] - protonvpn_results['ping']['avg']
        if latency_overhead > 50:
            print(f"   ⚠️  High latency overhead ({latency_overhead:.2f}ms). Consider optimizing Gost timeout settings.")
        elif latency_overhead > 20:
            print(f"   ⚠️  Moderate latency overhead ({latency_overhead:.2f}ms). May benefit from optimization.")
        else:
            print(f"   ✅ Low latency overhead ({latency_overhead:.2f}ms). Performance is good.")
    
    if protonvpn_results['download_large'] and protonvpn_results['download_large']['success'] and \
       gost_results['download_large'] and gost_results['download_large']['success']:
        speed_loss = ((protonvpn_results['download_large']['speed_mbps'] - gost_results['download_large']['speed_mbps']) / protonvpn_results['download_large']['speed_mbps']) * 100 if protonvpn_results['download_large']['speed_mbps'] > 0 else 0
        if speed_loss > 20:
            print(f"   ⚠️  Significant speed loss ({speed_loss:.1f}%). Consider optimizing buffer sizes.")
        elif speed_loss > 10:
            print(f"   ⚠️  Moderate speed loss ({speed_loss:.1f}%). May benefit from optimization.")
        else:
            print(f"   ✅ Minimal speed loss ({speed_loss:.1f}%). Performance is good.")

def main():
    import sys
    
    # Disable SSL warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    if len(sys.argv) < 4:
        print("Usage: python3 test_protonvpn_gost_speed.py <server_host> <server_port> <gost_port>")
        print("Example: python3 test_protonvpn_gost_speed.py node-jp-10.protonvpn.net 4453 7891")
        sys.exit(1)
    
    server_host = sys.argv[1]
    server_port = int(sys.argv[2])
    gost_port = int(sys.argv[3])
    
    print("🚀 ProtonVPN vs Gost Speed Test")
    print("=" * 60)
    
    # Get ProtonVPN proxy URL
    protonvpn_proxy_url = get_protonvpn_proxy_url(server_host, server_port)
    if not protonvpn_proxy_url:
        print("❌ Cannot get ProtonVPN credentials")
        sys.exit(1)
    
    # Test ProtonVPN HTTPS directly
    protonvpn_results = run_test_suite_protonvpn(protonvpn_proxy_url, server_host)
    
    # Test Gost SOCKS5
    gost_results = run_test_suite_gost("127.0.0.1", gost_port, server_host)
    
    # Print comparison
    if protonvpn_results['connection']['success'] and gost_results['connection']['success']:
        print_comparison(protonvpn_results, gost_results)
    else:
        print("\n❌ Cannot compare - one or both proxies failed connection test")
        if not protonvpn_results['connection']['success']:
            print(f"   ProtonVPN failed: {protonvpn_results['connection'].get('error', 'Unknown')}")
        if not gost_results['connection']['success']:
            print(f"   Gost failed: {gost_results['connection'].get('error', 'Unknown')}")
    
    print(f"\n{'='*60}")
    print("✅ Test completed!")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()

