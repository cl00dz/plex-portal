from flask import Blueprint, jsonify, request, render_template
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re

invite_bp = Blueprint('invite', __name__)

# Email configuration - would be stored in environment variables in production
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
SMTP_USERNAME = os.environ.get('SMTP_USERNAME', 'your-email@gmail.com')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', 'your-app-password')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'plex-admin@example.com')

@invite_bp.route('/request-invite', methods=['GET'])
def request_invite_form():
    """
    Render the invite request form page.
    """
    return render_template('request_invite.html')

@invite_bp.route('/submit-invite-request', methods=['POST'])
def submit_invite_request():
    """
    Process an invite request submission and send automated emails.
    """
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['name', 'email', 'reason']
        for field in required_fields:
            if field not in data or not data[field].strip():
                return jsonify({
                    'success': False,
                    'message': f'Missing required field: {field}'
                }), 400
        
        # Validate email format
        email = data['email']
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return jsonify({
                'success': False,
                'message': 'Invalid email format'
            }), 400
        
        # Store the request in a database or file
        # For simplicity, we'll just store in a JSON file here
        # In production, you would use a proper database
        request_data = {
            'name': data['name'],
            'email': data['email'],
            'reason': data['reason'],
            'device': data.get('device', 'Not specified'),
            'experience': data.get('experience', 'Not specified'),
            'timestamp': request.json.get('timestamp', '')
        }
        
        save_request_to_file(request_data)
        
        # Send confirmation email to the user
        send_confirmation_email(request_data)
        
        # Send notification email to the admin
        send_admin_notification(request_data)
        
        return jsonify({
            'success': True,
            'message': 'Your invite request has been submitted successfully. Please check your email for confirmation.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error processing request: {str(e)}'
        }), 500

def save_request_to_file(request_data):
    """
    Save the invite request to a JSON file.
    In production, this would be replaced with a database operation.
    """
    requests_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    os.makedirs(requests_dir, exist_ok=True)
    
    requests_file = os.path.join(requests_dir, 'invite_requests.json')
    
    # Load existing requests
    existing_requests = []
    if os.path.exists(requests_file):
        try:
            with open(requests_file, 'r') as f:
                existing_requests = json.load(f)
        except json.JSONDecodeError:
            existing_requests = []
    
    # Add new request
    existing_requests.append(request_data)
    
    # Save updated requests
    with open(requests_file, 'w') as f:
        json.dump(existing_requests, f, indent=2)

def send_confirmation_email(request_data):
    """
    Send a confirmation email to the user who requested an invite.
    """
    subject = "Plex Server Invite Request Received"
    
    # Create a more personalized and friendly email body
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
            <h2 style="color: #E5A00D;">Thank You for Your Plex Server Invite Request!</h2>
            
            <p>Hello {request_data['name']},</p>
            
            <p>We've received your request to join our Plex server. Thank you for your interest!</p>
            
            <p>Here's a summary of the information you provided:</p>
            
            <ul>
                <li><strong>Name:</strong> {request_data['name']}</li>
                <li><strong>Email:</strong> {request_data['email']}</li>
                <li><strong>Device:</strong> {request_data.get('device', 'Not specified')}</li>
                <li><strong>Experience Level:</strong> {request_data.get('experience', 'Not specified')}</li>
            </ul>
            
            <p>Our Plex server administrator will review your request as soon as possible. If approved, you'll receive an official Plex invitation email with instructions on how to access the server.</p>
            
            <p>In the meantime, you might want to:</p>
            
            <ol>
                <li>Create a Plex account if you don't already have one at <a href="https://www.plex.tv/sign-up/" style="color: #E5A00D;">plex.tv</a></li>
                <li>Download the Plex app for your preferred device</li>
                <li>Check out our <a href="#" style="color: #E5A00D;">beginner's guide to Plex</a> to get familiar with how it works</li>
            </ol>
            
            <p>If you have any questions while waiting for your invite, feel free to reply to this email.</p>
            
            <p>Thank you again for your interest in joining our Plex community!</p>
            
            <p>Best regards,<br>
            The Plex Server Team</p>
            
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #777;">
                <p>This is an automated message. Please do not reply directly to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    send_email(request_data['email'], subject, body)

def send_admin_notification(request_data):
    """
    Send a notification email to the admin about the new invite request.
    """
    subject = f"New Plex Invite Request from {request_data['name']}"
    
    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 5px;">
            <h2 style="color: #E5A00D;">New Plex Server Invite Request</h2>
            
            <p>A new user has requested access to your Plex server:</p>
            
            <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Name:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{request_data['name']}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Email:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{request_data['email']}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Device:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{request_data.get('device', 'Not specified')}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Experience:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{request_data.get('experience', 'Not specified')}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Reason:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{request_data['reason']}</td>
                </tr>
            </table>
            
            <p>To approve this request, please send an invite to {request_data['email']} through your Plex server dashboard.</p>
            
            <p>All invite requests are also saved in the system for your reference.</p>
        </div>
    </body>
    </html>
    """
    
    send_email(ADMIN_EMAIL, subject, body)

def send_email(to_email, subject, body):
    """
    Send an HTML email using the configured SMTP server.
    """
    # In a development environment, we'll just log the email instead of sending it
    if os.environ.get('FLASK_ENV') == 'development':
        print(f"Would send email to {to_email}")
        print(f"Subject: {subject}")
        print(f"Body: {body}")
        return
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = SMTP_USERNAME
        msg['To'] = to_email
        
        html_part = MIMEText(body, 'html')
        msg.attach(html_part)
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        # In production, you would log this error properly
