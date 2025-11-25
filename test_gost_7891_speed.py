#!/usr/bin/env python3
"""
Script test tốc độ của gost port 7891 và phân tích nguyên nhân chậm
"""

import time
import requests
import socket
import statistics
import sys
import subprocess
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Test URLs
TEST_URLS = {
    'small': 'https://ipinfo.io/ip',  # ~20 bytes
    'medium': 'https://speed.cloudflare.com/__down?bytes=1048576',  # 1MB
    'large': 'https://speed.cloudflare.com/__down?bytes=10485760',  # 10MB
}

def test_connection(proxy_host, proxy_port):
    """Test kết nối cơ bản"""
    proxies = {
        'http': f'socks5h://{proxy_host}:{proxy_port}',
        'https': f'socks5h://{proxy_host}:{proxy_port}'
    }
    
    try:
        start_time = time.time()
        response = requests.get('https://ipinfo.io/ip', proxies=proxies, timeout=15)
        end_time = time.time()
        
        if response.status_code == 200:
            latency = (end_time - start_time) * 1000
            return {
                'success': True,
                'ip': response.text.strip(),
                'latency': latency
            }
        else:
            return {'success': False, 'error': f'HTTP {response.status_code}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_ping(proxy_host, proxy_port, test_url, num_tests=10):
    """Test ping/latency qua proxy"""
    proxies = {
        'http': f'socks5h://{proxy_host}:{proxy_port}',
        'https': f'socks5h://{proxy_host}:{proxy_port}'
    }
    
    latencies = []
    success_count = 0
    errors = []
    
    print(f"  📍 Testing ping ({num_tests} requests)...")
    
    for i in range(num_tests):
        try:
            start_time = time.time()
            response = requests.get(test_url, proxies=proxies, timeout=15)
            end_time = time.time()
            
            if response.status_code == 200:
                latency = (end_time - start_time) * 1000
                latencies.append(latency)
                success_count += 1
            else:
                errors.append(f"HTTP {response.status_code}")
        except requests.exceptions.Timeout:
            errors.append("Timeout")
        except Exception as e:
            errors.append(str(e))
    
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
            'success_tests': success_count,
            'errors': errors
        }
    else:
        return {
            'success': False,
            'success_rate': 0,
            'total_tests': num_tests,
            'success_tests': 0,
            'errors': errors
        }

def test_download_speed(proxy_host, proxy_port, test_url, duration=10):
    """Test download speed qua proxy"""
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
            
    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'Timeout'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def check_gost_process():
    """Kiểm tra process gost"""
    try:
        result = subprocess.run(['pgrep', '-f', 'gost.*7891'], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            return {'running': True, 'pids': pids}
        else:
            return {'running': False, 'pids': []}
    except Exception as e:
        return {'running': False, 'error': str(e)}

def check_port_listening(port):
    """Kiểm tra port có đang listen không"""
    try:
        result = subprocess.run(['lsof', '-i', f':{port}'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return {'listening': True, 'info': result.stdout.strip()}
        else:
            return {'listening': False}
    except Exception as e:
        return {'listening': False, 'error': str(e)}

def check_upstream_server(proxy_url):
    """Kiểm tra upstream server từ config"""
    try:
        import json
        import os
        
        config_file = os.path.join(os.path.dirname(__file__), 'config', 'gost_7891.config')
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                proxy_url = config.get('proxy_url', '')
                
                # Parse proxy URL để lấy host và port
                if proxy_url.startswith('https://'):
                    # Format: https://user:pass@host:port
                    url_part = proxy_url.split('@')[-1]
                    if ':' in url_part:
                        host = url_part.split(':')[0]
                        port = url_part.split(':')[1].split('/')[0]
                        return {'host': host, 'port': port, 'proxy_url': proxy_url}
        
        return {'error': 'Cannot parse config'}
    except Exception as e:
        return {'error': str(e)}

def test_direct_connection(host, port):
    """Test kết nối trực tiếp đến upstream server"""
    try:
        start_time = time.time()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, int(port)))
        end_time = time.time()
        sock.close()
        
        if result == 0:
            latency = (end_time - start_time) * 1000
            return {'success': True, 'latency': latency}
        else:
            return {'success': False, 'error': f'Connection failed: {result}'}
    except socket.timeout:
        return {'success': False, 'error': 'Connection timeout'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def analyze_logs():
    """Phân tích log để tìm vấn đề"""
    try:
        import os
        log_file = os.path.join(os.path.dirname(__file__), 'logs', 'gost_7891.log')
        
        if not os.path.exists(log_file):
            return {'error': 'Log file not found'}
        
        # Đọc 100 dòng cuối
        with open(log_file, 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-100:] if len(lines) > 100 else lines
        
        timeout_count = sum(1 for line in recent_lines if 'timeout' in line.lower())
        error_count = sum(1 for line in recent_lines if 'error' in line.lower() or 'failed' in line.lower())
        
        return {
            'timeout_count': timeout_count,
            'error_count': error_count,
            'recent_lines': len(recent_lines)
        }
    except Exception as e:
        return {'error': str(e)}

def main():
    print("🚀 Gost 7891 Speed Test & Analysis")
    print("=" * 70)
    
    proxy_host = "127.0.0.1"
    proxy_port = 7891
    
    # 1. Kiểm tra process và port
    print("\n📋 System Check:")
    print("-" * 70)
    
    gost_process = check_gost_process()
    if gost_process.get('running'):
        print(f"✅ Gost process running: PIDs {', '.join(gost_process['pids'])}")
    else:
        print(f"❌ Gost process not running")
        if 'error' in gost_process:
            print(f"   Error: {gost_process['error']}")
    
    port_status = check_port_listening(proxy_port)
    if port_status.get('listening'):
        print(f"✅ Port {proxy_port} is listening")
        if 'info' in port_status:
            print(f"   {port_status['info']}")
    else:
        print(f"❌ Port {proxy_port} is not listening")
    
    # 2. Kiểm tra upstream server
    print("\n🌐 Upstream Server Check:")
    print("-" * 70)
    
    upstream = check_upstream_server("")
    if 'host' in upstream:
        print(f"   Server: {upstream['host']}:{upstream['port']}")
        
        # Test kết nối trực tiếp
        direct_test = test_direct_connection(upstream['host'], upstream['port'])
        if direct_test.get('success'):
            print(f"✅ Direct connection: {direct_test['latency']:.2f}ms")
        else:
            print(f"❌ Direct connection failed: {direct_test.get('error', 'Unknown')}")
    else:
        print(f"⚠️  Cannot get upstream server info: {upstream.get('error', 'Unknown')}")
    
    # 3. Phân tích log
    print("\n📊 Log Analysis:")
    print("-" * 70)
    
    log_analysis = analyze_logs()
    if 'error' not in log_analysis:
        print(f"   Recent log lines: {log_analysis['recent_lines']}")
        print(f"   Timeout errors: {log_analysis['timeout_count']}")
        print(f"   Other errors: {log_analysis['error_count']}")
        
        if log_analysis['timeout_count'] > 5:
            print(f"   ⚠️  WARNING: High timeout count detected!")
    else:
        print(f"   ⚠️  {log_analysis['error']}")
    
    # 4. Test kết nối qua proxy
    print("\n🔌 Proxy Connection Test:")
    print("-" * 70)
    
    connection_test = test_connection(proxy_host, proxy_port)
    if connection_test.get('success'):
        print(f"✅ Connected! IP: {connection_test['ip']}, Latency: {connection_test['latency']:.2f}ms")
    else:
        print(f"❌ Connection failed: {connection_test.get('error', 'Unknown')}")
        print("\n❌ Cannot continue speed test - connection failed")
        return
    
    # 5. Test ping
    print("\n⏱️  Ping Test:")
    print("-" * 70)
    
    ping_result = test_ping(proxy_host, proxy_port, TEST_URLS['small'], num_tests=10)
    if ping_result.get('success'):
        print(f"✅ Ping Results:")
        print(f"   Average: {ping_result['avg']:.2f}ms")
        print(f"   Min: {ping_result['min']:.2f}ms")
        print(f"   Max: {ping_result['max']:.2f}ms")
        print(f"   Median: {ping_result['median']:.2f}ms")
        print(f"   Success Rate: {ping_result['success_rate']:.1f}%")
        
        if ping_result['errors']:
            print(f"   Errors: {', '.join(set(ping_result['errors'][:5]))}")
        
        # Phân tích
        if ping_result['avg'] > 5000:
            print(f"   ⚠️  WARNING: Very high latency (>5s)")
        elif ping_result['avg'] > 2000:
            print(f"   ⚠️  WARNING: High latency (>2s)")
    else:
        print(f"❌ Ping test failed")
        if ping_result.get('errors'):
            print(f"   Errors: {', '.join(set(ping_result['errors'][:5]))}")
    
    # 6. Test download speed
    print("\n📦 Download Speed Test:")
    print("-" * 70)
    
    print("   Small file (1MB)...")
    speed_small = test_download_speed(proxy_host, proxy_port, TEST_URLS['medium'], duration=10)
    if speed_small.get('success'):
        print(f"   ✅ Speed: {speed_small['speed_mbps']:.2f} Mbps ({speed_small['speed_mb_s']:.2f} MB/s)")
        print(f"   Data: {speed_small['bytes'] / 1024 / 1024:.2f} MB in {speed_small['time']:.2f}s")
    else:
        print(f"   ❌ Failed: {speed_small.get('error', 'Unknown')}")
    
    print("\n   Large file (10MB)...")
    speed_large = test_download_speed(proxy_host, proxy_port, TEST_URLS['large'], duration=30)
    if speed_large.get('success'):
        print(f"   ✅ Speed: {speed_large['speed_mbps']:.2f} Mbps ({speed_large['speed_mb_s']:.2f} MB/s)")
        print(f"   Data: {speed_large['bytes'] / 1024 / 1024:.2f} MB in {speed_large['time']:.2f}s")
    else:
        print(f"   ❌ Failed: {speed_large.get('error', 'Unknown')}")
    
    # 7. Tổng kết và đề xuất
    print("\n💡 Analysis & Recommendations:")
    print("-" * 70)
    
    issues = []
    
    if log_analysis.get('timeout_count', 0) > 5:
        issues.append("High timeout count in logs - upstream server may be slow or unreachable")
    
    if ping_result.get('success') and ping_result.get('avg', 0) > 2000:
        issues.append(f"High latency ({ping_result['avg']:.0f}ms) - network or server issue")
    
    if ping_result.get('success_rate', 100) < 80:
        issues.append(f"Low success rate ({ping_result['success_rate']:.1f}%) - connection instability")
    
    if speed_small.get('success') and speed_small.get('speed_mbps', 0) < 1:
        issues.append("Very slow download speed - possible bandwidth limitation")
    
    if issues:
        print("   ⚠️  Issues detected:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        print("\n   💡 Recommendations:")
        print("   1. Check upstream server status (lk-02.protonvpn.net)")
        print("   2. Check network connectivity to ProtonVPN")
        print("   3. Try restarting gost: ./manage_gost.sh restart-port 7891")
        print("   4. Check if server is overloaded or far from your location")
    else:
        print("   ✅ No major issues detected")
    
    print(f"\n{'='*70}")
    print("✅ Test completed!")
    print(f"{'='*70}\n")

if __name__ == '__main__':
    main()

