# TuneSmith 

An AI assistant to help you find music and create/refine Spotify playlists based on natural language prompts. Built with LangChain, OpenAI, Spotify Web API, and Flask. Currently deployed publicly on https://tunesssmith.xyz/. Contact us if you'd like to be registered as a user. The branch with the deployment related files is Tunesmith-Deployed. 

## Features

*   **Conversational Input:** Describe moods, genres, activities, or artists to get music suggestions.
*   **AI Playlist Creation:** Ask TuneSmith to create Spotify playlists based on your descriptions.
*   **Song Search:** Ask TuneSmith to find specific songs or songs matching a theme.
*   **Playlist Refinement:**
    *   View a preview of created playlists.
    *   Optionally load and view the full tracklist.
    *   Remove individual tracks from the displayed list.
*   **Spotify Integration:** Connects securely to your Spotify account using OAuth2 to manage playlists.

## Prerequisites

*   Python (3.9 or later recommended)
*   A Spotify Account
*   An OpenAI Account (with API key)

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repo-url>
    cd <repo-dir>
    ```
2.  **Create and activate a virtual/conda environment:**
3.  **Install required packages:**
    *   **(Recommended)** Install manually:
        ```bash
        pip install flask python-dotenv requests spotipy langchain langchain-openai langchain-core pydantic Flask-Session
        ```
    *   **(Alternative)** Clean up `requirements.txt` (pretty messy rn) if needed, then:
        ```bash
        pip install -r requirements.txt
        ```
## Configuration

1.  **Create a `.env` file** in the project's root directory (`tunesmith-main`).
2.  **Add the following environment variables** to the `.env` file:

    ```dotenv
    # Get from OpenAI Platform: https://platform.openai.com/account/api-keys
    OPENAI_API_KEY="sk-..."

    # Get from Spotify Developer Dashboard (SEE IMPORTANT NOTE BELOW):
    SPOTIFY_CLIENT_ID="your_spotify_client_id"
    SPOTIFY_CLIENT_SECRET="your_spotify_client_secret"

    # Must match the Redirect URI set in your Spotify App Dashboard exactly:
    SPOTIFY_REDIRECT_URI="http://127.0.0.1:5000/callback"

    # A random string for Flask session security:
    FLASK_SECRET_KEY="generate_a_strong_random_secret_key"
    ```

## IMPORTANT: Spotify Developer Setup (Required for Development Mode)
Spotify applications start in **Development Mode**, limiting access. To run TuneSmith locally, you **must** perform these steps:

1.  **Go to the Spotify Developer Dashboard:** [https://developer.spotify.com/dashboard/](https://developer.spotify.com/dashboard/)
2.  **Log in** with the Spotify account you will use to test TuneSmith.
3.  **Create a new App:**
    *   Click "Create app".
    *   Fill in the name (e.g., "TuneSmith Dev") and description.
    *   Go to the app's **Settings**.
    *   Add **exactly** `http://127.0.0.1:5000/callback` to the **Redirect URIs**. Save changes.
4.  **Get Credentials:** Copy the **Client ID** and **Client Secret** from this new app and put them into your `.env` file.
5.  **Add Your Test User:**
    *   In the app's **Settings** on the dashboard, find **"Users and Access"**.
    *   Click "Add New User".
    *   Enter the **Full Name** and **Email Address** associated with the Spotify account you are using for testing.
    *   Save the user.

**This setup is necessary because, in Development Mode, only explicitly registered users can authorize and use the application.**

## Running the Application

1.  **Ensure your virtual environment is activated.**
2.  **Make sure your `.env` file is configured correctly.**
3.  **Run the Flask server:**
    ```bash
    python main.py
    ```
4.  **Open your web browser** and navigate to: `http://127.0.0.1:5000`
5.  Click **"Connect with Spotify"** and log in using the *same Spotify account you added* to "Users and Access" on the dashboard.
6.  Authorize the application when prompted by Spotify.
7.  You will be redirected back to TuneSmith.

## Usage

1.  Once logged in, use the main input field to describe your music request (e.g., "Create a chill lo-fi playlist for studying", "Find some 80s synthwave tracks", "Songs like 'Blinding Lights'").
2.  Click **"Submit"**.
3.  TuneSmith will process your request:
    *   If it creates a playlist, you'll see playlist details (cover art, track count, preview) and an "Open in Spotify" link.
    *   If it finds songs without creating a playlist, it will list them and offer a button to **"Create Playlist from This Description"**.
4.  **Playlist Interaction:**
    *   For created playlists, you can click **"Show All Tracks"** to load the full list.
    *   Click the **`×`** button next to any track to remove it from the playlist on Spotify.