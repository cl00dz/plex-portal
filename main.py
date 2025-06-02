import os
import sys
import json
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, redirect, url_for
from src.models.user import db
from src.routes.user import user_bp
from src.routes.plex import plex_bp
from src.routes.auth import auth_bp
from src.routes.guides import guides_bp
from src.routes.setup import setup_bp

# Load configuration from file if it exists
def load_config_from_file():
    config_file = os.path.join(os.path.dirname(__file__), 'data', 'config.json')
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                
            # Set environment variables from config
            for key, value in config.items():
                if key.upper() in ['PLEX_SERVER_URL', 'PLEX_TOKEN', 'OVERSEERR_URL', 'OVERSEERR_API_KEY', 
                                  'SITE_NAME', 'ADMIN_EMAIL']:
                    os.environ[key.upper()] = value
                    
            return True
        except Exception as e:
            print(f"Error loading config: {str(e)}")
    
    return False

# Check if setup is complete
def is_setup_complete():
    setup_file = os.path.join(os.path.dirname(__file__), 'data', 'setup_complete.json')
    return os.path.exists(setup_file)

# Create data directory if it doesn't exist
data_dir = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(data_dir, exist_ok=True)

# Load config from file
load_config_from_file()

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'asdf#FGSgvasgf$5$WGT')

# Register all blueprints
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(plex_bp, url_prefix='/api/plex')
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(guides_bp, url_prefix='/api/guides')
app.register_blueprint(setup_bp, url_prefix='/api/setup')

# Database configuration
db_host = os.environ.get('DB_HOST', 'localhost')
db_port = os.environ.get('DB_PORT', '3306')
db_user = os.environ.get('DB_USERNAME', 'root')
db_pass = os.environ.get('DB_PASSWORD', 'password')
db_name = os.environ.get('DB_NAME', 'mydb')

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
with app.app_context():
    db.create_all()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    # Redirect to setup if not completed
    if not is_setup_complete() and not path.startswith('api/setup'):
        return redirect('/api/setup/setup')
    
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
