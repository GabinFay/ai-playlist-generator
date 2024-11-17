import streamlit as st
import os
from openai import OpenAI
from Util.MySpotify import MySpotify
import requests
import json
import threading
from streamlit.runtime.scriptrunner import add_script_run_ctx

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
    print(f"playlist url: https://open.spotify.com/playlist/{pl_id}")

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

    while True:
        try:
            best_indices = [int(index.strip()) for index in response.choices[0].message.content.split(',')]
            if len(best_indices) != len(all_results):
                raise ValueError("Number of indices doesn't match number of queries")
            break  # Exit the loop if no exception is raised
        except ValueError as e:
            if "Number of indices doesn't match number of queries" in str(e):
                print(f"Retrying due to mismatch in number of indices... : {response.choices[0].message.content}")
                # Retry logic: request a new response from the LLM
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a music expert helping to match song queries with search results."},
                        {"role": "user", "content": prompt}
                    ]
                )
            else:
                print(f"Error: Unable to parse LLM response. {str(e)}")
                best_indices = [-1] * len(all_results)
                break
        except AttributeError as e:
            print(f"Error: Unable to parse LLM response. {str(e)}")
            best_indices = [-1] * len(all_results)
            break

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

def load_spotify_client():
    with st.spinner("Connecting to Spotify... Should take 10/20 seconds"):
        st.session_state.spotify_client = MySpotify(access_token=st.session_state['spotify_token'])
        print('client created')

if __name__=='__main__':
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
        # st.experimental_set_query_params()  # Clear query params after fetching the code
        # st.rerun()
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

    if 'spotify_token' in st.session_state:
        if 'spotify_client' not in st.session_state:
            # Create a thread for loading the Spotify client
            client_thread = threading.Thread(target=load_spotify_client)
            # Attach Streamlit's context to the thread
            add_script_run_ctx(client_thread)
            # Start the thread
            client_thread.start()
            st.session_state.step = 'enter_theme'  # Move to the next step immediately

        # Use the stored Spotify client
        if 'spotify_client' in st.session_state:
            print('client known')
            spo = st.session_state.spotify_client
            print('client used')
            print(st.session_state.get('step', 'Not set'))

        # Initialize session state variables for flow control
        if 'step' not in st.session_state:
            st.session_state.step = 'enter_theme'

        if st.session_state.step == 'enter_theme':
            st.session_state.description = st.text_area(
                "Enter a detailed description for your playlist:", 
                max_chars=1000,
                placeholder="Example: Make a playlist of electronic music that reminds of water, waves and nature"
            )
            if st.button("Generate Playlist"):
                if st.session_state.description:
                    st.session_state.step = 'generate_playlist'

        if st.session_state.step == 'generate_playlist':
            st.subheader("Generating playlist...")
            st.session_state.songs = generate_playlist(st.session_state.description)
            st.session_state.step = 'display_playlist'

        if st.session_state.step == 'display_playlist':
            st.subheader("Generated Songs:")
            for i, song in enumerate(st.session_state.songs):
                col1, col2 = st.columns([0.9, 0.1])
                col1.write(song)
                if col2.button("➖", key=f"remove_{i}"):
                    st.session_state.songs.pop(i)
                    st.rerun()

            refinement = st.text_input("Refine your playlist (e.g., 'Add more energetic tracks'):")
            if st.button("Refine Playlist"):
                st.session_state.songs = refine_playlist(st.session_state.description, "\n".join(st.session_state.songs), refinement)
                st.rerun()

            if st.button("Get Song Details"):
                st.session_state.song_details = get_song_details(st.session_state.description, st.session_state.songs)
                st.session_state.step = 'display_details'

            st.session_state.playlist_name = st.text_input("Enter a name for your Spotify playlist:", value=f"{st.session_state.description[:30]}... Playlist")
            if st.button("Create Spotify Playlist"):
                # New LLM call to format the songs list
                formatted_songs = format_songs_list(st.session_state.songs)
                st.session_state.songs = formatted_songs
                st.session_state.step = 'creating_playlist'

        if st.session_state.step == 'display_details':
            st.subheader("Song Details:")
            for detail in st.session_state.song_details:
                st.write(detail)
            if st.button("Back to Playlist"):
                st.session_state.step = 'display_playlist'

        if st.session_state.step == 'creating_playlist':
            st.subheader("Creating Spotify playlist...")
            not_found = create_spotify_playlist(st.session_state.songs, st.session_state.playlist_name)
            
            st.success(f"Playlist '{st.session_state.playlist_name}' created successfully!")
            
            if not_found:
                st.warning("Some songs were not found on Spotify:")
                for song in not_found:
                    st.write(song)
            
            if st.button("Create Another Playlist"):
                st.session_state.step = 'enter_theme'