from flask import Blueprint, jsonify, request, redirect, url_for, session, current_app
from flask_login import login_required, login_user, logout_user, current_user
import requests
import os
import json
import uuid
from urllib.parse import urlencode

auth_bp = Blueprint('auth', __name__)

# Overseerr and Plex configuration
# These would be stored in environment variables or a config file in production
OVERSEERR_URL = os.environ.get('OVERSEERR_URL', 'http://localhost:5055')
OVERSEERR_API_KEY = os.environ.get('OVERSEERR_API_KEY', '')
PLEX_CLIENT_ID = os.environ.get('PLEX_CLIENT_ID', 'PlexPortal')
PLEX_OAUTH_URL = 'https://app.plex.tv/auth'
PLEX_API_URL = 'https://plex.tv/api/v2'

@auth_bp.route('/login', methods=['GET'])
def login():
    """
    Initiate the Plex OAuth login flow.
    Redirects the user to the Plex authentication page.
    """
    # Generate a random state token to prevent CSRF
    state = str(uuid.uuid4())
    session['oauth_state'] = state
    
    # Redirect to Plex OAuth
    params = {
        'clientID': PLEX_CLIENT_ID,
        'code': state,
        'context[device][product]': 'Plex Portal',
        'context[device][environment]': 'Web',
        'context[device][layout]': 'desktop',
        'context[device][platform]': 'Web',
        'forwardUrl': url_for('auth.plex_callback', _external=True),
    }
    
    auth_url = f"{PLEX_OAUTH_URL}#!{urlencode(params)}"
    return redirect(auth_url)

@auth_bp.route('/callback', methods=['GET'])
def plex_callback():
    """
    Handle the callback from Plex OAuth.
    Exchanges the auth code for a token and logs the user in.
    """
    auth_code = request.args.get('code')
    state = request.args.get('state')
    
    # Verify state to prevent CSRF
    if not state or state != session.get('oauth_state'):
        return jsonify({'error': 'Invalid state parameter'}), 400
    
    # Exchange auth code for token
    try:
        # This is a simplified example - in production, you'd make a proper token exchange
        # For Plex, the auth flow is a bit different than standard OAuth
        headers = {
            'Accept': 'application/json',
            'X-Plex-Client-Identifier': PLEX_CLIENT_ID,
            'X-Plex-Product': 'Plex Portal',
        }
        
        # Get user info from Plex
        response = requests.get(
            f"{PLEX_API_URL}/user",
            headers=headers,
            params={'X-Plex-Token': auth_code}
        )
        
        if response.status_code != 200:
            return jsonify({'error': 'Failed to authenticate with Plex'}), 401
        
        user_data = response.json()
        
        # Here you would typically:
        # 1. Check if the user exists in your database
        # 2. If not, create a new user
        # 3. Log the user in
        
        # For this example, we'll just store the user info in the session
        session['user'] = {
            'id': user_data.get('id'),
            'username': user_data.get('username'),
            'email': user_data.get('email'),
            'plex_token': auth_code,
        }
        
        # Redirect to the frontend dashboard
        return redirect('/')
        
    except Exception as e:
        return jsonify({'error': f'Authentication error: {str(e)}'}), 500

@auth_bp.route('/logout', methods=['GET'])
def logout():
    """
    Log the user out by clearing their session.
    """
    session.clear()
    return redirect('/')

@auth_bp.route('/user', methods=['GET'])
def get_user():
    """
    Get the current user's information.
    """
    if 'user' not in session:
        return jsonify({'authenticated': False})
    
    return jsonify({
        'authenticated': True,
        'user': session['user']
    })

# Overseerr integration routes

@auth_bp.route('/overseerr/search', methods=['GET'])
def search_overseerr():
    """
    Search for media on Overseerr.
    """
    if 'user' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    query = request.args.get('query', '')
    media_type = request.args.get('type', 'movie')  # movie, tv, person
    
    if not query:
        return jsonify({'error': 'Query parameter is required'}), 400
    
    try:
        headers = {
            'X-Api-Key': OVERSEERR_API_KEY,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{OVERSEERR_URL}/api/v1/search",
            headers=headers,
            params={'query': query, 'mediaType': media_type}
        )
        
        if response.status_code != 200:
            return jsonify({'error': f'Overseerr API error: {response.status_code}'}), response.status_code
        
        return jsonify(response.json())
        
    except Exception as e:
        return jsonify({'error': f'Error searching Overseerr: {str(e)}'}), 500

@auth_bp.route('/overseerr/request', methods=['POST'])
def request_media():
    """
    Submit a media request to Overseerr.
    """
    if 'user' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    data = request.json
    
    if not data or 'mediaId' not in data or 'mediaType' not in data:
        return jsonify({'error': 'Missing required parameters'}), 400
    
    try:
        headers = {
            'X-Api-Key': OVERSEERR_API_KEY,
            'Content-Type': 'application/json'
        }
        
        # Prepare request payload
        payload = {
            'mediaId': data['mediaId'],
            'mediaType': data['mediaType'],
            'userId': session['user']['id'],
            'seasons': data.get('seasons', []),  # For TV shows
            'is4k': data.get('is4k', False)
        }
        
        response = requests.post(
            f"{OVERSEERR_URL}/api/v1/request",
            headers=headers,
            json=payload
        )
        
        if response.status_code not in [200, 201]:
            return jsonify({'error': f'Overseerr API error: {response.status_code}'}), response.status_code
        
        return jsonify(response.json())
        
    except Exception as e:
        return jsonify({'error': f'Error submitting request to Overseerr: {str(e)}'}), 500

@auth_bp.route('/overseerr/requests', methods=['GET'])
def get_requests():
    """
    Get the current user's requests from Overseerr.
    """
    if 'user' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    
    try:
        headers = {
            'X-Api-Key': OVERSEERR_API_KEY,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{OVERSEERR_URL}/api/v1/request?take=20&skip=0&sort=created&filter=all",
            headers=headers
        )
        
        if response.status_code != 200:
            return jsonify({'error': f'Overseerr API error: {response.status_code}'}), response.status_code
        
        return jsonify(response.json())
        
    except Exception as e:
        return jsonify({'error': f'Error getting requests from Overseerr: {str(e)}'}), 500
