from flask import Flask, request, jsonify, session, redirect, url_for, render_template
import os
import secrets
import json
import requests
from urllib.parse import urlencode

import config
from agent.agent import SpotifyAgent
from flask_session import Session

# Global dictionary to store agent instances
agent_instances = {}

def create_app():
    app = Flask(__name__, 
                static_folder="../static", 
                template_folder="../templates")
    app.secret_key = config.FLASK_SECRET_KEY

    # Configure server-side session
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    Session(app)
    
    @app.route('/')
    def index():
        """Serve the main page"""
        return render_template('index.html')
    
    @app.route('/api/status')
    def get_status():
        """Check authentication status"""
        if 'spotify_token' in session:
            return jsonify({"authenticated": True})
        else:
            return jsonify({"authenticated": False})
    
    @app.route('/api/login')
    def login():
        """Start Spotify OAuth flow"""
        # Generate state parameter for CSRF protection
        state = secrets.token_hex(16)
        session['oauth_state'] = state
        
        # Prepare authorization URL parameters
        auth_params = {
            'client_id': config.SPOTIFY_CLIENT_ID,
            'response_type': 'code',
            'redirect_uri': config.SPOTIFY_REDIRECT_URI,
            'state': state,
            'scope': ' '.join([
                'user-read-playback-state',
                'user-modify-playback-state',
                'playlist-read-private',
                'playlist-modify-private',
                'playlist-modify-public'
            ])
        }
        
        # Construct the authorization URL
        auth_url = f'https://accounts.spotify.com/authorize?{urlencode(auth_params)}'
        
        return jsonify({"auth_url": auth_url})
    
    @app.route('/callback')
    def callback():
        """Handle the OAuth callback from Spotify"""
        global agent_instances
        
        # Verify state parameter to prevent CSRF
        state = request.args.get('state')
        if state != session.get('oauth_state'):
            return jsonify({"error": "State mismatch. Possible CSRF attack."}), 400
        
        # Check for error
        error = request.args.get('error')
        if error:
            return jsonify({"error": error}), 400
        
        # Exchange authorization code for tokens
        code = request.args.get('code')
        if not code:
            return jsonify({"error": "No authorization code provided"}), 400
        
        # Exchange the authorization code for tokens
        token_url = 'https://accounts.spotify.com/api/token'
        payload = {
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': config.SPOTIFY_REDIRECT_URI,
            'client_id': config.SPOTIFY_CLIENT_ID,
            'client_secret': config.SPOTIFY_CLIENT_SECRET
        }
        
        try:
            response = requests.post(token_url, data=payload)
            response.raise_for_status()
            tokens = response.json()
            
            # Store tokens in session
            session['spotify_token'] = tokens['access_token']
            session['spotify_refresh_token'] = tokens.get('refresh_token')
            session['spotify_token_expiry'] = tokens['expires_in']
            
            # Create a unique ID for this agent instance
            agent_id = secrets.token_hex(8)
            session['agent_id'] = agent_id
            
            # Create a new agent instance
            agent_instances[agent_id] = SpotifyAgent(
                openai_api_key=config.OPENAI_API_KEY,
                spotify_credentials={
                    'client_id': config.SPOTIFY_CLIENT_ID,
                    'client_secret': config.SPOTIFY_CLIENT_SECRET,
                    'redirect_uri': config.SPOTIFY_REDIRECT_URI,
                    'token': json.dumps(tokens)
                },
                spotify_mcp_path=config.SPOTIFY_MCP_PATH
            )
            
            # Redirect to the main page
            return redirect(url_for('index'))
            
        except requests.exceptions.RequestException as e:
            return jsonify({"error": f"Error exchanging authorization code: {str(e)}"}), 400
    
    @app.route('/api/request', methods=['POST'])
    def process_request():
        """Process a user request through the agent"""
        global agent_instances
        
        # Check if user is authenticated
        if 'agent_id' not in session or 'spotify_token' not in session:
            return jsonify({"error": "Not authenticated"}), 401
        
        # Get the agent instance
        agent_id = session['agent_id']
        if agent_id not in agent_instances:
            return jsonify({"error": "Agent not found"}), 404
        
        # Get the request data
        data = request.json
        if not data or 'request' not in data:
            return jsonify({"error": "No request provided"}), 400
        
        # Process the request
        agent = agent_instances[agent_id]
        try:
            result = agent.process_request(data['request'])
            return jsonify(result)
        except Exception as e:
            return jsonify({"error": f"Error processing request: {str(e)}"}), 500
    
    @app.route('/api/logout')
    def logout():
        """Log out the user"""
        global agent_instances
        
        # Clean up the agent instance
        if 'agent_id' in session:
            agent_id = session['agent_id']
            if agent_id in agent_instances:
                agent_instances[agent_id].cleanup()
                del agent_instances[agent_id]
        
        # Clear the session
        session.clear()
        
        return jsonify({"success": True})
    
    return app