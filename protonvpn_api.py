#!/usr/bin/env python3
"""
ProtonVPN API Module
Lấy danh sách server ProtonVPN và thông tin cấu hình
"""

import requests
import json
from typing import List, Dict, Optional
import os

PROTONVPN_API_URL = "https://account.proton.me/api/vpn/v1/logicals"
CACHE_FILE = "protonvpn_servers_cache.json"
CACHE_DURATION = 3600  # 1 hour

# ProtonVPN API credentials (example - user should provide their own)
# Get these from ProtonVPN account
PROTONVPN_AUTH = {
    'bearer_token': '',  # User's bearer token
    'uid': ''  # User's UID
}

# Default private key (user can override)
DEFAULT_PRIVATE_KEY = "mHp/fZJpapyDKr4QT1SVZGg5xgNkpJUKNCXVk7P7yk4="

class ProtonVPNAPI:
    def __init__(self, cache_file=CACHE_FILE, bearer_token='', uid=''):
        self.cache_file = cache_file
        self.servers = []
        self.bearer_token = bearer_token or PROTONVPN_AUTH.get('bearer_token', '')
        self.uid = uid or PROTONVPN_AUTH.get('uid', '')
    
    def fetch_servers(self, force_refresh=False) -> List[Dict]:
        """Lấy danh sách server từ ProtonVPN API hoặc cache"""
        
        # Check cache first
        if not force_refresh and os.path.exists(self.cache_file):
            try:
                import time
                cache_age = time.time() - os.path.getmtime(self.cache_file)
                if cache_age < CACHE_DURATION:
                    with open(self.cache_file, 'r') as f:
                        self.servers = json.load(f)
                        return self.servers
            except Exception:
                pass
        
        # Check if we have credentials
        if not self.bearer_token or not self.uid:
            raise Exception("ProtonVPN credentials not provided. Please set bearer_token and uid.")
        
        # Fetch from API
        try:
            headers = {
                'x-pm-single-group': 'vpn-paid',
                'x-pm-apiversion': '3',
                'x-pm-appversion': 'windows-vpn@4.3.1-dev+X64',
                'x-pm-locale': 'en-US',
                'User-Agent': 'ProtonVPN/4.3.1],[(Microsoft Windows NT 10.0.26100.0; X64)',
                'x-pm-timezone': 'Asia/Bangkok',
                'Authorization': f'Bearer {self.bearer_token}',
                'x-pm-uid': self.uid,
                'Accept': 'application/json'
            }
            
            # Add limit parameter to get all servers
            params = {
                'Limit': 100000
            }
            
            response = requests.get(PROTONVPN_API_URL, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            
            raw_data = response.json()
            logical_servers = raw_data.get('LogicalServers', [])
            
            # Parse and format servers
            self.servers = []
            for server in logical_servers:
                # Get physical servers for WireGuard endpoints
                physical_servers = server.get('Servers', [])
                if not physical_servers:
                    continue
                
                # Get first physical server's entry IP
                entry_ip = physical_servers[0].get('EntryIP', '')
                if not entry_ip:
                    continue
                
                # Get WireGuard public key (X25519PublicKey)
                x25519_key = physical_servers[0].get('X25519PublicKey', '')
                if not x25519_key:
                    continue
                
                # Get location info
                city = server.get('City', '')
                country = server.get('ExitCountry', 'XX')
                
                # Get server load
                load = server.get('Load', 0)
                
                # Get server status (1 = online)
                status = 'online' if server.get('Status', 0) == 1 else 'offline'
                
                # Get tier (0 = free, 1 = basic, 2 = plus/premium)
                tier = server.get('Tier', 0)
                tier_name = {0: 'Free', 1: 'Basic', 2: 'Plus'}.get(tier, 'Unknown')
                
                # Get features
                features = server.get('Features', 0)
                
                server_info = {
                    'id': server.get('ID', ''),
                    'name': server.get('Name', ''),
                    'domain': server.get('Domain', ''),
                    'entry_ip': entry_ip,
                    'public_key': x25519_key,
                    'country': {
                        'name': self._get_country_name(country),
                        'code': country,
                        'city': city
                    },
                    # Flatten for easier UI access
                    'country_name': self._get_country_name(country),
                    'country_code': country,
                    'city': city,
                    'load': load,
                    'status': status,
                    'tier': tier,
                    'tier_name': tier_name,
                    'features': features,
                    'score': server.get('Score', 0)
                }
                
                self.servers.append(server_info)
            
            # Sort by country, tier, and load
            self.servers.sort(key=lambda x: (x['country']['name'], x['tier'], x['load']))
            
            # Save to cache
            try:
                with open(self.cache_file, 'w') as f:
                    json.dump(self.servers, f, indent=2)
            except Exception:
                pass
            
            return self.servers
            
        except Exception as e:
            # If API fails, try to load from cache
            if os.path.exists(self.cache_file):
                try:
                    with open(self.cache_file, 'r') as f:
                        self.servers = json.load(f)
                        return self.servers
                except Exception:
                    pass
            
            raise Exception(f"Failed to fetch ProtonVPN servers: {str(e)}")
    
    def _get_country_name(self, code: str) -> str:
        """Convert country code to name"""
        countries = {
            'US': 'United States', 'GB': 'United Kingdom', 'DE': 'Germany',
            'FR': 'France', 'NL': 'Netherlands', 'CH': 'Switzerland',
            'CA': 'Canada', 'AU': 'Australia', 'JP': 'Japan',
            'SG': 'Singapore', 'SE': 'Sweden', 'ES': 'Spain',
            'IT': 'Italy', 'BE': 'Belgium', 'AT': 'Austria',
            'DK': 'Denmark', 'NO': 'Norway', 'FI': 'Finland',
            'PL': 'Poland', 'CZ': 'Czech Republic', 'RO': 'Romania',
            'IS': 'Iceland', 'HK': 'Hong Kong', 'IN': 'India',
            'BR': 'Brazil', 'AR': 'Argentina', 'MX': 'Mexico',
            'ZA': 'South Africa', 'IL': 'Israel', 'AE': 'United Arab Emirates',
            'TR': 'Turkey', 'KR': 'South Korea', 'TW': 'Taiwan',
            'UA': 'Ukraine', 'PT': 'Portugal', 'IE': 'Ireland',
            'LU': 'Luxembourg', 'BG': 'Bulgaria', 'GR': 'Greece',
            'HU': 'Hungary', 'SK': 'Slovakia', 'RS': 'Serbia',
            'HR': 'Croatia', 'EE': 'Estonia', 'LV': 'Latvia',
            'LT': 'Lithuania', 'MD': 'Moldova', 'AL': 'Albania',
            'CL': 'Chile', 'CR': 'Costa Rica', 'PE': 'Peru'
        }
        return countries.get(code, code)
    
    def get_servers_by_country(self, country_code: str) -> List[Dict]:
        """Lấy danh sách server theo quốc gia"""
        if not self.servers:
            self.fetch_servers()
        
        return [s for s in self.servers if s['country']['code'].lower() == country_code.lower()]
    
    def get_servers_by_tier(self, tier: int) -> List[Dict]:
        """Lấy danh sách server theo tier (0=Free, 1=Basic, 2=Plus)"""
        if not self.servers:
            self.fetch_servers()
        
        return [s for s in self.servers if s['tier'] >= tier]
    
    def get_countries(self) -> List[Dict]:
        """Lấy danh sách các quốc gia có server"""
        if not self.servers:
            self.fetch_servers()
        
        countries = {}
        for server in self.servers:
            code = server['country']['code']
            if code not in countries:
                countries[code] = {
                    'code': code,
                    'name': server['country']['name'],
                    'server_count': 0,
                    'free_count': 0,
                    'plus_count': 0
                }
            countries[code]['server_count'] += 1
            if server['tier'] == 0:
                countries[code]['free_count'] += 1
            elif server['tier'] >= 2:
                countries[code]['plus_count'] += 1
        
        return sorted(countries.values(), key=lambda x: x['name'])
    
    def get_server_by_name(self, name: str) -> Optional[Dict]:
        """Lấy thông tin server theo tên"""
        if not self.servers:
            self.fetch_servers()
        
        for server in self.servers:
            if server['name'].lower() == name.lower() or server['domain'].lower() == name.lower():
                return server
        
        return None
    
    def get_best_server(self, country_code: Optional[str] = None, tier: Optional[int] = None) -> Optional[Dict]:
        """Lấy server tốt nhất (load thấp nhất)"""
        if not self.servers:
            self.fetch_servers()
        
        servers = self.servers
        
        # Filter by country
        if country_code:
            servers = [s for s in servers if s['country']['code'].lower() == country_code.lower()]
        
        # Filter by tier
        if tier is not None:
            servers = [s for s in servers if s['tier'] >= tier]
        
        if not servers:
            return None
        
        # Filter only online servers
        online_servers = [s for s in servers if s['status'] == 'online']
        if not online_servers:
            return None
        
        # Sort by load and score
        return min(online_servers, key=lambda x: (x['load'], -x['score']))
    
    def generate_wireguard_config(self, server: Dict, private_key: str = None, 
                                  address: str = "10.2.0.2/32", 
                                  dns: str = "10.2.0.1",
                                  bind_address: str = "127.0.0.1:18181") -> Dict:
        """Tạo config WireGuard từ thông tin server"""
        
        # Use default private key if not provided
        if not private_key:
            private_key = DEFAULT_PRIVATE_KEY
        
        config = {
            'interface': {
                'PrivateKey': private_key,
                'Address': address,
                'DNS': dns
            },
            'peer': {
                'PublicKey': server['public_key'],
                'Endpoint': f"{server['entry_ip']}:51820",
                'AllowedIPs': '0.0.0.0/0',
                'PersistentKeepalive': '25'
            },
            'socks5': {
                'BindAddress': bind_address
            }
        }
        
        return config


if __name__ == '__main__':
    # Test the API
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python3 protonvpn_api.py <bearer_token> <uid>")
        print("\nTo get credentials:")
        print("1. Login to ProtonVPN web")
        print("2. Open browser DevTools → Network")
        print("3. Look for API requests")
        print("4. Copy Authorization header (Bearer token) and x-pm-uid")
        sys.exit(1)
    
    bearer_token = sys.argv[1]
    uid = sys.argv[2]
    
    api = ProtonVPNAPI(bearer_token=bearer_token, uid=uid)
    
    print("Fetching ProtonVPN servers...")
    try:
        servers = api.fetch_servers()
        print(f"Found {len(servers)} servers")
        
        print("\nCountries:")
        countries = api.get_countries()
        for country in countries[:10]:
            print(f"  {country['code']}: {country['name']} ({country['server_count']} servers, {country['free_count']} free, {country['plus_count']} plus)")
        
        print("\nBest free server:")
        best = api.get_best_server(tier=0)
        if best:
            print(f"  {best['name']} - {best['country']['name']} (Load: {best['load']}%, Tier: {best['tier_name']})")
            print(f"  Entry IP: {best['entry_ip']}")
            print(f"  Public Key: {best['public_key'][:20]}...")
        
        print("\nBest Plus server in US:")
        best_us = api.get_best_server(country_code='US', tier=2)
        if best_us:
            print(f"  {best_us['name']} - {best_us['country']['name']} (Load: {best_us['load']}%)")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

