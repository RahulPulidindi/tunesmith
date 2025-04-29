# Standard library imports
import json
import os
import time
from typing import Dict, Any, List, Optional, Type

# Third-party imports
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException

# LangChain imports
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.tools import Tool, StructuredTool
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field 
from langchain_core.messages import SystemMessage

# Pydantic models for validating Spotify API inputs
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

class SpotifyClient:
    """Client for interacting with Spotify through the spotipy library, managing authentication."""
    # ... (__init__, _authenticate, _ensure_client - Unchanged) ...
    def __init__(self, spotify_credentials: Dict[str, str]):
        self.credentials = spotify_credentials
        self.sp: Optional[spotipy.Spotify] = None
        self.sp_oauth: Optional[SpotifyOAuth] = None
        self._authenticate()

    def _authenticate(self):
        print("Attempting Spotify authentication...")
        try:
            self.sp_oauth = SpotifyOAuth(
                client_id=self.credentials["client_id"],
                client_secret=self.credentials["client_secret"],
                redirect_uri=self.credentials["redirect_uri"],
                scope="user-read-playback-state user-modify-playback-state playlist-read-private playlist-modify-private playlist-modify-public",
                cache_path=None,
            )
            print("SpotifyOAuth object created.")
            token_check = self.sp_oauth.get_cached_token()
            if token_check:
                 print(f"Found cached token info via get_cached_token().")
                 self.sp = spotipy.Spotify(auth_manager=self.sp_oauth)
                 print("Spotify client created successfully using cached token.")
            else:
                 if "token" in self.credentials and self.credentials["token"]:
                     print("No cached token, attempting to use token from credentials...")
                     try:
                         token_info_from_creds = json.loads(self.credentials["token"])
                         if 'access_token' in token_info_from_creds:
                              print("Creating Spotify client directly with access token from credentials.")
                              self.sp = spotipy.Spotify(auth=token_info_from_creds['access_token'])
                         else: self.sp = None
                     except Exception as e_inner:
                         print(f"Error creating client directly from credential token: {e_inner}")
                         self.sp = None
                 else: self.sp = None
            if self.sp: print("Spotify client instance created.")
            else: print("Failed to create Spotify client instance.")
        except Exception as e:
            print(f"ERROR during Spotify authentication: {str(e)}")
            import traceback; traceback.print_exc(); self.sp = None

    def _ensure_client(self) -> bool:
        if not self.sp:
            print("Spotify client not initialized or authentication failed previously.")
            if self.sp_oauth:
                print("Attempting re-authentication...")
                try:
                    token_check = self.sp_oauth.get_access_token(check_cache=True)
                    if token_check:
                        self.sp = spotipy.Spotify(auth_manager=self.sp_oauth)
                        print("Re-authentication successful.")
                        return True
                    else: return False
                except Exception as e: print(f"Error during re-authentication: {e}"); return False
            return False
        return True

    def search_tracks(self, query: str, limit: int = 10) -> Dict[str, Any]:
        if not self._ensure_client(): return {"error": "Not authenticated with Spotify"}
        try:
            print(f"Searching Spotify for query: '{query}' limit: {limit}")
            results = self.sp.search(q=query, type='track', limit=limit)
            simplified_tracks = []
            spotify_tracks = results.get("tracks", {}).get("items", [])
            if spotify_tracks:
                for track in spotify_tracks:
                    simplified_tracks.append({
                        "name": track.get("name"),
                        "artists": [artist.get("name") for artist in track.get("artists", [])],
                        "uri": track.get("uri"), "id": track.get("id")
                    })
            print(f"Found {len(simplified_tracks)} tracks.")
            return {"tracks": simplified_tracks}
        except SpotifyException as e:
            print(f"Spotify API error during search: {str(e)}")
            error_message = f"Spotify API error: {e.msg}" if hasattr(e, 'msg') and e.msg else f"Spotify API error code: {e.http_status}"
            return {"error": error_message}
        except Exception as e: print(f"Error searching Spotify: {str(e)}"); return {"error": str(e)}


    def create_playlist(self, name: str, track_uris: List[str], description: str = "") -> Dict[str, Any]:
        """Create a playlist, add tracks, and return enhanced details including cover and preview."""
        if not self._ensure_client(): return {"error": "Not authenticated with Spotify"}
        try:
            print(f"Attempting to create playlist '{name}' with {len(track_uris)} tracks. Description: '{description}'")
            user_id = self.sp.current_user()["id"]
            playlist = self.sp.user_playlist_create(user=user_id, name=name, public=False, description=description)
            playlist_id = playlist["id"]
            print(f"Empty playlist created with ID: {playlist_id}")
            if track_uris:
                for i in range(0, len(track_uris), 100):
                    chunk = track_uris[i:i+100]
                    print(f"Adding batch of {len(chunk)} tracks...")
                    self.sp.playlist_add_items(playlist_id, chunk)
                print("Tracks added successfully.")

            print(f"Fetching enhanced details for playlist {playlist_id}...")
            playlist_details = self.sp.playlist(playlist_id, fields="name,description,external_urls,id,uri,images,tracks.total")
            playlist_items_preview = self.sp.playlist_items(playlist_id, fields='items(track(name,artists(name),uri,id))', limit=5) # Get only preview initially

            cover_image_url = playlist_details.get("images", [{}])[0].get("url") if playlist_details.get("images") else None
            tracks_preview = []
            if playlist_items_preview and 'items' in playlist_items_preview:
                for item in playlist_items_preview['items']:
                    track = item.get('track')
                    if track and track.get('uri'): # Ensure track and uri exist
                        tracks_preview.append({
                            "name": track.get("name", "Unknown Track"),
                            "artists": [a.get("name", "Unknown Artist") for a in track.get("artists", [])],
                            "uri": track.get("uri"),
                            "id": track.get("id")
                        })

            result = {
                "name": playlist_details.get("name"), "description": playlist_details.get("description"),
                "external_urls": playlist_details.get("external_urls"), "id": playlist_details.get("id"),
                "uri": playlist_details.get("uri"), "tracks": {"total": playlist_details.get("tracks", {}).get("total")},
                "cover_image_url": cover_image_url, "tracks_preview": tracks_preview # Return preview
            }
            print(f"Successfully created playlist and fetched details: {result.get('name')}")
            return result
        except SpotifyException as e:
            print(f"Spotify API error during playlist creation/fetch: {str(e)}")
            error_message = f"Spotify API error: {e.msg}" if hasattr(e, 'msg') and e.msg else f"Spotify API error code: {e.http_status}"
            return {"error": error_message}
        except Exception as e:
            print(f"Error creating playlist or fetching details: {str(e)}")
            import traceback; traceback.print_exc(); return {"error": str(e)}

    def get_all_playlist_items(self, playlist_id: str) -> Dict[str, Any]:
        """Fetches all tracks from a playlist, handling pagination."""
        if not self._ensure_client(): return {"error": "Not authenticated with Spotify"}
        all_tracks = []
        offset = 0
        limit = 100 # Max limit per request
        print(f"Fetching all items for playlist {playlist_id}...")
        try:
            while True:
                print(f"Fetching playlist items: offset={offset}, limit={limit}")
                page = self.sp.playlist_items(
                    playlist_id,
                    fields='items(track(name,artists(name),uri,id)),next', # Get fields needed and 'next' URL
                    limit=limit,
                    offset=offset
                )
                if page and 'items' in page:
                    for item in page['items']:
                        track = item.get('track')
                        # Ensure track exists and has a URI before adding
                        if track and track.get('uri'):
                            all_tracks.append({
                                "name": track.get("name", "Unknown Track"),
                                "artists": [a.get("name", "Unknown Artist") for a in track.get("artists", [])],
                                "uri": track.get("uri"),
                                "id": track.get("id")
                            })
                    # Check if there's a next page using the 'next' field from response
                    if page.get('next'):
                        offset += limit # Increment offset for the next iteration
                    else:
                        break # No more pages
                else:
                    print("Warning: Received empty or invalid page from playlist_items.")
                    break # Exit loop if page data is missing

            print(f"Fetched a total of {len(all_tracks)} tracks.")
            return {"tracks": all_tracks} # Return list under 'tracks' key

        except SpotifyException as e:
            print(f"Spotify API error fetching all playlist items: {str(e)}")
            error_message = f"Spotify API error: {e.msg}" if hasattr(e, 'msg') and e.msg else f"Spotify API error code: {e.http_status}"
            return {"error": error_message}
        except Exception as e:
            print(f"Error fetching all playlist items: {str(e)}")
            import traceback; traceback.print_exc()
            return {"error": str(e)}

    def remove_track_from_playlist(self, playlist_id: str, track_uri: str) -> Dict[str, Any]:
        """Removes all occurrences of a specific track from a playlist."""
        if not self._ensure_client(): return {"error": "Not authenticated with Spotify"}
        try:
            print(f"Attempting to remove all occurrences of track '{track_uri}' from playlist '{playlist_id}'")
            snapshot = self.sp.playlist_remove_all_occurrences_of_items(
                playlist_id=playlist_id, items=[track_uri]
            )
            print(f"Track removal successful. New snapshot ID: {snapshot.get('snapshot_id')}")
            updated_playlist = self.sp.playlist(playlist_id, fields="tracks.total")
            new_track_count = updated_playlist.get("tracks", {}).get("total")
            return {"success": True, "snapshot_id": snapshot.get('snapshot_id'), "new_track_count": new_track_count}
        except SpotifyException as e:
            print(f"Spotify API error removing track: {str(e)}")
            error_message = f"Spotify API error: {e.msg}" if hasattr(e, 'msg') and e.msg else f"Spotify API error code: {e.http_status}"
            if hasattr(e, 'reason') and e.reason: error_message += f" (Reason: {e.reason})"
            return {"error": error_message, "success": False}
        except Exception as e: print(f"Error removing track: {str(e)}"); return {"error": str(e), "success": False}

    def control_playback(self, action: str, context_uri: Optional[str] = None) -> Dict[str, Any]:
        if not self._ensure_client(): return {"error": "Not authenticated with Spotify"}
        try:
            result = {"success": True, "action": action}; action = action.lower()
            print(f"Attempting playback action: {action}, context: {context_uri}")
            if action == "play":
                devices = self.sp.devices()
                active_device = next((d for d in devices['devices'] if d['is_active']), None)
                device_id = active_device['id'] if active_device else None
                if not device_id:
                     if devices['devices']:
                         device_id = devices['devices'][0]['id']
                         print(f"No active device. Transferring playback to: {devices['devices'][0]['name']}")
                         self.sp.transfer_playback(device_id=device_id, force_play=False); time.sleep(1)
                     else: return {"error": "No available Spotify devices found."}
                if context_uri: self.sp.start_playback(device_id=device_id, context_uri=context_uri)
                else: self.sp.start_playback(device_id=device_id)
                result["status"] = "Playback started/resumed"
            elif action == "pause": self.sp.pause_playback(); result["status"] = "Playback paused"
            elif action == "next": self.sp.next_track(); result["status"] = "Skipped to next track"
            elif action == "previous": self.sp.previous_track(); result["status"] = "Skipped to previous track"
            else: return {"error": f"Unknown playback action: {action}"}
            print(f"Playback action '{action}' successful."); return result
        except SpotifyException as e:
            print(f"Spotify API error during playback control: {str(e)}"); msg = getattr(e, 'msg', "") or ""
            if e.http_status == 404 and "No active device found" in msg: return {"error": "No active Spotify device found."}
            if e.http_status == 403 and ("restricted" in msg or "premium" in msg): return {"error": "Playback control failed. Requires Premium or restricted."}
            error_message = f"Spotify API error: {msg}" if msg else f"Spotify API error code: {e.http_status}"; return {"error": error_message}
        except Exception as e: print(f"Error controlling playback: {str(e)}"); return {"error": str(e)}

    def get_current_user_profile(self) -> Dict[str, Any]:
        if not self._ensure_client(): return {"error": "Not authenticated with Spotify"}
        try:
            print("Getting current user profile."); profile = self.sp.current_user()
            print(f"Found user: {profile.get('display_name')}"); return profile
        except SpotifyException as e:
            print(f"Spotify API error getting user profile: {str(e)}")
            error_message = f"Spotify API error: {e.msg}" if hasattr(e, 'msg') and e.msg else f"Spotify API error code: {e.http_status}"; return {"error": error_message}
        except Exception as e: print(f"Error getting user profile: {str(e)}"); return {"error": str(e)}

# Main agent class that handles user interactions
class SpotifyAgent:
    def __init__(self, openai_api_key: str, spotify_credentials: Dict[str, str]):
        self.openai_api_key = openai_api_key
        self.spotify_credentials = spotify_credentials
        self.client = SpotifyClient(spotify_credentials=self.spotify_credentials)
        
        # Temperature settings for different task types
        self.temperature_settings = {
            "creative": 0.9,      # High temperature for creative tasks
            "analytical": 0.3,    # Low temperature for analytical tasks
            "recommendation": 0.7, # Medium temperature for recommendations
            "default": 0.7        # Default temperature
        }
        
        self.llm = ChatOpenAI(
            temperature=self.temperature_settings["default"],
            model="gpt-3.5-turbo-0125",
            openai_api_key=self.openai_api_key
        )
        self.tools = self._create_tools()
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key='output'
        )
        self.agent_executor = self._create_agent_executor()

    def _create_tools(self) -> List[Tool]:
        tools = [
            StructuredTool.from_function(
                func=self.client.search_tracks, name="spotify_search_tracks",
                description="Search for tracks on Spotify based on a query string. Returns a list of tracks with details like name, artist, and URI.",
                args_schema=SpotifySearchSchema
            ),
            StructuredTool.from_function(
                func=self.client.create_playlist, name="spotify_create_playlist",
                description="Creates a new Spotify playlist for the current user with a given name, description, and list of track URIs. Returns details of the created playlist including its name, URL, ID, cover image, and track preview.",
                args_schema=SpotifyCreatePlaylistSchema
            ),
            StructuredTool.from_function(
                func=self.client.control_playback, name="spotify_control_playback",
                description="Controls Spotify playback. Actions: 'play', 'pause', 'next', 'previous'. 'play' can optionally take a context_uri (playlist, album, artist URI) to start playing specific content.",
                args_schema=SpotifyPlaybackSchema
            ),
             StructuredTool.from_function(
                func=self.client.get_current_user_profile, name="get_current_user_profile",
                description="Gets the profile information of the currently authenticated Spotify user, like display name and user ID."
            )
        ]
        return tools

    def _create_agent_executor(self) -> AgentExecutor:
        """Creates the LangChain AgentExecutor."""
        system_prompt = SystemMessage(content="""You are TuneSmith, a helpful AI assistant specialized in Spotify.
        Your goal is to help users create Spotify playlists based on their descriptions of mood, genre, activity, or theme.
        You can also search for tracks and control playback.

        **Workflow Rules:**
        1. Understand the user's request (e.g., "create a playlist for relaxing", "play some upbeat pop music", "find songs about heartbreak", "create a playlist from the songs we just discussed").
        2. **If the request explicitly asks to CREATE a playlist:**
           - Determine the core theme/description.
           - **If the request refers to songs already discussed or found in previous steps/memory:** Prioritize using the URIs for those tracks. Gather the relevant track URIs from memory or previous tool outputs.
           - **If new songs need to be found:** Determine suitable search queries. Use 'spotify_search_tracks' efficiently (avoid searching one by one unless absolutely necessary). Aim for 15-30 initial candidates.
           - Select the final list of track URIs (10-25 usually).
           - Use 'spotify_create_playlist' with a fitting name, a brief description, and the collected track URIs.
           - Your FINAL response must confirm playlist creation, providing its name and URL. Include a few sample tracks.
        3. **If the request asks to FIND or SEARCH for songs/tracks (and doesn't explicitly ask to create a playlist initially):**
           - Use 'spotify_search_tracks' with appropriate queries.
           - Your FINAL response should list the found tracks clearly. Do NOT create a playlist.
        4. **If controlling playback:** Use 'spotify_control_playback' and confirm the action.
        5. **If asked about the user:** Use 'get_current_user_profile'.
        6. **Error Handling:** If a Spotify tool returns an error, report that specific error clearly.
        7. **Focus:** Ensure the final response directly addresses the user's most recent request.""") # Added emphasis and refined creation flow for follow-ups

        prompt = ChatPromptTemplate.from_messages([
            system_prompt, MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"), MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        agent = create_openai_functions_agent(self.llm, self.tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent, tools=self.tools, memory=self.memory, verbose=True,
            max_iterations=8, # Keep iterations for now, prompt should fix it
            handle_parsing_errors=True, return_intermediate_steps=True
        )
        return agent_executor

    def _get_temperature_for_task(self, user_input: str) -> float:
        """Determine the appropriate temperature based on the task type."""
        input_lower = user_input.lower()
        
        # Creative tasks (playlist creation, mood-based recommendations)
        if any(word in input_lower for word in ["create", "make", "build", "new playlist", "mood", "feel"]):
            return self.temperature_settings["creative"]
            
        # Analytical tasks (statistics, analysis)
        elif any(word in input_lower for word in ["analyze", "statistics", "stats", "compare", "top"]):
            return self.temperature_settings["analytical"]
            
        # Recommendation tasks
        elif any(word in input_lower for word in ["recommend", "suggest", "similar to", "like"]):
            return self.temperature_settings["recommendation"]
            
        return self.temperature_settings["default"]

    def process_request(self, user_input: str) -> Dict[str, Any]:
        if not self.client.sp:
            return {"success": False, "error": "Spotify client not authenticated."}
            
        print(f"Processing request with AgentExecutor: {user_input}")
        try:
            # Determine and set appropriate temperature
            temperature = self._get_temperature_for_task(user_input)
            self.llm.temperature = temperature
            print(f"Using temperature setting: {temperature}")
            
            response = self.agent_executor.invoke({"input": user_input})
            final_output_text = response.get("output", "Task completed.")
            intermediate_steps = response.get("intermediate_steps", [])
            playlist_details_extracted = None
            agent_steps_explanation_list = []
            last_error = None

            if intermediate_steps:
                 for step in intermediate_steps:
                    if not isinstance(step, (tuple, list)) or len(step) < 2: continue
                    action, observation = step
                    tool_name = getattr(action, 'tool', 'unknown_action')
                    tool_input = getattr(action, 'tool_input', {})
                    agent_steps_explanation_list.append(f"Action: Called tool '{tool_name}' with input: {tool_input}")
                    obs_text = ""
                    if isinstance(observation, dict):
                        if observation.get("error"):
                            last_error = observation.get("error"); obs_text = f"Observation: Error - {last_error}"
                        elif len(json.dumps(observation, default=str)) > 500: obs_text = f"Observation: Received dictionary (keys: {list(observation.keys())})"
                        else: obs_text = f"Observation: {json.dumps(observation, indent=2)}"
                    else: obs_text = f"Observation: {str(observation)}"
                    agent_steps_explanation_list.append(obs_text)
                    # Observation from create_playlist now contains the enhanced details
                    if tool_name == "spotify_create_playlist" and isinstance(observation, dict) and not observation.get("error"):
                        playlist_url = observation.get("external_urls", {}).get("spotify")
                        if playlist_url:
                             playlist_details_extracted = {
                                 "name": observation.get("name"), "description": observation.get("description"),
                                 "url": playlist_url, "track_count": observation.get("tracks", {}).get("total"),
                                 "cover_image_url": observation.get("cover_image_url"), # Use directly
                                 "tracks_preview": observation.get("tracks_preview"),    # Use directly
                                 "id": observation.get("id") # Keep ID
                             }
                        else:
                             print("Warning: Playlist created but URL not found."); last_error = last_error or "Playlist created, but failed to get URL."

            agent_steps_explanation = "\n".join(agent_steps_explanation_list)

            if playlist_details_extracted:
                return { "success": True, "type": "playlist", "playlist": playlist_details_extracted,
                         "agent_steps_explanation": agent_steps_explanation, "raw_output": final_output_text }
            else:
                if last_error:
                     print(f"Tool error occurred: {last_error}"); return { "success": False, "error": last_error, "agent_steps_explanation": agent_steps_explanation }
                else:
                     print(f"No playlist created. Returning generic success."); return { "success": True, "type": "generic", "message": final_output_text, "agent_steps_explanation": agent_steps_explanation }
        except Exception as e:
            print(f"Error invoking AgentExecutor: {str(e)}"); import traceback; traceback.print_exc()
            return {"success": False, "error": f"Unexpected agent error: {str(e)}"}

    def cleanup(self): print("Cleaning up Spotify Agent resources (if any).")