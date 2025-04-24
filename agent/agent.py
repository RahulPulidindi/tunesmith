import json, os
import time
from typing import Dict, Any, List, Optional, Type
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import Tool, StructuredTool
from pydantic.v1 import BaseModel, Field
from langchain_core.messages import SystemMessage

# Pydantic models that define the expected input parameters for Spotify API interactions
class SpotifySearchSchema(BaseModel):
    query: str = Field(description="The search query for tracks, albums, or artists.")
    limit: int = Field(default=10, description="The maximum number of results to return.")

class SpotifyCreatePlaylistSchema(BaseModel):
    name: str = Field(description="The name for the new playlist.")
    description: str = Field(default="", description="The description for the new playlist.")
    track_uris: List[str] = Field(description="A list of Spotify track URIs (e.g., 'spotify:track:...') to add to the playlist.")

class SpotifyPlaybackSchema(BaseModel):
    action: str = Field(description="The playback action to perform: 'play', 'pause', 'next', 'previous'.")
    context_uri: Optional[str] = Field(default=None, description="Optional Spotify URI of the context to play (album, artist, playlist URI). Required for 'play' if not resuming.")

# Main class for handling Spotify API interactions
class SpotifyClient:
    """Client for interacting with Spotify through the spotipy library, managing authentication."""

    def __init__(self, spotify_credentials: Dict[str, str]):
        self.credentials = spotify_credentials
        self.sp: Optional[spotipy.Spotify] = None
        self.sp_oauth: Optional[SpotifyOAuth] = None
        self._authenticate()

    def _authenticate(self):
        """Set up the Spotify client with proper authentication using SpotifyOAuth for auto-refresh."""
        print("Attempting Spotify authentication...")
        try:
            # Create SpotifyOAuth manager without file caching
            # This keeps tokens in memory only during the session
            self.sp_oauth = SpotifyOAuth(
                client_id=self.credentials["client_id"],
                client_secret=self.credentials["client_secret"],
                redirect_uri=self.credentials["redirect_uri"],
                scope="user-read-playback-state user-modify-playback-state playlist-read-private playlist-modify-private playlist-modify-public",
                cache_path=None, # Use memory cache, won't persist across restarts unless session stores it
            )
            print("SpotifyOAuth object created.")

            # First try to get token from cache
            token_check = self.sp_oauth.get_cached_token()

            if token_check:
                print(f"Found cached token info via get_cached_token().") 
                self.sp = spotipy.Spotify(auth_manager=self.sp_oauth)
                print("Spotify client created successfully using cached token.")
            else:
                # If no cached token exists, try using credentials from session
                if "token" in self.credentials and self.credentials["token"]:
                    print("No cached token, attempting to use token from credentials...")
                    try:
                        token_info_from_creds = json.loads(self.credentials["token"])
                        # Create client directly with access token
                        # Note: Manual refresh may be needed when token expires
                        if 'access_token' in token_info_from_creds:
                            print("Creating Spotify client directly with access token from credentials.")
                            self.sp = spotipy.Spotify(auth=token_info_from_creds['access_token'])
                        else:
                            print("Token info from credentials missing 'access_token'.")
                            self.sp = None
                    except json.JSONDecodeError:
                        print("Could not parse token from credentials.")
                        self.sp = None
                    except Exception as e_inner:
                        print(f"Error creating client directly from credential token: {e_inner}")
                        self.sp = None
                else:
                    print("Authentication required: No cached token and no token in credentials.")
                    self.sp = None

                if self.sp:
                    print("Spotify client instance created.")
                else:
                    print("Failed to create Spotify client instance.")

        except Exception as e:
            print(f"ERROR during Spotify authentication: {str(e)}")
            import traceback
            traceback.print_exc()
            self.sp = None

    def _ensure_client(self) -> bool:
        """Checks if the Spotify client is authenticated."""
        if not self.sp:
            print("Spotify client not initialized or authentication failed previously.")
            # Try to re-authenticate if possible
            if self.sp_oauth:
                print("Attempting re-authentication...")
                try:
                    token_check = self.sp_oauth.get_access_token(check_cache=True)
                    if token_check:
                        self.sp = spotipy.Spotify(auth_manager=self.sp_oauth)
                        print("Re-authentication successful.")
                        return True
                    else:
                        print("Re-authentication failed: No valid token.")
                        return False
                except Exception as e:
                    print(f"Error during re-authentication: {e}")
                    return False
            return False
        return True

    def search_tracks(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search for tracks on Spotify and return simplified results."""
        if not self._ensure_client():
            return {"error": "Not authenticated with Spotify"}
        try:
            results = self.sp.search(q=query, type='track', limit=limit)

            # Convert full track objects to simplified format
            simplified_tracks = []
            spotify_tracks = results.get("tracks", {}).get("items", [])

            if spotify_tracks:
                for track in spotify_tracks:
                    # Keep only essential track information
                    simplified_tracks.append({
                        "name": track.get("name"),
                        "artists": [artist.get("name") for artist in track.get("artists", [])],
                        "uri": track.get("uri"),
                        "id": track.get("id")
                    })

            return {"tracks": simplified_tracks}

        except SpotifyException as e:
            print(f"Spotify API error during search: {str(e)}")
            return {"error": f"Spotify API error: {e.msg}"}
        except Exception as e:
            print(f"Error searching Spotify: {str(e)}")
            return {"error": str(e)}

    def create_playlist(self, name: str, description: str, track_uris: List[str]) -> Dict[str, Any]:
        """Create a playlist on Spotify"""
        if not self._ensure_client():
            return {"error": "Not authenticated with Spotify"}
        try:
            user_id = self.sp.current_user()["id"]
            playlist = self.sp.user_playlist_create(
                user=user_id,
                name=name,
                public=False, # Default to private
                description=description
            )
            if track_uris:
                # Add items in chunks of 100 if necessary
                for i in range(0, len(track_uris), 100):
                    self.sp.playlist_add_items(playlist["id"], track_uris[i:i+100])

            # Return essential playlist info
            updated_playlist = self.sp.playlist(playlist["id"], fields="name,description,external_urls,id,uri,tracks.total")
            return updated_playlist
        except SpotifyException as e:
            print(f"Spotify API error during playlist creation: {str(e)}")
            return {"error": f"Spotify API error: {e.msg}"}
        except Exception as e:
            print(f"Error creating playlist: {str(e)}")
            return {"error": str(e)}

    def control_playback(self, action: str, context_uri: Optional[str] = None) -> Dict[str, Any]:
        """Control Spotify playback"""
        if not self._ensure_client():
            return {"error": "Not authenticated with Spotify"}
        try:
            result = {"success": True, "action": action}
            action = action.lower()

            if action == "play":
                # Check active device first
                devices = self.sp.devices()
                active_device = next((d for d in devices['devices'] if d['is_active']), None)
                device_id = active_device['id'] if active_device else None

                if not device_id:
                     # Try to use first available device if none active
                     if devices['devices']:
                         device_id = devices['devices'][0]['id']
                         print(f"No active device found. Transferring playback to: {devices['devices'][0]['name']}")
                         self.sp.transfer_playback(device_id=device_id, force_play=False)
                         time.sleep(1) # Wait for transfer
                     else:
                         return {"error": "No available Spotify devices found."}

                if context_uri:
                    self.sp.start_playback(device_id=device_id, context_uri=context_uri)
                else:
                    # Resume current playback if no context provided
                    self.sp.start_playback(device_id=device_id)
                result["status"] = "Playback started/resumed"
            elif action == "pause":
                self.sp.pause_playback()
                result["status"] = "Playback paused"
            elif action == "next":
                self.sp.next_track()
                result["status"] = "Skipped to next track"
            elif action == "previous":
                self.sp.previous_track()
                result["status"] = "Skipped to previous track"
            else:
                return {"error": f"Unknown playback action: {action}"}

            return result
        except SpotifyException as e:
            print(f"Spotify API error during playback control: {str(e)}")
            # Give helpful error messages for common issues
            if e.http_status == 404 and "No active device found" in e.msg:
                 return {"error": "No active Spotify device found. Please start playback on a device."}
            if e.http_status == 403 and ("restricted" in e.msg or "premium" in e.msg):
                 return {"error": "Playback control failed. This action might require Spotify Premium or is restricted."}
            return {"error": f"Spotify API error: {e.msg}"}
        except Exception as e:
            print(f"Error controlling playback: {str(e)}")
            return {"error": str(e)}

    def get_current_user_profile(self) -> Dict[str, Any]:
        """Gets the current user's profile information."""
        if not self._ensure_client():
            return {"error": "Not authenticated with Spotify"}
        try:
            return self.sp.current_user()
        except SpotifyException as e:
            print(f"Spotify API error getting user profile: {str(e)}")
            return {"error": f"Spotify API error: {e.msg}"}
        except Exception as e:
            print(f"Error getting user profile: {str(e)}")
            return {"error": str(e)}


# Main agent class that combines Spotify functionality with AI capabilities
class SpotifyAgent:
    def __init__(self, openai_api_key: str, spotify_credentials: Dict[str, str]):
        self.openai_api_key = openai_api_key
        self.spotify_credentials = spotify_credentials

        # Create Spotify client instance
        self.client = SpotifyClient(spotify_credentials=self.spotify_credentials)

        # Set up OpenAI language model
        self.llm = ChatOpenAI(
            temperature=0.7,
            model="gpt-3.5-turbo-0125",
            openai_api_key=self.openai_api_key
        )

        # Create tools for Spotify interactions
        self.tools = self._create_tools()

        # Initialize conversation memory
        self.memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

        # Create the agent that will handle user requests
        self.agent_executor = self._create_agent_executor()

    def _create_tools(self) -> List[Tool]:
        """Creates tools that the agent can use to interact with Spotify"""
        tools = [
            StructuredTool.from_function(
                func=self.client.search_tracks,
                name="spotify_search_tracks",
                description="Search for tracks on Spotify based on a query string. Returns a list of tracks with details like name, artist, and URI.",
                args_schema=SpotifySearchSchema
            ),
            StructuredTool.from_function(
                func=self.client.create_playlist,
                name="spotify_create_playlist",
                description="Creates a new Spotify playlist for the current user with a given name, description, and list of track URIs. Returns details of the created playlist including its URL.",
                args_schema=SpotifyCreatePlaylistSchema
            ),
            StructuredTool.from_function(
                func=self.client.control_playback,
                name="spotify_control_playback",
                description="Controls Spotify playback. Actions: 'play', 'pause', 'next', 'previous'. 'play' can optionally take a context_uri (playlist, album, artist URI) to start playing specific content.",
                args_schema=SpotifyPlaybackSchema
            ),
            StructuredTool.from_function(
                func=self.client.get_current_user_profile,
                name="get_current_user_profile",
                description="Gets the profile information of the currently authenticated Spotify user, like display name and user ID."
            )
        ]
        return tools
    
    def _create_agent_executor(self) -> AgentExecutor:
        """Creates the AI agent that will process user requests"""

        # Define how the agent should behave and what it can do
        system_prompt = SystemMessage(content="""You are TuneSmith, a helpful AI assistant specialized in Spotify.
        Your goal is to help users create Spotify playlists based on their descriptions of mood, genre, activity, or theme.
        You can also search for tracks and control playback.
        1. Understand the user's request (e.g., "create a playlist for relaxing", "play some upbeat pop music").
        2. If creating a playlist:
           - Think step-by-step to determine suitable search queries based on the user's request.
           - Use 'spotify_search_tracks' with those queries to find relevant songs. You might need to search multiple times with varied queries.
           - Select a list of suitable track URIs from the search results (aim for 10-20 tracks unless specified otherwise).
           - Use 'spotify_create_playlist' with a fitting name (e.g., "Relaxing Vibes Playlist"), description, and the collected track URIs.
           - Inform the user the playlist has been created and provide its name or URL (if available in the tool output). Include a few sample tracks found.
        3. If searching: Use 'spotify_search_tracks' and present the findings clearly.
        4. If controlling playback: Use 'spotify_control_playback' with the correct action and context_uri if needed.
        5. If asked about the user: Use 'get_current_user_profile' to get their details.
        6. Be conversational and confirm actions taken.
        7. If the Spotify client is not authenticated (tool returns an auth error), inform the user they need to log in or there's an issue with authentication.""")

        # Set up the conversation template
        prompt = ChatPromptTemplate.from_messages([
            system_prompt,
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # Create the AI agent
        agent = create_openai_functions_agent(self.llm, self.tools, prompt)

        # Create the executor that will run the agent
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,  # Show the agent's thought process
            max_iterations=6, # Allow multiple steps for complex tasks
            handle_parsing_errors=True # Make the agent more robust
            )

        return agent_executor

    def process_request(self, user_input: str) -> Dict[str, Any]:
        """
        Takes a user's text input and processes it through the AI agent.

        Args:
            user_input: What the user asked for (as text)

        Returns:
            A dictionary with the agent's response in the 'output' key
        """
        if not self.client.sp:
             return {"output": "Sorry, I can't connect to Spotify right now. Please ensure you are logged in and have granted permissions."}

        print(f"Processing request with AgentExecutor: {user_input}")
        try:
            # Let the agent process the request
            response = self.agent_executor.invoke({"input": user_input})

            return {"output": response.get("output", "Sorry, I encountered an issue processing your request.")}

        except Exception as e:
            print(f"Error invoking AgentExecutor: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"output": f"An unexpected error occurred: {str(e)}"}

    def cleanup(self):
        """Clean up any resources when shutting down"""
        print("Cleaning up Spotify Agent resources (if any).")
        pass