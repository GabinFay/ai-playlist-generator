from Util.MySpotify import MySpotify
import os
from dotenv import load_dotenv
import sys
from difflib import SequenceMatcher
import re

# Load environment variables from .env file
load_dotenv()

def string_similarity(a, b):
    """Calculate the similarity ratio between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def is_remix(track_name, album_name):
    """
    Determine if a track is a remix based on its name or album name.
    
    Args:
        track_name: The name of the track
        album_name: The name of the album
        
    Returns:
        bool: True if the track is identified as a remix, False otherwise
    """
    # Check for remix keywords in track name suffix or album
    if re.search(r'[-(\[]\s*.*(remix|mix|edit|version|extended|instrumental)', track_name, re.IGNORECASE):
        return True
    if 'remix' in album_name.lower():
        return True
    return False

def should_keep_remix(track_name, artist1_name, artist2_name):
    """
    Determine if a remix should be kept based on whether it's remixed by one of our artists.
    
    Args:
        track_name: The name of the track
        artist1_name: First artist name
        artist2_name: Second artist name
        
    Returns:
        bool: True if the remix should be kept, False otherwise
    """
    # Split track name to extract suffix
    parts = re.split(r'[-(\[]', track_name, 1)
    if len(parts) < 2:
        return False
    suffix = parts[1].lower()
    # Check if either artist is in the suffix
    return artist1_name.lower() in suffix or artist2_name.lower() in suffix

def get_base_track_name(track_name):
    """
    Get the base name of a track by removing any remix or feature information.
    
    Args:
        track_name: The full track name
        
    Returns:
        str: The base track name
    """
    # Remove everything after these delimiters
    for delimiter in [' - ', ' (', ' [', ' feat', ' ft.', ' with']:
        if delimiter in track_name:
            track_name = track_name.split(delimiter)[0]
    
    return track_name.lower().strip()

def deduplicate_tracks(tracks):
    """
    Remove duplicate tracks based on similar track names.
    
    Args:
        tracks: List of track objects
        
    Returns:
        list: Deduplicated list of tracks
    """
    if not tracks:
        return []
        
    print("\nDeduplicating tracks with similar names...")
    
    # Group tracks by similar names
    track_groups = {}
    
    for track in tracks:
        base_name = get_base_track_name(track['name'])
        
        # Check if this track is similar to any existing group
        found_group = False
        for group_name in list(track_groups.keys()):
            if string_similarity(base_name, group_name) > 0.85:  # High similarity threshold
                track_groups[group_name].append(track)
                found_group = True
                break
        
        # If no similar group found, create a new one
        if not found_group:
            track_groups[base_name] = [track]
    
    # Print groups for debugging
    for base_name, group in track_groups.items():
        print(f"\nFound {len(group)} similar tracks for '{base_name}':")
        for i, track in enumerate(group, 1):
            print(f"  {i}. {track['name']} - {track['album']}")
    
    # Choose the best track from each group (prefer original versions)
    deduplicated = []
    
    for base_name, group in track_groups.items():
        # Sort by:
        # 1. Prefer non-remixes
        # 2. Prefer tracks from albums (not singles)
        # 3. Prefer older releases (they're usually the originals)
        sorted_group = sorted(group, key=lambda t: (
            is_remix(t['name'], t['album']),  # False (non-remix) comes first
            'remix' in t['album'].lower(),    # False (non-remix album) comes first
            t['album'].lower().endswith('single'),  # False (not a single) comes first
            t['release_date']                 # Earlier date comes first
        ))
        
        best_track = sorted_group[0]
        deduplicated.append(best_track)
        print(f"Keeping '{best_track['name']}' from '{best_track['album']}' for '{base_name}'")
    
    print(f"\nReduced from {len(tracks)} to {len(deduplicated)} unique tracks")
    return deduplicated

class FeaturingsFinder:
    def __init__(self, spotify_client=None):
        """Initialize the FeaturingsFinder with a Spotify client."""
        self.spo = spotify_client
    
    def find_artist_id(self, artist_name):
        """Search for an artist by name and return their ID."""
        results = self.spo.search(artist_name, type="artist", limit=10)
        if not results['artists']['items']:
            print(f"No ID found for artist: {artist_name}")
            return None
            
        # Find the artist with the closest name match
        artists = results['artists']['items']
        
        # First, try exact match (case insensitive)
        for artist in artists:
            if artist['name'].lower() == artist_name.lower():
                print(f"Found exact match for {artist_name}: {artist['name']} (ID: {artist['id']})")
                return artist['id']
        
        # If no exact match, use string similarity
        similarities = [(artist, string_similarity(artist_name, artist['name'])) 
                        for artist in artists]
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Print top matches for debugging
        print(f"Top matches for '{artist_name}':")
        for i, (artist, score) in enumerate(similarities[:3], 1):
            print(f"  {i}. {artist['name']} (Score: {score:.2f}, ID: {artist['id']})")
        
        best_match = similarities[0][0]
        artist_id = best_match['id']
        
        print(f"Selected best match for {artist_name}: {best_match['name']} (ID: {artist_id})")
        return artist_id
    
    def get_artist_tracks(self, artist_id):
        """Get all tracks associated with an artist."""
        # Get artist details for verification
        artist_details = self.spo.artist(artist_id)
        print(f"Getting tracks for: {artist_details['name']} (ID: {artist_id})")
        
        # Get artist's albums
        albums = []
        results = self.spo.artist_albums(artist_id, album_type='album,single', limit=50)
        albums.extend(results['items'])
        while results['next']:
            results = self.spo.next(results)
            albums.extend(results['items'])
        
        print(f"Found {len(albums)} albums for artist ID: {artist_id}")
        
        # Get all tracks from all albums
        tracks = []
        for album in albums:
            album_tracks = self.spo.album_tracks(album['id'])['items']
            for track in album_tracks:
                # Add album information and check if this artist is featured
                track['album_name'] = album['name']
                track['album_id'] = album['id']
                track['release_date'] = album.get('release_date', 'Unknown')
                tracks.append(track)
        
        print(f"Found {len(tracks)} total tracks for artist ID: {artist_id}")
        # Print artists in a few tracks to debug
        if tracks:
            print("Sample track artists:")
            for i in range(min(3, len(tracks))):
                artists_str = ", ".join([a['name'] for a in tracks[i]['artists']])
                print(f"  - {tracks[i]['name']}: {artists_str}")
        
        return tracks
    
    def find_featurings(self, artist1_name, artist2_name, filter_remixes=False, deduplicate=False):
        """Find tracks featuring both artists."""
        # Find artist IDs
        artist1_id = self.find_artist_id(artist1_name)
        artist2_id = self.find_artist_id(artist2_name)
        
        if not artist1_id or not artist2_id:
            return {"error": "One or both artists not found"}
        
        # Get tracks for both artists
        print(f"\nGetting tracks for {artist1_name}...")
        artist1_tracks = self.get_artist_tracks(artist1_id)
        print(f"\nGetting tracks for {artist2_name}...")
        artist2_tracks = self.get_artist_tracks(artist2_id)
        
        # Debug: Check if artists appear in each other's tracks
        print(f"\nChecking if {artist2_name} appears in {artist1_name}'s tracks...")
        for track in artist1_tracks[:10]:  # Check first 10 tracks
            artist_names = [artist['name'].lower() for artist in track['artists']]
            if artist2_name.lower() in " ".join(artist_names):
                print(f"Found {artist2_name} in {artist1_name}'s track: {track['name']}")
                print(f"  Artists: {', '.join([a['name'] for a in track['artists']])}")
        
        print(f"\nChecking if {artist1_name} appears in {artist2_name}'s tracks...")
        for track in artist2_tracks[:10]:  # Check first 10 tracks
            artist_names = [artist['name'].lower() for artist in track['artists']]
            if artist1_name.lower() in " ".join(artist_names):
                print(f"Found {artist1_name} in {artist2_name}'s track: {track['name']}")
                print(f"  Artists: {', '.join([a['name'] for a in track['artists']])}")
        
        # Extract track IDs for comparison
        artist1_track_ids = {track['id'] for track in artist1_tracks}
        artist2_track_ids = {track['id'] for track in artist2_tracks}
        
        print(f"\nTrack ID comparison:")
        print(f"  {artist1_name} has {len(artist1_track_ids)} unique track IDs")
        print(f"  {artist2_name} has {len(artist2_track_ids)} unique track IDs")
        
        # Find common tracks
        common_track_ids = artist1_track_ids.intersection(artist2_track_ids)
        print(f"  Common track IDs: {len(common_track_ids)}")
        
        # Get full information for common tracks
        common_tracks = []
        for track_id in common_track_ids:
            # Find the track in artist1's tracks (could use either artist's tracks)
            track_info = next((track for track in artist1_tracks if track['id'] == track_id), None)
            if track_info:
                # Format the data for display
                artists = ", ".join([artist['name'] for artist in track_info['artists']])
                common_tracks.append({
                    "track_id": track_id,
                    "name": track_info['name'],
                    "artists": artists,
                    "album": track_info['album_name'],
                    "release_date": track_info['release_date']
                })
        
        # Check for collaborations based on artist names (additional method)
        print("\nLooking for collaborations based on artist names...")
        name_based_collaborations = []
        
        # Check artist1's tracks for artist2's name
        for track in artist1_tracks:
            artists_names = [a['name'].lower() for a in track['artists']]
            # Check if artist2 is in the list of artists
            if any(string_similarity(a, artist2_name) > 0.8 for a in artists_names):
                artists = ", ".join([artist['name'] for artist in track['artists']])
                collab = {
                    "track_id": track['id'],
                    "name": track['name'],
                    "artists": artists,
                    "album": track['album_name'],
                    "release_date": track['release_date'],
                    "found_in": f"{artist1_name}'s tracks"
                }
                if track['id'] not in common_track_ids:  # Avoid duplicates
                    name_based_collaborations.append(collab)
                    print(f"Found collaboration: {track['name']} by {artists}")
        
        # Check artist2's tracks for artist1's name
        for track in artist2_tracks:
            artists_names = [a['name'].lower() for a in track['artists']]
            # Check if artist1 is in the list of artists
            if any(string_similarity(a, artist1_name) > 0.8 for a in artists_names):
                artists = ", ".join([artist['name'] for artist in track['artists']])
                collab = {
                    "track_id": track['id'],
                    "name": track['name'],
                    "artists": artists,
                    "album": track['album_name'],
                    "release_date": track['release_date'],
                    "found_in": f"{artist2_name}'s tracks"
                }
                if track['id'] not in common_track_ids:  # Avoid duplicates
                    name_based_collaborations.append(collab)
                    print(f"Found collaboration: {track['name']} by {artists}")
        
        print(f"\nFound {len(name_based_collaborations)} additional collaborations by artist name")
        
        # Filter remixes if requested
        if filter_remixes:
            print("\nFiltering out unwanted remixes...")
            filtered_collaborations = []
            
            for track in common_tracks + name_based_collaborations:
                track_name = track["name"]
                album_name = track["album"]
                
                if is_remix(track_name, album_name):
                    if should_keep_remix(track_name, artist1_name, artist2_name):
                        filtered_collaborations.append(track)
                        print(f"Keeping remix: {track_name} - remixed by one of the artists")
                    else:
                        print(f"Filtering out third-party remix: {track_name}")
                else:
                    filtered_collaborations.append(track)
                    print(f"Keeping non-remix track: {track_name}")
            
            # Split into common tracks and name-based collaborations for consistent format
            common_track_ids = {track["track_id"] for track in common_tracks}
            common_tracks = [t for t in filtered_collaborations if t["track_id"] in common_track_ids]
            name_based_collaborations = [t for t in filtered_collaborations if t["track_id"] not in common_track_ids]
            
            print(f"\nAfter filtering, kept {len(filtered_collaborations)} tracks:")
            print(f"  - Common tracks: {len(common_tracks)}")
            print(f"  - Name-based collaborations: {len(name_based_collaborations)}")
        
        # Deduplicate tracks if requested
        if deduplicate:
            # Deduplicate common tracks and name-based collaborations together
            all_tracks = common_tracks + name_based_collaborations
            all_deduplicated = deduplicate_tracks(all_tracks)
            
            # Split back into common tracks and name-based collaborations
            common_track_ids = {track["track_id"] for track in common_tracks}
            common_tracks = [t for t in all_deduplicated if t["track_id"] in common_track_ids]
            name_based_collaborations = [t for t in all_deduplicated if t["track_id"] not in common_track_ids]
        
        return {
            "artist1": artist1_name,
            "artist2": artist2_name,
            "common_tracks": common_tracks,
            "name_based_collaborations": name_based_collaborations,
            "total_count": len(common_tracks) + len(name_based_collaborations)
        }

def main():
    """Main function to run when the script is executed directly."""
    # Check for required environment variables
    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI')
    
    # Check if we have a direct access token
    access_token = os.getenv('SPOTIFY_ACCESS_TOKEN')
    
    # Initialize Spotify client
    try:
        if access_token:
            print("Using provided access token for authentication")
            spotify = MySpotify(
                access_token=access_token,
                skip_user_playlists=True  # Skip loading playlists to speed up initialization
            )
        elif client_id and client_secret and redirect_uri:
            print("Using client credentials for authentication")
            spotify = MySpotify(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope="user-library-read",
                skip_user_playlists=True  # Skip loading playlists to speed up initialization
            )
        else:
            print("Error: Missing Spotify credentials")
            print("Please set SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, and SPOTIFY_REDIRECT_URI")
            print("Or set SPOTIFY_ACCESS_TOKEN directly in your .env file")
            sys.exit(1)
            
        # Initialize FeaturingsFinder
        finder = FeaturingsFinder(spotify_client=spotify)
        
        # Get artist names from command line args or use defaults
        artist1 = "Rihanna"
        artist2 = "Drake"
        filter_remixes = True    # Enable remix filtering by default
        deduplicate_tracks = True  # Enable track deduplication by default
        
        if len(sys.argv) >= 3:
            artist1 = sys.argv[1]
            artist2 = sys.argv[2]
            # If a fourth argument is provided, use it as a flag for remix filtering
            if len(sys.argv) >= 4:
                filter_remixes = sys.argv[3].lower() in ['true', 't', 'yes', 'y', '1']
            # If a fifth argument is provided, use it as a flag for deduplication
            if len(sys.argv) >= 5:
                deduplicate_tracks = sys.argv[4].lower() in ['true', 't', 'yes', 'y', '1']
        
        print(f"Searching for collaborations between {artist1} and {artist2}...")
        print(f"Remix filtering: {'Enabled' if filter_remixes else 'Disabled'}")
        print(f"Track deduplication: {'Enabled' if deduplicate_tracks else 'Disabled'}")
        
        results = finder.find_featurings(
            artist1, 
            artist2, 
            filter_remixes=filter_remixes,
            deduplicate=deduplicate_tracks
        )
        
        # Display results
        if "error" in results:
            print(f"Error: {results['error']}")
            sys.exit(1)
            
        print(f"\nFeaturings between {results['artist1']} and {results['artist2']}:")
        total_count = results['total_count']
        print(f"Total collaborations found: {total_count}")
        
        if total_count > 0:
            if len(results['common_tracks']) > 0:
                print("\nTracks found in both artists' catalogs:")
                for i, track in enumerate(results['common_tracks'], 1):
                    print(f"\n{i}. {track['name']}")
                    print(f"   Artists: {track['artists']}")
                    print(f"   Album: {track['album']}")
                    print(f"   Release date: {track['release_date']}")
            
            if 'name_based_collaborations' in results and len(results['name_based_collaborations']) > 0:
                print("\nAdditional collaborations found by artist name:")
                start_idx = len(results['common_tracks']) + 1
                for i, track in enumerate(results['name_based_collaborations'], start_idx):
                    print(f"\n{i}. {track['name']}")
                    print(f"   Artists: {track['artists']}")
                    print(f"   Album: {track['album']}")
                    print(f"   Release date: {track['release_date']}")
                    print(f"   Found in: {track['found_in']}")
        else:
            print("\nNo collaborations found. This may be due to:")
            print("1. The artist names could be misspelled or not match Spotify's exact names")
            print("2. The artists might collaborate under different names/aliases")
            print("3. The API might be returning limited results")
            print("\nTry checking spelling or using different artist names.")
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 