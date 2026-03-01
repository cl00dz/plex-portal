import os
import requests
from flask import Blueprint, jsonify
from plexapi.server import PlexServer
from plexapi.exceptions import Unauthorized, NotFound

plex_bp = Blueprint('plex', __name__)


def _plex_url():
    return os.environ.get('PLEX_SERVER_URL', '').rstrip('/')


def _plex_token():
    return os.environ.get('PLEX_TOKEN', '')


@plex_bp.route('/status', methods=['GET'])
def check_plex_status():
    """Check if the Plex server is online and accessible."""
    plex_url = _plex_url()
    plex_token = _plex_token()

    if not plex_url or not plex_token:
        return jsonify({
            'status': 'unconfigured',
            'message': 'Plex server not configured. Complete setup first.',
        })

    try:
        response = requests.get(
            f"{plex_url}/identity",
            headers={'X-Plex-Token': plex_token, 'Accept': 'application/json'},
            timeout=5,
        )
        if response.status_code == 200:
            return jsonify({
                'status': 'online',
                'message': 'Plex server is online',
                'server_info': response.json().get('MediaContainer', {}),
            })
        return jsonify({
            'status': 'error',
            'message': f'Plex server responded with status {response.status_code}',
        })
    except requests.exceptions.ConnectionError:
        return jsonify({'status': 'offline', 'message': 'Cannot reach Plex server'})
    except requests.exceptions.Timeout:
        return jsonify({'status': 'timeout', 'message': 'Connection to Plex timed out'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error: {str(e)}'})


@plex_bp.route('/server-info', methods=['GET'])
def get_server_info():
    """Get detailed information about the Plex server."""
    plex_url = _plex_url()
    plex_token = _plex_token()

    if not plex_url or not plex_token:
        return jsonify({'status': 'unconfigured', 'message': 'Plex server not configured'})

    try:
        plex = PlexServer(plex_url, plex_token)
        server_info = {
            'name': plex.friendlyName,
            'version': plex.version,
            'platform': plex.platform,
            'machine_identifier': plex.machineIdentifier,
            'is_secure': plex.isSecure,
            'updated_at': str(plex.updatedAt),
        }
        libraries = [
            {'name': s.title, 'type': s.type, 'count': s.totalSize}
            for s in plex.library.sections()
        ]
        return jsonify({'status': 'online', 'server_info': server_info, 'libraries': libraries})
    except (Unauthorized, NotFound, requests.exceptions.ConnectionError):
        return jsonify({'status': 'offline', 'message': 'Plex offline or credentials invalid'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error: {str(e)}'})
