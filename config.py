import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Spotify API credentials
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:5000/callback")

# OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Flask secret key
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev_secret_key")

# Path to spotify-mcp directory (relative to project root)
SPOTIFY_MCP_PATH = os.path.join(os.path.dirname(__file__), "spotify-mcp")