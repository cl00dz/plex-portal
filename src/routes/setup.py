import os
import json
import smtplib
import ssl
import secrets
import requests
from flask import Blueprint, jsonify, request, render_template
from src.extensions import limiter

setup_bp = Blueprint('setup', __name__)

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')


def _data_path(*parts):
    return os.path.join(_DATA_DIR, *parts)


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@setup_bp.route('/setup', methods=['GET'])
def setup_form():
    if os.path.exists(_data_path('setup_complete.json')):
        return render_template('setup_complete.html')
    return render_template('setup.html')


# ---------------------------------------------------------------------------
# Connection testers  (called from the wizard's "Test Connection" buttons)
# ---------------------------------------------------------------------------

@setup_bp.route('/test-plex', methods=['POST'])
@limiter.limit("20 per minute")
def test_plex():
    """Verify that a Plex server URL + token are reachable."""
    data = request.json or {}
    url = data.get('plex_server_url', '').strip().rstrip('/')
    token = data.get('plex_token', '').strip()

    if not url or not token:
        return jsonify({'success': False, 'message': 'Server URL and token are required'})

    try:
        resp = requests.get(
            f"{url}/identity",
            headers={'X-Plex-Token': token, 'Accept': 'application/json'},
            timeout=6,
        )
        if resp.status_code == 200:
            name = resp.json().get('MediaContainer', {}).get('friendlyName', 'your Plex server')
            return jsonify({'success': True, 'message': f'Connected to {name}!'})
        if resp.status_code == 401:
            return jsonify({'success': False, 'message': 'Invalid token — double-check your Plex Token'})
        return jsonify({'success': False, 'message': f'Server returned error {resp.status_code}'})
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False,
                        'message': "Can't reach that address — check the URL and that Plex is running"})
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'message': 'Connection timed out — server may be slow or unreachable'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Connection failed: {str(e)}'})


@setup_bp.route('/test-overseerr', methods=['POST'])
@limiter.limit("20 per minute")
def test_overseerr():
    """Verify that an Overseerr URL + API key are reachable."""
    data = request.json or {}
    url = data.get('overseerr_url', '').strip().rstrip('/')
    api_key = data.get('overseerr_api_key', '').strip()

    if not url or not api_key:
        return jsonify({'success': False, 'message': 'Overseerr URL and API key are required'})

    try:
        resp = requests.get(
            f"{url}/api/v1/settings/main",
            headers={'X-Api-Key': api_key},
            timeout=6,
        )
        if resp.status_code == 200:
            return jsonify({'success': True, 'message': 'Connected to Overseerr successfully!'})
        if resp.status_code in (401, 403):
            return jsonify({'success': False, 'message': 'Invalid API key — check Overseerr → Settings → General'})
        return jsonify({'success': False, 'message': f'Overseerr returned error {resp.status_code}'})
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False,
                        'message': "Can't reach Overseerr — check the URL and that it is running"})
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'message': 'Connection timed out'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Connection failed: {str(e)}'})


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

@setup_bp.route('/save', methods=['POST'])
@limiter.limit("10 per minute")
def save_setup():
    """Persist the wizard configuration and mark setup as complete."""
    try:
        data = request.json or {}

        # Plex fields are required; Overseerr is optional
        for field in ('plex_server_url', 'plex_token'):
            if not data.get(field, '').strip():
                return jsonify({'success': False, 'message': f'Missing required field: {field}'}), 400

        os.makedirs(_DATA_DIR, exist_ok=True)

        # Persist configuration
        with open(_data_path('config.json'), 'w') as f:
            json.dump(data, f, indent=2)

        # Mark setup complete
        with open(_data_path('setup_complete.json'), 'w') as f:
            json.dump({'setup_completed': True, 'timestamp': data.get('timestamp', '')}, f, indent=2)

        # Update live environment so the running process picks up changes immediately
        env_map = {
            'plex_server_url':          'PLEX_SERVER_URL',
            'plex_token':               'PLEX_TOKEN',
            'overseerr_url':            'OVERSEERR_URL',
            'overseerr_api_key':        'OVERSEERR_API_KEY',
            'site_name':                'SITE_NAME',
            'smtp_host':                'SMTP_HOST',
            'smtp_port':                'SMTP_PORT',
            'smtp_username':            'SMTP_USERNAME',
            'smtp_password':            'SMTP_PASSWORD',
            'smtp_from_name':           'SMTP_FROM_NAME',
            'smtp_from_email':          'SMTP_FROM_EMAIL',
            'newsletter_webhook_secret': 'NEWSLETTER_WEBHOOK_SECRET',
        }
        for field, env_key in env_map.items():
            val = data.get(field, '').strip()
            if val:
                os.environ[env_key] = val

        return jsonify({'success': True, 'message': 'Setup completed successfully!'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error saving setup: {str(e)}'}), 500


# ---------------------------------------------------------------------------
# Test SMTP connection (called from setup wizard email step)
# ---------------------------------------------------------------------------

@setup_bp.route('/test-email', methods=['POST'])
@limiter.limit("5 per minute")
def test_email():
    """Verify SMTP credentials by opening a TLS connection."""
    data     = request.json or {}
    host     = data.get('smtp_host', '').strip()
    port     = int(data.get('smtp_port', 587) or 587)
    username = data.get('smtp_username', '').strip()
    password = data.get('smtp_password', '').strip()

    if not host or not username or not password:
        return jsonify({'success': False,
                        'message': 'Host, username, and password are all required'})
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.login(username, password)
        return jsonify({'success': True, 'message': f'Connected to {host}:{port} — credentials accepted!'})
    except smtplib.SMTPAuthenticationError:
        return jsonify({'success': False,
                        'message': 'Authentication failed — check username and password'})
    except (smtplib.SMTPConnectError, ConnectionRefusedError, OSError) as e:
        return jsonify({'success': False,
                        'message': f"Cannot connect to {host}:{port} — {e}"})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Test failed: {str(e)}'})


# ---------------------------------------------------------------------------
# Generate a webhook secret (called from setup wizard)
# ---------------------------------------------------------------------------

@setup_bp.route('/generate-webhook-secret', methods=['POST'])
def generate_webhook_secret():
    return jsonify({'secret': secrets.token_urlsafe(24)})


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@setup_bp.route('/status', methods=['GET'])
def setup_status():
    return jsonify({'setup_completed': os.path.exists(_data_path('setup_complete.json'))})
