from langchain.agents import AgentExecutor, initialize_agent, Tool
from langchain.memory import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI
from typing import Dict, Any, List, Optional, Union
import json
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth

class SpotifyClient:
    """Client for interacting with Spotify through the spotipy library"""
    
    def __init__(self, spotify_credentials: Dict[str, str]):
        self.credentials = spotify_credentials
        self.sp = None
        self._authenticate()
    
    def _authenticate(self):
        """Set up the Spotify client with proper authentication"""
        try:
            # If we have a token, use it directly
            if "token" in self.credentials and self.credentials["token"]:
                token_info = json.loads(self.credentials["token"])
                if "access_token" in token_info:
                    # Create client with the access token
                    self.sp = spotipy.Spotify(auth=token_info["access_token"])
                    return
            
            # If no valid token, create with client credentials
            sp_oauth = SpotifyOAuth(
                client_id=self.credentials["client_id"],
                client_secret=self.credentials["client_secret"],
                redirect_uri=self.credentials["redirect_uri"],
                scope="user-read-playback-state user-modify-playback-state playlist-read-private playlist-modify-private playlist-modify-public"
            )
            
            # Get an access token - this will use the authorization flow if needed
            token_info = sp_oauth.get_access_token(as_dict=True)
            
            # Create the Spotify client
            self.sp = spotipy.Spotify(auth=token_info["access_token"])
            
        except Exception as e:
            print(f"Error authenticating with Spotify: {str(e)}")
            raise
    
    def search_tracks(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search for tracks on Spotify"""
        if not self.sp:
            return {"error": "Not authenticated with Spotify"}
        
        try:
            results = self.sp.search(q=query, type='track', limit=limit)
            return results
        except Exception as e:
            print(f"Error searching Spotify: {str(e)}")
            return {"error": str(e)}
    
    def create_playlist(self, name: str, description: str, track_uris: List[str]) -> Dict[str, Any]:
        """Create a playlist on Spotify"""
        if not self.sp:
            return {"error": "Not authenticated with Spotify"}
        
        try:
            # Get current user's id
            user_id = self.sp.current_user()["id"]
            
            # Create an empty playlist
            playlist = self.sp.user_playlist_create(
                user=user_id,
                name=name,
                public=False,
                description=description
            )
            
            # Add tracks to the playlist
            if track_uris:
                self.sp.playlist_add_items(playlist["id"], track_uris)
            
            # Get the updated playlist with track count
            updated_playlist = self.sp.playlist(playlist["id"])
            
            return updated_playlist
        except Exception as e:
            print(f"Error creating playlist: {str(e)}")
            return {"error": str(e)}
    
    def control_playback(self, command: str, context_uri: Optional[str] = None) -> Dict[str, Any]:
        """Control Spotify playback"""
        if not self.sp:
            return {"error": "Not authenticated with Spotify"}
        
        try:
            result = {"success": True, "command": command}
            
            if command == "play":
                if context_uri:
                    self.sp.start_playback(context_uri=context_uri)
                else:
                    self.sp.start_playback()
                result["status"] = "playing"
            elif command == "pause":
                self.sp.pause_playback()
                result["status"] = "paused"
            elif command == "next":
                self.sp.next_track()
                result["status"] = "skipped"
            elif command == "previous":
                self.sp.previous_track()
                result["status"] = "previous"
            else:
                result = {"error": f"Unknown command: {command}"}
            
            return result
        except Exception as e:
            print(f"Error controlling playback: {str(e)}")
            return {"error": str(e)}

# Define tool functions that will be wrapped as LangChain tools
def spotify_search(query: str, limit: int = 10, client=None) -> str:
    """Search for tracks on Spotify"""
    result = client.search_tracks(query, limit)
    return json.dumps(result)

def spotify_create_playlist(name: str, description: str, track_uris: List[str], client=None) -> str:
    """Create a playlist on Spotify"""
    result = client.create_playlist(name, description, track_uris)
    return json.dumps(result)

def spotify_playback(action: str, context_uri: Optional[str] = None, client=None) -> str:
    """Control Spotify playback (play, pause, next, previous)"""
    result = client.control_playback(action, context_uri)
    return json.dumps(result)

class SpotifyAgent:
    def __init__(self, openai_api_key: str, spotify_credentials: Dict[str, str], spotify_mcp_path: str):
        self.openai_api_key = openai_api_key
        self.spotify_credentials = spotify_credentials
        self.spotify_mcp_path = spotify_mcp_path
        
        # Initialize the Spotify client
        self.client = SpotifyClient(spotify_credentials=self.spotify_credentials)
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            temperature=0.7,
            model="gpt-3.5-turbo",
            openai_api_key=self.openai_api_key
        )
        
        # Create tool functions with the client bound
        def search_with_client(query: str, limit: int = 10) -> str:
            return spotify_search(query, limit, self.client)
            
        def create_playlist_with_client(name: str, description: str, track_uris: List[str]) -> str:
            return spotify_create_playlist(name, description, track_uris, self.client)
            
        def playback_with_client(action: str, context_uri: Optional[str] = None) -> str:
            return spotify_playback(action, context_uri, self.client)
        
        # Format tools for LangChain
        self.tools = [
            Tool(
                name="spotify_search",
                func=search_with_client,
                description="Search for tracks on Spotify based on a query. Input should be a JSON string with 'query' and optional 'limit' fields."
            ),
            Tool(
                name="spotify_create_playlist",
                func=create_playlist_with_client,
                description="Create a playlist on Spotify. Input should be a JSON string with 'name', 'description', and 'tracks' fields, where 'tracks' is an array of Spotify track URIs."
            ),
            Tool(
                name="spotify_playback",
                func=playback_with_client,
                description="Control Spotify playback. Input should be a JSON string with 'action' field (play, pause, next, previous) and optional 'context_uri' field."
            )
        ]
        
        # Initialize memory
        self.memory = ConversationBufferMemory(return_messages=True)
        
        # Initialize agent
        self.agent = self._create_agent()
    
    def _create_agent(self) -> AgentExecutor:
        """Create the LangChain agent"""
        # Use initialize_agent with tools
        agent = initialize_agent(
            agent="chat-conversational-react-description",
            tools=self.tools,
            llm=self.llm,
            verbose=True,
            max_iterations=5,
            memory=self.memory,
            early_stopping_method="generate"
        )
        
        return agent
    
    def process_request(self, user_input: str) -> Dict[str, Any]:
        """Process a user request through the agent using direct OpenAI API calls"""
        try:
            print(f"Processing request: {user_input}")
            
            # Step 1: Use OpenAI API directly to analyze the request and generate search queries
            system_message = """
            You are an AI trained to generate Spotify playlists based on mood descriptions.
            Analyze the user's request and generate 3-5 specific search queries to find appropriate 
            tracks on Spotify. Return your output as a JSON object with a 'queries' field containing 
            an array of search terms.
            """
            
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": f"Generate Spotify search queries for this mood: {user_input}"}
            ]
            
            response = self.llm.predict_messages(messages).content
            
            # Try to parse JSON response or extract queries
            try:
                queries_data = json.loads(response)
                queries = queries_data.get('queries', [])
            except json.JSONDecodeError:
                # If not valid JSON, extract lines that look like queries
                import re
                queries = re.findall(r'"([^"]+)"', response)
                if not queries:
                    queries = [user_input]  # Fallback to original input
            
            print(f"Generated queries: {queries}")
            
            # Step 2: Search Spotify for tracks matching the queries
            all_tracks = []
            for query in queries[:3]:  # Limit to first 3 queries
                search_results = self.client.search_tracks(query, limit=5)
                if 'tracks' in search_results and 'items' in search_results['tracks']:
                    for track in search_results['tracks']['items']:
                        if track not in all_tracks:  # Avoid duplicates
                            all_tracks.append(track)
            
            # Step 3: Select top tracks (up to 15)
            selected_tracks = all_tracks[:15]
            track_uris = [track['uri'] for track in selected_tracks]
            
            # Step 4: Create the playlist
            playlist_name = f"Mood Playlist: {user_input[:30]}"
            playlist_description = f"Created based on the mood: {user_input}"
            
            playlist = self.client.create_playlist(playlist_name, playlist_description, track_uris)
            
            # Step 5: Generate a response
            track_info = "\n".join([
                f"- {track['name']} by {', '.join([artist['name'] for artist in track['artists']])}"
                for track in selected_tracks[:5]  # Show just first 5 tracks in the response
            ])
            
            output = f"""I've created a playlist based on your request: "{user_input}"

                        Your new playlist "{playlist_name}" contains {len(track_uris)} tracks.

                        Here are some highlights:
                        {track_info}
                        ...and more!

                        You can open it in Spotify with the link below."""
            
            # Record steps for display
            steps = [
                [{"tool": "spotify_search"}, f"Found {len(all_tracks)} tracks matching your mood"],
                [{"tool": "spotify_create_playlist"}, json.dumps(playlist)]
            ]
            
            thoughts = [
                f"Analyzed the mood '{user_input}' and generated search queries",
                f"Selected {len(track_uris)} tracks for the playlist"
            ]
            
            return {
                "output": output,
                "steps": steps,
                "thoughts": thoughts
            }
        except Exception as e:
            print(f"Error in direct processing: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "output": f"Error creating your playlist: {str(e)}",
                "steps": [],
                "thoughts": []
            }
    
    def cleanup(self):
        """Clean up resources"""
        # Nothing to clean up with the real client
        pass