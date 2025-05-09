from flask import Flask, request, jsonify, session, redirect, url_for, render_template 
import os
import secrets
import json
import requests
import time
from urllib.parse import urlencode
from flask_session import Session

import config
from agent.agent import SpotifyAgent

agent_instances = {}

def create_app():
    '''
    Creates the Flask application.
    '''
    app = Flask(__name__, static_folder="../static", template_folder="../templates")
    app.secret_key = config.FLASK_SECRET_KEY
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600 * 2
    app.config['SESSION_FILE_DIR'] = './flask_session/'
    app.config['SESSION_USE_SIGNER'] = True
    Session(app)
    os.makedirs('./flask_session', exist_ok=True)

    def get_agent_instance():
        '''
        Gets the agent instance from the session.
        '''
        if 'agent_id' not in session or 'spotify_token_json' not in session:
            print(f"get_agent failed: agent_id:{'agent_id' in session}, token:{'spotify_token_json' in session}")
            return None, "Not authenticated"
        agent_id = session['agent_id']
        if agent_id in agent_instances: return agent_instances[agent_id], None
        print(f"Agent {agent_id} not in memory, recreating...")
        try:
            spotify_creds = { 'client_id': config.SPOTIFY_CLIENT_ID, 'client_secret': config.SPOTIFY_CLIENT_SECRET,
                              'redirect_uri': config.SPOTIFY_REDIRECT_URI, 'token': session.get('spotify_token_json') }
            if not spotify_creds.get('token'):
                print("Error: Token missing in session."); session.clear(); return None, "Auth token missing."
            agent = SpotifyAgent(openai_api_key=config.OPENAI_API_KEY, spotify_credentials=spotify_creds)
            if not agent.client or not agent.client.sp:
                 print(f"Error: Failed Spotify client init for {agent_id}."); session.clear(); return None, "Re-auth failed."
            agent_instances[agent_id] = agent; print(f"Recreated agent: {agent_id}"); return agent, None
        except Exception as e:
            print(f"Error recreating agent {agent_id}: {str(e)}"); import traceback; traceback.print_exc()
            session.clear(); return None, "Error recreating session."

    @app.route('/')
    def index(): return render_template('index.html')

    @app.route('/api/status')
    def get_status():
        agent, error = get_agent_instance()
        return jsonify({"authenticated": bool(agent)})

    @app.route('/api/login')
    def login():
        '''
        Logs in the user.
        '''
        state = secrets.token_hex(16); session['oauth_state'] = state
        auth_params = { 'client_id': config.SPOTIFY_CLIENT_ID, 'response_type': 'code', 'redirect_uri': config.SPOTIFY_REDIRECT_URI,
                        'state': state, 'scope': ' '.join([ 'user-read-playback-state', 'user-modify-playback-state',
                        'playlist-read-private', 'playlist-modify-private', 'playlist-modify-public' ]) }
        auth_url = f'https://accounts.spotify.com/authorize?{urlencode(auth_params)}'; return jsonify({"auth_url": auth_url})

    @app.route('/callback')
    def callback():
        '''
        Callback for the Spotify OAuth flow.
        '''
        state = request.args.get('state'); error = request.args.get('error'); code = request.args.get('code')
        if state != session.get('oauth_state'): return jsonify({"error": "State mismatch."}), 400
        if error: return jsonify({"error": f"Spotify OAuth Error: {error}"}), 400
        if not code: return jsonify({"error": "No authorization code provided"}), 400
        token_url = 'https://accounts.spotify.com/api/token'
        payload = { 'grant_type': 'authorization_code', 'code': code, 'redirect_uri': config.SPOTIFY_REDIRECT_URI,
                    'client_id': config.SPOTIFY_CLIENT_ID, 'client_secret': config.SPOTIFY_CLIENT_SECRET }
        try:
            response = requests.post(token_url, data=payload); response.raise_for_status(); tokens = response.json()
            if 'expires_in' in tokens and 'expires_at' not in tokens: tokens['expires_at'] = int(time.time()) + tokens['expires_in']
            session['spotify_token_json'] = json.dumps(tokens); agent_id = secrets.token_hex(8); session['agent_id'] = agent_id
            agent = SpotifyAgent( openai_api_key=config.OPENAI_API_KEY,
                                  spotify_credentials={ 'client_id': config.SPOTIFY_CLIENT_ID, 'client_secret': config.SPOTIFY_CLIENT_SECRET,
                                                        'redirect_uri': config.SPOTIFY_REDIRECT_URI, 'token': session['spotify_token_json'] })
            if not agent.client or not agent.client.sp: raise Exception("Failed to initialize Spotify client after callback.")
            agent_instances[agent_id] = agent; print(f"Created agent {agent_id} after callback."); return redirect(url_for('index'))
        except requests.exceptions.RequestException as e: print(f"Token exchange error: {e}"); return jsonify({"error": f"Spotify token error: {e}"}), 500
        except Exception as e: print(f"Callback agent creation error: {e}"); import traceback; traceback.print_exc(); return jsonify({"error": f"Login setup error: {e}"}), 500

    @app.route('/api/request', methods=['POST'])
    def process_general_request():
        agent, error = get_agent_instance()
        if not agent: return jsonify({"success": False, "error": error}), 401
        data = request.json
        if not data or 'request' not in data: return jsonify({"success": False, "error": "No request prompt"}), 400
        try: result = agent.process_request(data['request']); return jsonify(result)
        except Exception as e: print(f"Agent request error: {e}"); import traceback; traceback.print_exc(); return jsonify({"success": False, "error": f"Server error: {e}"}), 500

    @app.route('/api/playlist/remove_track', methods=['POST'])
    def remove_playlist_track():
        agent, error = get_agent_instance()
        if not agent: return jsonify({"success": False, "error": error}), 401
        data = request.json; playlist_id = data.get('playlist_id'); track_uri = data.get('track_uri')
        if not playlist_id or not track_uri: return jsonify({"success": False, "error": "Missing playlist_id or track_uri"}), 400
        try:
            result = agent.client.remove_track_from_playlist(playlist_id, track_uri)
            if result.get('error'): return jsonify({"success": False, "error": result.get('error', 'Failed to remove track')}), 500
            else: return jsonify({"success": True, "new_track_count": result.get("new_track_count")})
        except Exception as e: print(f"Track removal error: {e}"); import traceback; traceback.print_exc(); return jsonify({"success": False, "error": f"Server error: {e}"}), 500

    @app.route('/api/playlist/items/<string:playlist_id>', methods=['GET'])
    def get_playlist_items(playlist_id):
        """Fetches all items for a given playlist ID."""
        agent, error = get_agent_instance()
        if not agent:
            return jsonify({"success": False, "error": error}), 401 # Unauthorized

        if not playlist_id:
             return jsonify({"success": False, "error": "Missing playlist_id"}), 400 # Bad request

        try:
            # Call the client method directly
            result = agent.client.get_all_playlist_items(playlist_id)
            if result.get('error'):
                 # If the client method returned an error dictionary
                 return jsonify({"success": False, "error": result.get('error', 'Failed to fetch playlist items')}), 500
            else:
                # Return the list of tracks
                return jsonify({"success": True, "tracks": result.get("tracks", [])})

        except Exception as e:
            print(f"Error getting all playlist items: {str(e)}")
            import traceback; traceback.print_exc()
            return jsonify({"success": False, "error": f"Server error fetching playlist items: {str(e)}"}), 500


    @app.route('/api/logout')
    def logout():
        if 'agent_id' in session:
            agent_id = session.pop('agent_id'); session.pop('spotify_token_json', None); session.pop('oauth_state', None)
            if agent_id in agent_instances:
                try: agent_instances[agent_id].cleanup()
                except Exception as e: print(f"Cleanup error {agent_id}: {e}")
                del agent_instances[agent_id]; print(f"Cleaned up agent {agent_id}.")
        session.clear(); return jsonify({"success": True})

    return app