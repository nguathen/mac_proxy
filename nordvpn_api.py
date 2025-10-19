#!/usr/bin/env python3
"""
NordVPN API Module
Lấy danh sách server NordVPN và thông tin cấu hình
"""

import requests
import json
from typing import List, Dict, Optional
import os

NORDVPN_API_URL = "https://api.nordvpn.com/v1"
CACHE_FILE = "nordvpn_servers_cache.json"
CACHE_DURATION = 3600  # 1 hour

# Default private key for NordVPN
DEFAULT_PRIVATE_KEY = "ECDeW1Oi8TC5reUZcyp8n3KAOaDVz3ZXZB5tu1+8Ik4="

class NordVPNAPI:
    def __init__(self, cache_file=CACHE_FILE):
        self.cache_file = cache_file
        self.servers = []
    
    def fetch_servers(self, force_refresh=False) -> List[Dict]:
        """Lấy danh sách server từ NordVPN API hoặc cache"""
        
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
        
        # Fetch from API
        try:
            # Get all servers with WireGuard support
            response = requests.get(
                f"{NORDVPN_API_URL}/servers",
                params={
                    "limit": 100000,
                    "filters[servers_technologies][identifier]": "wireguard_udp"
                },
                timeout=30
            )
            response.raise_for_status()
            
            raw_servers = response.json()
            
            # Parse and format servers
            self.servers = []
            for server in raw_servers:
                # Get WireGuard technology details
                wg_tech = None
                for tech in server.get('technologies', []):
                    if tech.get('identifier') == 'wireguard_udp':
                        wg_tech = tech
                        break
                
                if not wg_tech:
                    continue
                
                # Get public key from metadata
                public_key = wg_tech.get('metadata', [{}])[0].get('value', '')
                if not public_key:
                    continue
                
                # Get station (IP address)
                station = server.get('station', '')
                if not station:
                    continue
                
                # Get location info
                locations = server.get('locations', [{}])
                location = locations[0] if locations else {}
                country = location.get('country', {})
                
                server_info = {
                    'id': server.get('id'),
                    'name': server.get('name'),
                    'hostname': server.get('hostname'),
                    'station': station,
                    'public_key': public_key,
                    'country': {
                        'name': country.get('name', 'Unknown'),
                        'code': country.get('code', 'XX'),
                        'city': country.get('city', {}).get('name', '')
                    },
                    'load': server.get('load', 0),
                    'status': server.get('status', 'unknown')
                }
                
                self.servers.append(server_info)
            
            # Sort by country and load
            self.servers.sort(key=lambda x: (x['country']['name'], x['load']))
            
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
            
            raise Exception(f"Failed to fetch NordVPN servers: {str(e)}")
    
    def get_servers_by_country(self, country_code: str) -> List[Dict]:
        """Lấy danh sách server theo quốc gia"""
        if not self.servers:
            self.fetch_servers()
        
        return [s for s in self.servers if s['country']['code'].lower() == country_code.lower()]
    
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
                    'server_count': 0
                }
            countries[code]['server_count'] += 1
        
        return sorted(countries.values(), key=lambda x: x['name'])
    
    def get_server_by_name(self, name: str) -> Optional[Dict]:
        """Lấy thông tin server theo tên"""
        if not self.servers:
            self.fetch_servers()
        
        for server in self.servers:
            if server['name'].lower() == name.lower() or server['hostname'].lower() == name.lower():
                return server
        
        return None
    
    def get_best_server(self, country_code: Optional[str] = None) -> Optional[Dict]:
        """Lấy server tốt nhất (load thấp nhất)"""
        if not self.servers:
            self.fetch_servers()
        
        servers = self.servers
        if country_code:
            servers = self.get_servers_by_country(country_code)
        
        if not servers:
            return None
        
        # Filter only online servers
        online_servers = [s for s in servers if s['status'] == 'online']
        if not online_servers:
            return None
        
        # Sort by load
        return min(online_servers, key=lambda x: x['load'])
    
    def generate_wireguard_config(self, server: Dict, private_key: str = None, 
                                  address: str = "10.5.0.2/16", 
                                  dns: str = "103.86.96.100",
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
                'Endpoint': f"{server['station']}:51820",
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
    api = NordVPNAPI()
    
    print("Fetching NordVPN servers...")
    servers = api.fetch_servers()
    print(f"Found {len(servers)} servers")
    
    print("\nCountries:")
    countries = api.get_countries()
    for country in countries[:10]:
        print(f"  {country['code']}: {country['name']} ({country['server_count']} servers)")
    
    print("\nBest server:")
    best = api.get_best_server()
    if best:
        print(f"  {best['name']} - {best['country']['name']} (Load: {best['load']}%)")
        print(f"  Station: {best['station']}")
        print(f"  Public Key: {best['public_key'][:20]}...")

