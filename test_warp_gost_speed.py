#!/usr/bin/env python3
"""
Script test tốc độ và ping giữa WARP (8111) và Gost (7890)
"""

import time
import requests
import socket
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

# Test URLs
TEST_URLS = {
    'small': 'https://api.ipify.org',  # ~20 bytes
    'medium': 'https://speed.cloudflare.com/__down?bytes=1048576',  # 1MB
    'large': 'https://speed.cloudflare.com/__down?bytes=10485760',  # 10MB
}

def test_ping(proxy_host, proxy_port, test_url, num_tests=10):
    """Test ping/latency qua proxy"""
    proxies = {
        'http': f'socks5h://{proxy_host}:{proxy_port}',
        'https': f'socks5h://{proxy_host}:{proxy_port}'
    }
    
    latencies = []
    success_count = 0
    
    print(f"  📍 Testing ping ({num_tests} requests)...")
    
    for i in range(num_tests):
        try:
            start_time = time.time()
            response = requests.get(test_url, proxies=proxies, timeout=10)
            end_time = time.time()
            
            if response.status_code == 200:
                latency = (end_time - start_time) * 1000  # Convert to ms
                latencies.append(latency)
                success_count += 1
        except Exception as e:
            print(f"    ⚠️  Request {i+1} failed: {e}")
    
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

def test_connection(proxy_host, proxy_port):
    """Test kết nối cơ bản"""
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
        response = requests.get('https://api.ipify.org', proxies=proxies, timeout=10)
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

def run_test_suite(proxy_name, proxy_host, proxy_port):
    """Chạy bộ test đầy đủ cho một proxy"""
    print(f"\n{'='*60}")
    print(f"🧪 Testing {proxy_name}")
    print(f"   Proxy: socks5h://{proxy_host}:{proxy_port}")
    print(f"{'='*60}")
    
    results = {
        'name': proxy_name,
        'host': proxy_host,
        'port': proxy_port,
        'connection': None,
        'ping': None,
        'download_small': None,
        'download_medium': None,
        'download_large': None
    }
    
    # Test connection
    results['connection'] = test_connection(proxy_host, proxy_port)
    if not results['connection']['success']:
        print(f"  ❌ Connection failed: {results['connection'].get('error', 'Unknown error')}")
        return results
    
    print(f"  ✅ Connected! IP: {results['connection']['ip']}, Latency: {results['connection']['latency']:.2f}ms")
    
    # Test ping
    results['ping'] = test_ping(proxy_host, proxy_port, TEST_URLS['small'], num_tests=10)
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
    results['download_small'] = test_download_speed(proxy_host, proxy_port, TEST_URLS['medium'], duration=10)
    if results['download_small']['success']:
        print(f"     Speed: {results['download_small']['speed_mbps']:.2f} Mbps ({results['download_small']['speed_mb_s']:.2f} MB/s)")
        print(f"     Downloaded: {results['download_small']['bytes'] / 1024 / 1024:.2f} MB in {results['download_small']['time']:.2f}s")
    else:
        print(f"     ❌ Failed: {results['download_small'].get('error', 'Unknown error')}")
    
    # Test download speed - large
    print(f"\n  📦 Large file test (10MB)...")
    results['download_large'] = test_download_speed(proxy_host, proxy_port, TEST_URLS['large'], duration=15)
    if results['download_large']['success']:
        print(f"     Speed: {results['download_large']['speed_mbps']:.2f} Mbps ({results['download_large']['speed_mb_s']:.2f} MB/s)")
        print(f"     Downloaded: {results['download_large']['bytes'] / 1024 / 1024:.2f} MB in {results['download_large']['time']:.2f}s")
    else:
        print(f"     ❌ Failed: {results['download_large'].get('error', 'Unknown error')}")
    
    return results

def print_comparison(warp_results, gost_results):
    """In so sánh kết quả"""
    print(f"\n{'='*60}")
    print(f"📊 COMPARISON RESULTS")
    print(f"{'='*60}")
    
    # Connection comparison
    print(f"\n🔌 Connection:")
    if warp_results['connection']['success'] and gost_results['connection']['success']:
        warp_latency = warp_results['connection']['latency']
        gost_latency = gost_results['connection']['latency']
        diff = gost_latency - warp_latency
        diff_pct = (diff / warp_latency) * 100
        
        print(f"   WARP:  {warp_latency:.2f}ms")
        print(f"   Gost:  {gost_latency:.2f}ms ({diff:+.2f}ms, {diff_pct:+.1f}%)")
        
        if diff > 0:
            print(f"   ⚠️  Gost slower by {diff:.2f}ms")
        else:
            print(f"   ✅ Gost faster by {abs(diff):.2f}ms")
    
    # Ping comparison
    if warp_results['ping'] and warp_results['ping']['success'] and gost_results['ping'] and gost_results['ping']['success']:
        print(f"\n📍 Ping (Average):")
        warp_avg = warp_results['ping']['avg']
        gost_avg = gost_results['ping']['avg']
        diff = gost_avg - warp_avg
        diff_pct = (diff / warp_avg) * 100
        
        print(f"   WARP:  {warp_avg:.2f}ms")
        print(f"   Gost:  {gost_avg:.2f}ms ({diff:+.2f}ms, {diff_pct:+.1f}%)")
        
        print(f"\n📍 Ping (Median):")
        warp_median = warp_results['ping']['median']
        gost_median = gost_results['ping']['median']
        diff_median = gost_median - warp_median
        
        print(f"   WARP:  {warp_median:.2f}ms")
        print(f"   Gost:  {gost_median:.2f}ms ({diff_median:+.2f}ms)")
    
    # Download speed comparison
    if warp_results['download_large'] and warp_results['download_large']['success'] and \
       gost_results['download_large'] and gost_results['download_large']['success']:
        print(f"\n⬇️  Download Speed (Large file):")
        warp_speed = warp_results['download_large']['speed_mbps']
        gost_speed = gost_results['download_large']['speed_mbps']
        diff = gost_speed - warp_speed
        diff_pct = (diff / warp_speed) * 100
        
        print(f"   WARP:  {warp_speed:.2f} Mbps")
        print(f"   Gost:  {gost_speed:.2f} Mbps ({diff:+.2f} Mbps, {diff_pct:+.1f}%)")
        
        if diff < 0:
            print(f"   ⚠️  Gost slower by {abs(diff):.2f} Mbps ({abs(diff_pct):.1f}%)")
        else:
            print(f"   ✅ Gost faster by {diff:.2f} Mbps ({diff_pct:.1f}%)")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    
    if warp_results['ping'] and warp_results['ping']['success'] and gost_results['ping'] and gost_results['ping']['success']:
        latency_overhead = gost_results['ping']['avg'] - warp_results['ping']['avg']
        if latency_overhead > 50:
            print(f"   ⚠️  High latency overhead ({latency_overhead:.2f}ms). Consider optimizing Gost timeout settings.")
        elif latency_overhead > 20:
            print(f"   ⚠️  Moderate latency overhead ({latency_overhead:.2f}ms). May benefit from optimization.")
        else:
            print(f"   ✅ Low latency overhead ({latency_overhead:.2f}ms). Performance is good.")
    
    if warp_results['download_large'] and warp_results['download_large']['success'] and \
       gost_results['download_large'] and gost_results['download_large']['success']:
        speed_loss = ((warp_results['download_large']['speed_mbps'] - gost_results['download_large']['speed_mbps']) / warp_results['download_large']['speed_mbps']) * 100
        if speed_loss > 20:
            print(f"   ⚠️  Significant speed loss ({speed_loss:.1f}%). Consider optimizing buffer sizes.")
        elif speed_loss > 10:
            print(f"   ⚠️  Moderate speed loss ({speed_loss:.1f}%). May benefit from optimization.")
        else:
            print(f"   ✅ Minimal speed loss ({speed_loss:.1f}%). Performance is good.")

def main():
    print("🚀 WARP vs Gost Speed Test")
    print("=" * 60)
    
    # Test WARP (8111)
    warp_results = run_test_suite("WARP", "127.0.0.1", 8111)
    
    # Test Gost (7890)
    gost_results = run_test_suite("Gost 7890", "127.0.0.1", 7890)
    
    # Print comparison
    if warp_results['connection']['success'] and gost_results['connection']['success']:
        print_comparison(warp_results, gost_results)
    else:
        print("\n❌ Cannot compare - one or both proxies failed connection test")
        if not warp_results['connection']['success']:
            print(f"   WARP failed: {warp_results['connection'].get('error', 'Unknown')}")
        if not gost_results['connection']['success']:
            print(f"   Gost failed: {gost_results['connection'].get('error', 'Unknown')}")
    
    print(f"\n{'='*60}")
    print("✅ Test completed!")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()

