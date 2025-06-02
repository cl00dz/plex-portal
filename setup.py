from flask import Blueprint, jsonify, request, render_template
import os
import json

setup_bp = Blueprint('setup', __name__)

@setup_bp.route('/setup', methods=['GET'])
def setup_form():
    """
    Render the setup form page for initial configuration.
    """
    # Check if setup has already been completed
    setup_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'setup_complete.json')
    if os.path.exists(setup_file):
        return render_template('setup_complete.html')
    
    return render_template('setup.html')

@setup_bp.route('/setup/save', methods=['POST'])
def save_setup():
    """
    Save the setup configuration and create the setup_complete file.
    """
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['plex_server_url', 'plex_token', 'overseerr_url', 'overseerr_api_key']
        for field in required_fields:
            if field not in data or not data[field].strip():
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Create data directory if it doesn't exist
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        # Save configuration to file
        config_file = os.path.join(data_dir, 'config.json')
        with open(config_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        # Create setup_complete file
        setup_file = os.path.join(data_dir, 'setup_complete.json')
        with open(setup_file, 'w') as f:
            json.dump({'setup_completed': True, 'timestamp': data.get('timestamp', '')}, f, indent=2)
        
        # Update environment variables for the current process
        os.environ['PLEX_SERVER_URL'] = data['plex_server_url']
        os.environ['PLEX_TOKEN'] = data['plex_token']
        os.environ['OVERSEERR_URL'] = data['overseerr_url']
        os.environ['OVERSEERR_API_KEY'] = data['overseerr_api_key']
        
        return jsonify({
            'success': True,
            'message': 'Setup completed successfully. Please restart the application for changes to take effect.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error saving setup: {str(e)}'
        }), 500

@setup_bp.route('/setup/status', methods=['GET'])
def setup_status():
    """
    Check if setup has been completed.
    """
    setup_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'setup_complete.json')
    if os.path.exists(setup_file):
        return jsonify({
            'setup_completed': True
        })
    else:
        return jsonify({
            'setup_completed': False
        })
