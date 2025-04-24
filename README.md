# TuneSmith

An AI agent that translates thematic or mood-based prompts into curated Spotify playlists using LangChain and the Spotify Web API.

## Prerequisites

*   Python (3.9 or later recommended)
*   A Spotify Account
*   An OpenAI Account

## Installation

1.  **Clone the repository (or ensure you are in the `tunesmith-main` directory).**

2.  **Create and activate a virtual/conda environment :**

3.  **Install required packages:**
    ```bash
    pip install flask python-dotenv requests spotipy langchain langchain-openai langchain-core pydantic Flask-Session
    ```
    or use the requirements.txt file (not sure about this, it's quite messy)
    ```
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
    FLASK_SECRET_KEY="any_random_strong_secret_key"
    ```

## IMPORTANT: Spotify Developer Setup (Required for Current Version)

Because Spotify applications start in **Development Mode**, you currently **must** perform the following steps:

1.  **Go to the Spotify Developer Dashboard:** [https://developer.spotify.com/dashboard/](https://developer.spotify.com/dashboard/)
2.  **Log in** with the Spotify account you intend to use when logging into TuneSmith later.
3.  **Create a new App:**
    *   Click "Create app".
    *   Fill in the name and description.
    *   Go to the app's **Settings**.
    *   Add **exactly** `http://127.0.0.1:5000/callback` to the **Redirect URIs**. Save changes.
4.  **Get Credentials:** Copy the **Client ID** and **Client Secret** from this newly created app and put them into your `.env` file.
5.  **Add Your Test User:**
    *   In the app's settings on the dashboard, find **"Users and Access"**.
    *   Click "Add New User".
    *   Enter the **Full Name** and **Email Address** associated with the Spotify account you are currently logged into the dashboard with (and will use to test TuneSmith).
    *   Save the user.

**This setup is necessary because, in Development Mode, only explicitly registered users can authorize and use the application.**

## Running the Application

1.  **Ensure your virtual environment is activated.**
2.  **Make sure you have the `.env` file configured correctly.**
3.  **Run the Flask server:**
    ```bash
    python main.py
    ```
4.  **Open your web browser** and navigate to: `http://127.0.0.1:5000`
5.  Click **"Connect with Spotify"** and log in using the *same Spotify account you added* to "Users and Access" on the dashboard.
6.  Authorize the application.
7.  You should be redirected back to TuneSmith and can now enter prompts to create playlists.