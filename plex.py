from flask import Blueprint, jsonify, request, current_app
import requests
import os
import json
from plexapi.server import PlexServer
from plexapi.exceptions import Unauthorized, NotFound

plex_bp = Blueprint('plex', __name__)

# This would be stored in a config file or environment variables in production
PLEX_SERVER_URL = os.environ.get('PLEX_SERVER_URL', 'http://localhost:32400')
PLEX_TOKEN = os.environ.get('PLEX_TOKEN', '')

@plex_bp.route('/status', methods=['GET'])
def check_plex_status():
    """
    Check if the Plex server is online and accessible.
    Returns a JSON response with the server status.
    """
    try:
        # Try to connect to the Plex server
        response = requests.get(f"{PLEX_SERVER_URL}/identity", 
                               headers={'X-Plex-Token': PLEX_TOKEN}, 
                               timeout=5)
        
        if response.status_code == 200:
            # Server is online and responding
            return jsonify({
                'status': 'online',
                'message': 'Plex server is online and accessible',
                'server_info': response.json()
            })
        else:
            # Server responded but with an error
            return jsonify({
                'status': 'error',
                'message': f'Plex server responded with status code: {response.status_code}'
            })
    
    except requests.exceptions.ConnectionError:
        # Could not connect to the server
        return jsonify({
            'status': 'offline',
            'message': 'Plex server appears to be offline or unreachable'
        })
    
    except requests.exceptions.Timeout:
        # Connection timed out
        return jsonify({
            'status': 'timeout',
            'message': 'Connection to Plex server timed out'
        })
    
    except Exception as e:
        # Any other error
        return jsonify({
            'status': 'error',
            'message': f'Error checking Plex server status: {str(e)}'
        })

@plex_bp.route('/server-info', methods=['GET'])
def get_server_info():
    """
    Get detailed information about the Plex server if it's online.
    """
    try:
        # Try to connect to the Plex server using PlexAPI
        plex = PlexServer(PLEX_SERVER_URL, PLEX_TOKEN)
        
        # Get server information
        server_info = {
            'name': plex.friendlyName,
            'version': plex.version,
            'platform': plex.platform,
            'machine_identifier': plex.machineIdentifier,
            'is_secure': plex.isSecure,
            'updated_at': plex.updatedAt,
        }
        
        # Get some basic library stats
        libraries = []
        for section in plex.library.sections():
            libraries.append({
                'name': section.title,
                'type': section.type,
                'count': section.totalSize
            })
        
        return jsonify({
            'status': 'online',
            'server_info': server_info,
            'libraries': libraries
        })
        
    except (Unauthorized, NotFound, requests.exceptions.ConnectionError):
        return jsonify({
            'status': 'offline',
            'message': 'Plex server is offline or credentials are invalid'
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error retrieving server information: {str(e)}'
        })
