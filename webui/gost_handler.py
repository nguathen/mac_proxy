"""
Gost Handler
Xử lý các API endpoints liên quan đến Gost
"""

from flask import request, jsonify
import os
import json
import sys
from datetime import datetime

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def register_gost_routes(app, BASE_DIR, LOG_DIR, run_command, save_gost_config, parse_gost_config, is_valid_gost_port, get_available_gost_ports):
    """Đăng ký các routes Gost với Flask app"""
    

    @app.route('/api/gost/config/<port>')
    def api_get_gost_config(port):
        """Lấy config gost theo port"""
        # Validate port using dynamic discovery
        available_ports = get_available_gost_ports()
        if port not in available_ports:
            return jsonify({
                'success': False, 
                'error': f'Invalid port. Available ports: {", ".join(available_ports)}'
            }), 400
        
        config = parse_gost_config(port)
        if config:
            return jsonify({'success': True, 'config': config})
        else:
            return jsonify({'success': False, 'error': 'Cannot read config'}), 500

    @app.route('/api/gost/config/<port>', methods=['POST'])
    def api_save_gost_config(port):
        """Lưu config gost theo port"""
        data = request.json
        
        # Validate port using dynamic discovery
        available_ports = get_available_gost_ports()
        if port not in available_ports:
            return jsonify({
                'success': False, 
                'error': f'Invalid port. Available ports: {", ".join(available_ports)}'
            }), 400
        
        config = data.get('config')
        if not config:
            return jsonify({'success': False, 'error': 'No config provided'}), 400
        
        if save_gost_config(port, config):
            return jsonify({'success': True, 'message': 'Config saved successfully'})
        else:
            return jsonify({'success': False, 'error': 'Cannot save config'}), 500

    @app.route('/api/gost/<action>', methods=['POST'])
    def api_gost_action(action):
        """Điều khiển gost (start/stop/restart)"""
        if action not in ['start', 'stop', 'restart']:
            return jsonify({'success': False, 'error': 'Invalid action'}), 400
        
        result = run_command(f'bash manage_gost.sh {action}', timeout=90)
        
        return jsonify({
            'success': result['success'],
            'output': result['stdout'],
            'error': result['stderr']
        })

    @app.route('/api/gost/<port>/<action>', methods=['POST'])
    def api_gost_port_action(port, action):
        """Điều khiển gost theo port"""
        if action not in ['start', 'stop', 'restart']:
            return jsonify({'success': False, 'error': 'Invalid action'}), 400
        
        # Validate port
        if not is_valid_gost_port(port):
            return jsonify({
                'success': False, 
                'error': f'Invalid port: {port}'
            }), 400
        
        # Use port-based file naming
        pid_file = os.path.join(LOG_DIR, f'gost_{port}.pid')
        
        if action == 'stop':
            # Stop gost service
            if os.path.exists(pid_file):
                try:
                    with open(pid_file) as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 15)  # SIGTERM
                    try:
                        os.remove(pid_file)
                    except Exception:
                        pass
                    return jsonify({
                        'success': True,
                        'message': f'Gost on port {port} stopped successfully'
                    })
                except (OSError, ValueError) as e:
                    return jsonify({
                        'success': False,
                        'error': f'Failed to stop: {str(e)}'
                    }), 500
            else:
                return jsonify({
                    'success': False,
                    'error': 'Gost not running'
                }), 400
        
        elif action == 'start':
            # Check if already running
            if os.path.exists(pid_file):
                try:
                    with open(pid_file) as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 0)  # Check if process exists
                    return jsonify({
                        'success': False,
                        'error': 'Gost already running'
                    }), 400
                except OSError:
                    # Process doesn't exist, remove stale pid file
                    try:
                        os.remove(pid_file)
                    except Exception:
                        pass
            
            # Start gost service
            result = run_command(f'bash manage_gost.sh start-port {port}', timeout=90)
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'message': f'Gost on port {port} started successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to start: {result["stderr"]}'
                }), 500
        
        elif action == 'restart':
            # Restart gost service
            result = run_command(f'bash manage_gost.sh restart-port {port}', timeout=90)
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'message': f'Gost on port {port} restarted successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Failed to restart: {result["stderr"]}'
                }), 500

    @app.route('/api/gost/delete/<port>', methods=['DELETE'])
    def api_gost_delete(port):
        """Xóa gost port"""
        try:
            # Validate port
            if not is_valid_gost_port(port):
                return jsonify({
                    'success': False, 
                    'error': f'Invalid port: {port}'
                }), 400
            
            # Stop gost service first
            pid_file = os.path.join(LOG_DIR, f'gost_{port}.pid')
            if os.path.exists(pid_file):
                try:
                    with open(pid_file) as f:
                        pid = int(f.read().strip())
                    os.kill(pid, 15)  # SIGTERM
                    try:
                        os.remove(pid_file)
                    except Exception:
                        pass
                except (OSError, ValueError):
                    pass
            
            # Remove config file
            config_file = os.path.join(BASE_DIR, 'config', f'gost_{port}.config')
            if os.path.exists(config_file):
                try:
                    os.remove(config_file)
                except Exception:
                    pass
            
            # Remove log file
            log_file = os.path.join(LOG_DIR, f'gost_{port}.log')
            if os.path.exists(log_file):
                try:
                    os.remove(log_file)
                except Exception:
                    pass
            
            return jsonify({
                'success': True,
                'message': f'Gost port {port} deleted successfully'
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/gost/reset-configs', methods=['POST'])
    def api_reset_gost_configs():
        """Reset tất cả gost configs về mặc định"""
        try:
            # Get all available gost ports
            available_ports = get_available_gost_ports()
            
            for port in available_ports:
                # Stop gost service
                pid_file = os.path.join(LOG_DIR, f'gost_{port}.pid')
                if os.path.exists(pid_file):
                    try:
                        with open(pid_file) as f:
                            pid = int(f.read().strip())
                        os.kill(pid, 15)  # SIGTERM
                        try:
                            os.remove(pid_file)
                        except Exception:
                            pass
                    except (OSError, ValueError):
                        pass
                
                # Remove config file
                config_file = os.path.join(BASE_DIR, 'config', f'gost_{port}.config')
                if os.path.exists(config_file):
                    try:
                        os.remove(config_file)
                    except Exception:
                        pass
            
            return jsonify({
                'success': True,
                'message': 'All gost configs reset successfully'
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
