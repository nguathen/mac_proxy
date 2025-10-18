#!/usr/bin/env python3
"""
NordVPN CLI Tool
Command line tool để quản lý NordVPN servers
"""

import sys
import argparse
from nordvpn_api import NordVPNAPI
import os

def main():
    parser = argparse.ArgumentParser(description='NordVPN Server Management CLI')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # List countries
    list_countries = subparsers.add_parser('countries', help='List all countries')
    
    # List servers
    list_servers = subparsers.add_parser('servers', help='List servers')
    list_servers.add_argument('--country', '-c', help='Filter by country code')
    list_servers.add_argument('--limit', '-l', type=int, default=20, help='Limit number of results')
    list_servers.add_argument('--refresh', '-r', action='store_true', help='Force refresh from API')
    
    # Get best server
    best_server = subparsers.add_parser('best', help='Get best server')
    best_server.add_argument('--country', '-c', help='Filter by country code')
    
    # Apply server
    apply_server = subparsers.add_parser('apply', help='Apply server to wireproxy instance')
    apply_server.add_argument('instance', type=int, choices=[1, 2], help='Wireproxy instance (1 or 2)')
    apply_server.add_argument('--server', '-s', required=True, help='Server name')
    apply_server.add_argument('--private-key', '-k', help='Private key (will read from config if not provided)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    api = NordVPNAPI()
    
    if args.command == 'countries':
        print("Loading countries...")
        countries = api.get_countries()
        print(f"\nFound {len(countries)} countries:\n")
        print(f"{'Code':<6} {'Name':<30} {'Servers':<10}")
        print("-" * 50)
        for country in countries:
            print(f"{country['code']:<6} {country['name']:<30} {country['server_count']:<10}")
    
    elif args.command == 'servers':
        print("Loading servers...")
        if args.country:
            servers = api.get_servers_by_country(args.country)
            print(f"\nServers in {args.country}:\n")
        else:
            servers = api.fetch_servers(force_refresh=args.refresh)
            print(f"\nAll servers:\n")
        
        if not servers:
            print("No servers found")
            return
        
        # Sort by load
        servers = sorted(servers, key=lambda x: x['load'])[:args.limit]
        
        print(f"{'Name':<20} {'Country':<15} {'City':<15} {'Load':<8} {'IP':<20} {'Status':<10}")
        print("-" * 100)
        for server in servers:
            city = server['country'].get('city', 'N/A')
            print(f"{server['name']:<20} {server['country']['name']:<15} {city:<15} {server['load']:<7}% {server['station']:<20} {server['status']:<10}")
    
    elif args.command == 'best':
        print("Finding best server...")
        server = api.get_best_server(args.country)
        
        if not server:
            print("No server found")
            return
        
        print(f"\nBest server:")
        print(f"  Name: {server['name']}")
        print(f"  Country: {server['country']['name']} ({server['country']['code']})")
        if server['country'].get('city'):
            print(f"  City: {server['country']['city']}")
        print(f"  IP: {server['station']}")
        print(f"  Load: {server['load']}%")
        print(f"  Status: {server['status']}")
        print(f"  Public Key: {server['public_key']}")
    
    elif args.command == 'apply':
        print(f"Applying server to Wireproxy {args.instance}...")
        
        # Get server info
        server = api.get_server_by_name(args.server)
        if not server:
            print(f"Error: Server '{args.server}' not found")
            return
        
        # Get private key
        if args.private_key:
            private_key = args.private_key
        else:
            # Read from config file
            config_file = f'wg1818{args.instance}.conf'
            if not os.path.exists(config_file):
                print(f"Error: Config file {config_file} not found")
                print("Please provide private key with --private-key")
                return
            
            # Parse config to get private key
            with open(config_file, 'r') as f:
                for line in f:
                    if line.strip().startswith('PrivateKey'):
                        private_key = line.split('=', 1)[1].strip()
                        break
                else:
                    print(f"Error: PrivateKey not found in {config_file}")
                    return
        
        # Generate config
        bind_address = f"127.0.0.1:1818{args.instance}"
        config = api.generate_wireguard_config(
            server=server,
            private_key=private_key,
            bind_address=bind_address
        )
        
        # Write config
        config_file = f'wg1818{args.instance}.conf'
        
        # Backup old config
        if os.path.exists(config_file):
            import shutil
            backup_file = f"{config_file}.backup"
            shutil.copy(config_file, backup_file)
            print(f"Backed up old config to {backup_file}")
        
        # Write new config
        with open(config_file, 'w') as f:
            f.write('[Interface]\n')
            for key, value in config['interface'].items():
                f.write(f'{key} = {value}\n')
            
            f.write('\n[Peer]\n')
            for key, value in config['peer'].items():
                f.write(f'{key} = {value}\n')
            
            f.write('\n[Socks5]\n')
            for key, value in config['socks5'].items():
                f.write(f'{key} = {value}\n')
        
        print(f"\n✅ Config saved to {config_file}")
        print(f"\nServer details:")
        print(f"  Name: {server['name']}")
        print(f"  Country: {server['country']['name']}")
        print(f"  IP: {server['station']}")
        print(f"  Load: {server['load']}%")
        print(f"\nRestart wireproxy to apply changes:")
        print(f"  bash manage_wireproxy.sh restart")

if __name__ == '__main__':
    main()

