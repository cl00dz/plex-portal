import os
import uuid
import requests
from urllib.parse import urlencode
from flask import Blueprint, jsonify, request, redirect, url_for, session
from src.extensions import limiter

auth_bp = Blueprint('auth', __name__)

PLEX_CLIENT_ID = os.environ.get('PLEX_CLIENT_ID', 'PlexPortal')
PLEX_OAUTH_URL = 'https://app.plex.tv/auth'
PLEX_API_URL = 'https://plex.tv/api/v2'


def _overseerr_url():
    return os.environ.get('OVERSEERR_URL', '').rstrip('/')


def _overseerr_key():
    return os.environ.get('OVERSEERR_API_KEY', '')


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@auth_bp.route('/login', methods=['GET'])
@limiter.limit("10 per minute")
def login():
    """Initiate the Plex OAuth login flow."""
    state = str(uuid.uuid4())
    session['oauth_state'] = state
    params = {
        'clientID': PLEX_CLIENT_ID,
        'code': state,
        'context[device][product]': 'Plex Portal',
        'context[device][environment]': 'Web',
        'context[device][layout]': 'desktop',
        'context[device][platform]': 'Web',
        'forwardUrl': url_for('auth.plex_callback', _external=True),
    }
    return redirect(f"{PLEX_OAUTH_URL}#!{urlencode(params)}")


@auth_bp.route('/callback', methods=['GET'])
def plex_callback():
    """Handle the Plex OAuth callback."""
    auth_code = request.args.get('code')
    state = request.args.get('state')

    if not state or state != session.get('oauth_state'):
        return jsonify({'error': 'Invalid state parameter'}), 400

    try:
        headers = {
            'Accept': 'application/json',
            'X-Plex-Client-Identifier': PLEX_CLIENT_ID,
            'X-Plex-Product': 'Plex Portal',
        }
        response = requests.get(
            f"{PLEX_API_URL}/user",
            headers=headers,
            params={'X-Plex-Token': auth_code},
            timeout=10,
        )
        if response.status_code != 200:
            return jsonify({'error': 'Failed to authenticate with Plex'}), 401

        user_data = response.json()
        session['user'] = {
            'id': user_data.get('id'),
            'username': user_data.get('username'),
            'email': user_data.get('email'),
            'plex_token': auth_code,
        }
        return redirect('/')
    except Exception as e:
        return jsonify({'error': f'Authentication error: {str(e)}'}), 500


@auth_bp.route('/logout', methods=['GET'])
def logout():
    session.clear()
    return redirect('/')


@auth_bp.route('/user', methods=['GET'])
def get_user():
    if 'user' not in session:
        return jsonify({'authenticated': False})
    return jsonify({'authenticated': True, 'user': session['user']})


# ---------------------------------------------------------------------------
# Overseerr proxy
# ---------------------------------------------------------------------------

@auth_bp.route('/overseerr/search', methods=['GET'])
def search_overseerr():
    if 'user' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400

    url = _overseerr_url()
    key = _overseerr_key()
    if not url or not key:
        return jsonify({'error': 'Overseerr not configured'}), 503

    try:
        resp = requests.get(
            f"{url}/api/v1/search",
            headers={'X-Api-Key': key},
            params={'query': query, 'mediaType': request.args.get('type', 'movie')},
            timeout=10,
        )
        if resp.status_code != 200:
            return jsonify({'error': f'Overseerr error: {resp.status_code}'}), resp.status_code
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': f'Search error: {str(e)}'}), 500


@auth_bp.route('/overseerr/request', methods=['POST'])
@limiter.limit("30 per hour")
def request_media():
    if 'user' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.json or {}
    if 'mediaId' not in data or 'mediaType' not in data:
        return jsonify({'error': 'Missing required parameters'}), 400

    url = _overseerr_url()
    key = _overseerr_key()
    if not url or not key:
        return jsonify({'error': 'Overseerr not configured'}), 503

    try:
        payload = {
            'mediaId': data['mediaId'],
            'mediaType': data['mediaType'],
            'userId': session['user']['id'],
            'seasons': data.get('seasons', []),
            'is4k': data.get('is4k', False),
        }
        resp = requests.post(
            f"{url}/api/v1/request",
            headers={'X-Api-Key': key, 'Content-Type': 'application/json'},
            json=payload,
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            return jsonify({'error': f'Overseerr error: {resp.status_code}'}), resp.status_code
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': f'Request error: {str(e)}'}), 500


@auth_bp.route('/overseerr/requests', methods=['GET'])
def get_requests():
    if 'user' not in session:
        return jsonify({'error': 'Authentication required'}), 401

    url = _overseerr_url()
    key = _overseerr_key()
    if not url or not key:
        return jsonify({'error': 'Overseerr not configured'}), 503

    try:
        resp = requests.get(
            f"{url}/api/v1/request",
            headers={'X-Api-Key': key},
            params={'take': 20, 'skip': 0, 'sort': 'created', 'filter': 'all'},
            timeout=10,
        )
        if resp.status_code != 200:
            return jsonify({'error': f'Overseerr error: {resp.status_code}'}), resp.status_code
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({'error': f'Error getting requests: {str(e)}'}), 500
