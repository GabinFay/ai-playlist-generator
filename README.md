# ai-playlist-generator
Text to Spotify playlist

Set your OPENAI_API_KEY environment variable
  
Create an app on the Spotify developer platform : https://developer.spotify.com/  
  
Set the Spotify environment variable appropriately  

Run pip install -r requirements.txt  

# To run:  

streamlit run ai_playlist_generator.py  

# Algo:  

Connect to your Spotify account  
Describe your playlist  
Remove some of the proposed tracks if needed / refine it with a follow up query / get explanations as to why these tracks were chosen  
Choose the playlist name  
Create it  
