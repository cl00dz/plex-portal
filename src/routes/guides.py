from flask import Blueprint, jsonify, request, render_template
import requests
import os

guides_bp = Blueprint('guides', __name__)

@guides_bp.route('/device-guides', methods=['GET'])
def device_guides():
    """
    Render the device guides page with comprehensive setup instructions
    for various Plex clients.
    """
    return render_template('device_guides.html')

@guides_bp.route('/plex-beginners', methods=['GET'])
def plex_beginners():
    """
    Render the beginner's guide to Plex page.
    """
    return render_template('plex_beginners.html')
