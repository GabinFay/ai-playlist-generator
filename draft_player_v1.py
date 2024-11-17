import streamlit as st
import os
from openai import OpenAI
from Util.MySpotify import MySpotify
import requests
import json


SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')
SPOTIFY_SCOPE = os.getenv('SPOTIFY_SCOPE')

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def get_spotify_auth_url():
    auth_url = f"https://accounts.spotify.com/authorize?client_id={SPOTIFY_CLIENT_ID}&response_type=code&redirect_uri={SPOTIFY_REDIRECT_URI}&scope={SPOTIFY_SCOPE}"
    return auth_url

def exchange_code_for_token(code):
    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "client_id": SPOTIFY_CLIENT_ID,
        "client_secret": SPOTIFY_CLIENT_SECRET,
    }
    response = requests.post(token_url, data=payload)
    return response.json()

# Streamlit UI
st.title("AI Playlist Creator")

# Initialize session state variables
if 'auth_flow_started' not in st.session_state:
    st.session_state.auth_flow_started = False

# Check for the authorization code
print(st.query_params.to_dict())
code = st.query_params.get('code')

if 'spotify_token' not in st.session_state:
    if code:
        token_info = exchange_code_for_token(code)
        st.session_state['spotify_token'] = token_info['access_token']
    else:
        # No code yet, continue the auth process
        if not st.session_state.get('auth_flow_started', False):
            auth_url = get_spotify_auth_url()
            st.write("Please connect your Spotify account:")
            if st.button("Connect Spotify"):
                st.session_state.auth_flow_started = True
                st.query_params['auth_flow_started'] = True
                st.rerun()
        else:
            st.write("Redirecting to Spotify for authorization...")
            st.markdown(f'<meta http-equiv="refresh" content="0;url={get_spotify_auth_url()}">', unsafe_allow_html=True)
            st.stop()

if 'spotify_token' in st.session_state:
    if 'spotify_client' not in st.session_state:
        with st.spinner("Connecting to Spotify... Should take 10/20 seconds"):
            st.session_state.spotify_client = MySpotify(access_token=st.session_state['spotify_token'])
            print('client created')

    # Use the stored Spotify client
    print('client known')
    spo = st.session_state.spotify_client
    print('client used')
    print(st.session_state.get('step', 'Not set'))
    # Initialize session state variables for flow control
    if 'step' not in st.session_state:
        st.session_state.step = 'enter_theme'

    if st.session_state.step == 'enter_theme':
        st.session_state.description = st.text_area(
            "Enter a detailed description of the music you want to listen to:", 
            max_chars=1000,
            placeholder="Example: Electronic music that reminds of water, waves and nature"
        )
        if st.button("Generate Playlist"):
            if st.session_state.description:
                st.session_state.step = 'generate_playlist'

    if st.session_state.step == 'generate_playlist':
        st.subheader("Generating playlist...")
        st.session_state.songs = generate_playlist(st.session_state.description)
        st.session_state.formatted_songs = format_songs_list(st.session_state.songs)
        st.session_state.track_uris, not_found = search_spotify_tracks(st.session_state.formatted_songs)
        st.session_state.current_track_index = 0
        st.session_state.step = 'play_music'

    if st.session_state.step == 'play_music':
        st.subheader("Now Playing")
        if st.session_state.track_uris:
            current_track = st.session_state.track_uris[st.session_state.current_track_index]
            st.components.v1.iframe(f"https://open.spotify.com/embed/track/{current_track.split(':')[-1]}", height=80)

            col1, col2, col3 = st.columns(3)
            if col1.button("Previous") and st.session_state.current_track_index > 0:
                st.session_state.current_track_index -= 1
                st.rerun()
            if col2.button("Next") and st.session_state.current_track_index < len(st.session_state.track_uris) - 1:
                st.session_state.current_track_index += 1
                st.rerun()
            if col3.button("New Playlist"):
                st.session_state.step = 'enter_theme'
                st.rerun()

        if not_found:
            st.warning("Some songs were not found on Spotify:")
            for song in not_found:
                st.write(song)

def generate_playlist(description):
    prompt = f"Create a playlist of 20 songs based on this description: '{description}'. Return only the song names and artists, one per line, without numbering or any other text. It is important that there is no numbering before each song. Format each song as 'Artist --- Song'"
    
    messages = [
        {"role": "system", "content": "You are a music expert tasked with creating themed playlists."},
        {"role": "user", "content": prompt}
    ]

    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages
    )

    # Split the content into lines and filter out empty lines
    songs = [song.strip() for song in response.choices[0].message.content.strip().split('\n') if song.strip()]

    return songs

def refine_playlist(description, current_playlist, refinement):
    prompt = f"Based on the original description: '{description}', and the refinement request: '{refinement}', modify the following playlist:\n\n{current_playlist}\n\nProvide an updated list of 20 songs, one per line, without numbering or any other text. It is important that there is no numbering before each song. Format each song as 'Artist - Song'"
    
    messages = [
        {"role": "system", "content": "You are a music expert tasked with refining playlists."},
        {"role": "user", "content": prompt}
    ]

    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages
    )

    return response.choices[0].message.content.strip().split('\n')

def get_song_details(description, songs):
    prompt = f"For each song in the following list, provide a brief explanation of why it was chosen and how it fits the theme: '{description}'. Format the response as 'Song - Artist: Explanation'"
    
    songs_list = "\n".join(songs)
    messages = [
        {"role": "system", "content": "You are a music expert explaining song choices for themed playlists."},
        {"role": "user", "content": f"{prompt}\n\n{songs_list}"}
    ]

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )

    return response.choices[0].message.content.strip().split('\n')

def create_spotify_playlist(songs, playlist_name):
    pl_id = spo.find_pl_id(playlist_name, create_missing=True)

    all_results = []
    not_found = []

    for song in songs:
        results = spo.search(song, type="track", market='FR', limit=5)['tracks']['items']
        if results:
            formatted_results = [f"{' '.join([artist['name'] for artist in track['artists']])} - {track['name']}" for track in results]
            all_results.append((song, formatted_results, results))
        else:
            not_found.append(song)

    # Prepare data for LLM
    llm_input = [{"query": query, "candidates": candidates} for query, candidates, _ in all_results]

    # Make a single call to the LLM
    prompt = f"""Given a list of original queries and their corresponding search results, determine which result is the most likely match for each query. 
    Consider factors like artist name, song title, and whether it's a remix or original version.
    Return a list of indices (0-4) for the best matches, or -1 if none are suitable. The list should be in the same order as the input queries.

    Input:
    {json.dumps(llm_input, indent=2)}

    Output:
    Provide your response as a comma-separated list of integers, e.g.: 1,3,0,-1,2"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a music expert helping to match song queries with search results."},
            {"role": "user", "content": prompt}
        ]
    )

    try:
        best_indices = [int(index.strip()) for index in response.choices[0].message.content.split(',')]
        if len(best_indices) != len(all_results):
            raise ValueError("Number of indices doesn't match number of queries")
    except (ValueError, AttributeError) as e:
        print(f"Error: Unable to parse LLM response. {str(e)}")
        best_indices = [-1] * len(all_results)

    # Process the LLM results and add tracks to the playlist
    for (original_query, _, full_results), best_index in zip(all_results, best_indices):
        if best_index != -1 and 0 <= best_index < len(full_results):
            selected_track = full_results[best_index]
            spo.pl_add_tr(pl_id, selected_track["id"])
            print(f"Added: {original_query} -> {selected_track['artists'][0]['name']} - {selected_track['name']}")
        else:
            not_found.append(original_query)

    return not_found

def format_songs_list(songs):
    system_prompt = """You are a music expert tasked with formatting song information consistently."""
    
    user_prompt = """
    Format each song in the given list according to these rules:
    1. Remove any "featuring" word, like 'ft', or "feat." mentions. But keep the featured artist name and add it to the final string.
    2. Keep the word "remix" alongside who did the remix at the end of the output.
    3. Strip any additional keyword that his only here to indicate a featuring. 
    4. Separate the artists names and song name with a single space.
    5. Do not include any separators like "---" in the output.

    Return the formatted list of songs, with each song as a single string on a new line.

    Example
    input: Artist1 feat. Artist2 - Song Name (Remix)
    output : Artist1 Artist2 Song Name

    Example 2:
    input: Artist3 & Artist4 - Another Song ft. Artist5
    output: Artist3 Artist4 Artist5 Another Song

    Please format the following list of songs:
    """
    
    songs_list = "\n".join(songs)
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{user_prompt}\n{songs_list}"}
    ]

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )

    return response.choices[0].message.content.strip().split('\n')

def search_spotify_tracks(songs):
    all_results = []
    not_found = []

    for song in songs:
        results = spo.search(song, type="track", market='FR', limit=5)['tracks']['items']
        if results:
            formatted_results = [f"{' '.join([artist['name'] for artist in track['artists']])} - {track['name']}" for track in results]
            all_results.append((song, formatted_results, results))
        else:
            not_found.append(song)

    # ... (keep existing LLM matching logic)

    return [full_results[best_index]["uri"] for (_, _, full_results), best_index in zip(all_results, best_indices) if best_index != -1], not_found

