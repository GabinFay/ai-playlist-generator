# Artist Featurings Finder

A simple Spotify application to identify collaborations between artists. This MVP focuses on finding tracks where two artists have collaborated.

## Features

- Search for two artists by name
- Fetch the full discography for each artist
- Identify tracks where both artists are featured
- Display detailed information about common tracks

## Installation

1. Clone this repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Authentication Setup

This application requires Spotify API credentials. You have two options for authentication:

### Option 1: Using Client Credentials (Recommended for first-time setup)

1. Create a Spotify Developer account at [developer.spotify.com](https://developer.spotify.com/)
2. Create a new application in the Spotify Developer Dashboard
3. Get your Client ID and Client Secret
4. Set up a Redirect URI (e.g., `http://localhost:8501`)
5. Create a `.env` file in the project root with the following:
   ```
   SPOTIFY_CLIENT_ID=your_client_id
   SPOTIFY_CLIENT_SECRET=your_client_secret
   SPOTIFY_REDIRECT_URI=your_redirect_uri
   SPOTIFY_SCOPE=user-library-read
   ```

### Option 2: Using Direct Access Token

If you already have a Spotify access token, you can use it directly:
1. Create a `.env` file with:
   ```
   SPOTIFY_ACCESS_TOKEN=your_access_token
   ```

## Usage

### Command Line Interface

Run the command-line version:

```
python featurings_finder.py
```

You can also specify two artists to compare:

```
python featurings_finder.py "Taylor Swift" "Ed Sheeran"
```

### Web Interface

Run the Streamlit web application:

```
streamlit run featurings_app.py
```

The web interface will guide you through the Spotify authentication process.

## How It Works

1. The application first authenticates with Spotify
2. It searches for the IDs of both artists
3. It fetches all tracks for each artist
4. It identifies tracks that appear in both discographies
5. It displays detailed information about these common tracks

## Default Artists

The default artists for the MVP are:
- Rihanna
- Drake

You can easily change these to search for collaborations between any two artists.

## Troubleshooting

If you encounter authentication errors:

1. Make sure your `.env` file is in the root directory of the project
2. Check that your Spotify API credentials are correct
3. For the web interface, try clearing your browser cookies and restarting the application
4. Ensure your Spotify Developer App has the correct redirect URI configured
