import os
import sys
import json
import secrets as _secrets
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, redirect, jsonify
from src.models.user import db
from src.routes.user import user_bp
from src.routes.plex import plex_bp
from src.routes.auth import auth_bp
from src.routes.guides import guides_bp
from src.routes.setup import setup_bp
from src.extensions import limiter

# ---------------------------------------------------------------------------
# Data directory (persistent across restarts via Docker volume)
# ---------------------------------------------------------------------------
data_dir = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(data_dir, exist_ok=True)

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def load_config_from_file():
    """Load saved setup values into environment variables."""
    config_file = os.path.join(data_dir, 'config.json')
    if not os.path.exists(config_file):
        return False
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        allowed = {'PLEX_SERVER_URL', 'PLEX_TOKEN', 'OVERSEERR_URL',
                   'OVERSEERR_API_KEY', 'SITE_NAME', 'ADMIN_EMAIL'}
        for key, value in config.items():
            if key.upper() in allowed and value:
                os.environ[key.upper()] = value
        return True
    except Exception as e:
        print(f"Warning: Could not load config file: {e}")
    return False


def is_setup_complete():
    setup_file = os.path.join(data_dir, 'setup_complete.json')
    return os.path.exists(setup_file)


def get_or_create_secret_key():
    """
    Return a persistent SECRET_KEY.
    Priority: SECRET_KEY env var → persisted key file → freshly generated key.
    A generated key is saved to the data volume so sessions survive restarts.
    """
    env_key = os.environ.get('SECRET_KEY', '')
    placeholders = {'change_this_in_production', 'asdf#FGSgvasgf$5$WGT', ''}
    if env_key not in placeholders:
        return env_key

    key_file = os.path.join(data_dir, 'secret_key')
    if os.path.exists(key_file):
        with open(key_file, 'r') as f:
            key = f.read().strip()
        if key:
            return key

    key = _secrets.token_hex(32)
    try:
        with open(key_file, 'w') as f:
            f.write(key)
        os.chmod(key_file, 0o600)
    except Exception as e:
        print(f"Warning: Could not persist secret key: {e}")
    return key


# ---------------------------------------------------------------------------
# Load persisted config before creating the app (so blueprints can read envs)
# ---------------------------------------------------------------------------
load_config_from_file()

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
_repo_root = os.path.dirname(os.path.dirname(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(_repo_root, 'static'),
    template_folder=os.path.join(_repo_root, 'templates'),
)

# Security-hardened session & app config
app.config.update(
    SECRET_KEY=get_or_create_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=3600,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)

# ---------------------------------------------------------------------------
# Database  (SQLite by default; MySQL when DB_HOST is set)
# ---------------------------------------------------------------------------
db_host = os.environ.get('DB_HOST', '')
if db_host:
    db_user = os.environ.get('DB_USERNAME', 'plex_portal')
    db_pass = os.environ.get('DB_PASSWORD', '')
    db_port = os.environ.get('DB_PORT', '3306')
    db_name = os.environ.get('DB_NAME', 'plex_portal_db')
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    )
else:
    db_path = os.path.join(data_dir, 'plex_portal.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"

db.init_app(app)
with app.app_context():
    db.create_all()

# ---------------------------------------------------------------------------
# Extensions
# ---------------------------------------------------------------------------
limiter.init_app(app)

# ---------------------------------------------------------------------------
# Blueprints
# ---------------------------------------------------------------------------
app.register_blueprint(user_bp,  url_prefix='/api')
app.register_blueprint(plex_bp,  url_prefix='/api/plex')
app.register_blueprint(auth_bp,  url_prefix='/api/auth')
app.register_blueprint(guides_bp, url_prefix='/api/guides')
app.register_blueprint(setup_bp,  url_prefix='/api/setup')

# ---------------------------------------------------------------------------
# Security headers on every response
# ---------------------------------------------------------------------------
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    # Remove Flask/Werkzeug server banner
    response.headers.pop('Server', None)
    return response

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'setup_complete': is_setup_complete()})

# ---------------------------------------------------------------------------
# SPA catch-all route
# ---------------------------------------------------------------------------
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    # Gate everything behind the setup wizard on first run
    if not is_setup_complete() and not path.startswith('api/setup'):
        return redirect('/api/setup/setup')

    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    if path and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)

    index_path = os.path.join(static_folder_path, 'index.html')
    if os.path.exists(index_path):
        return send_from_directory(static_folder_path, 'index.html')
    return "index.html not found", 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
