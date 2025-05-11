import os
from random import random
import time
import requests
import spotipy
from flask import Flask, redirect, url_for, session, request, render_template, jsonify
from pymongo import MongoClient
from urllib.parse import urlencode
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'supersecretkey')
app.config['SESSION_COOKIE_NAME'] = 'spotify_cookie'


# Load environment variables
SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
SPOTIPY_REDIRECT_URI = os.getenv('SPOTIPY_REDIRECT_URI')
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/SpotiSurf')

# Initialize MongoDB client
client = MongoClient(MONGO_URI)
db = client.get_database('SpotiSurf')
tokens_collection = db.tokens

# Spotify OAuth endpoints
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"

def get_spotify_auth_url():
    params = {
        'client_id': SPOTIPY_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': SPOTIPY_REDIRECT_URI,
        'scope': 'user-library-read user-top-read user-read-recently-played playlist-modify-public playlist-modify-private playlist-read-collaborative',
    }
    return f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"

def get_spotify_token(code):
    payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': SPOTIPY_REDIRECT_URI,
        'client_id': SPOTIPY_CLIENT_ID,
        'client_secret': SPOTIPY_CLIENT_SECRET,
    }
    response = requests.post(SPOTIFY_TOKEN_URL, data=payload)
    return response.json()

def refresh_spotify_token(refresh_token):
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': SPOTIPY_CLIENT_ID,
        'client_secret': SPOTIPY_CLIENT_SECRET,
    }
    response = requests.post(SPOTIFY_TOKEN_URL, data=payload)
    return response.json()

def save_token(user_id, token_info):
    token_info['expires_at'] = int(time.time()) + token_info['expires_in']
    tokens_collection.update_one({'user_id': user_id}, {'$set': token_info}, upsert=True)

def get_user_token(user_id):
    token_info = tokens_collection.find_one({'user_id': user_id})
    if token_info and token_info['expires_at'] < int(time.time()):
        new_token_info = refresh_spotify_token(token_info['refresh_token'])
        new_token_info['user_id'] = user_id
        save_token(user_id, new_token_info)
        return new_token_info
    return token_info

#Search Algorithm
def get_audio_features(track_id, token_info):
    """
    Fetches the audio features for a given track using the Spotify API.
    """
    audio_features_url = f"https://api.spotify.com/v1/audio-features/{track_id}"
    headers = {'Authorization': f"Bearer {token_info['access_token']}"}
    response = requests.get(audio_features_url, headers=headers)
    
    # Return the audio features if the request is successful
    if response.status_code == 200:
        return response.json()
    else:
        return None

def get_similar_tracks_based_on_features(track_id, token_info):
    features = get_audio_features(track_id, token_info)
    # Example of how to use features: you can refine this logic
    if features:
        tempo = features['tempo']
        energy = features['energy']
        danceability = features['danceability']
        # Use these features to search or filter similar songs, possibly by genre, tempo, etc.
        return search_for_similar_songs(tempo, energy, danceability, token_info) # type: ignore
    return []

def get_collaborative_filtering_recommendations(track_id, token_info):
    recommendations_url = "https://api.spotify.com/v1/recommendations"
    headers = {'Authorization': f"Bearer {token_info['access_token']}"}
    params = {
        'seed_tracks': track_id,
        'limit': 10  # Fetch 10 similar tracks
    }
    response = requests.get(recommendations_url, headers=headers, params=params)
    return response.json()['tracks']

def get_similar_songs_by_genre_artist(track_id, token_info):
    track_info_url = f"https://api.spotify.com/v1/tracks/{track_id}"
    headers = {'Authorization': f"Bearer {token_info['access_token']}"}
    response = requests.get(track_info_url, headers=headers)
    track_info = response.json()
    
    artist_id = track_info['artists'][0]['id']
    
    # Safely access the genre field
    genre = track_info.get('album', {}).get('genres', [None])[0]

    # Fetch top tracks for the artist or similar tracks within the genre
    artist_top_tracks_url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks"
    artist_params = {'country': 'US'}
    top_tracks_response = requests.get(artist_top_tracks_url, headers=headers, params=artist_params)
    return top_tracks_response.json()['tracks']   

def get_recommendations_based_on_track(track_id, token_info):
    """
    Fetch similar songs using Spotify's recommendation API with track, artist, and genre seeds.
    """
    # Get track audio features
    features = get_audio_features(track_id, token_info)
    
    # Get the track info to seed artist and genre
    track_info_url = f"https://api.spotify.com/v1/tracks/{track_id}"
    headers = {'Authorization': f"Bearer {token_info['access_token']}"}
    response = requests.get(track_info_url, headers=headers)
    track_info = response.json()
    
    artist_id = track_info['artists'][0]['id']
    genre = track_info.get('album', {}).get('genres', [None])[0]

    # Prepare the recommendation request with track, artist, and possibly genre
    recommendations_url = "https://api.spotify.com/v1/recommendations"
    params = {
        'seed_tracks': track_id,
        'seed_artists': artist_id,
        'limit': 10
    }

    # Include genre if available
    if genre:
        params['seed_genres'] = genre

    response = requests.get(recommendations_url, headers=headers, params=params)
    recommended_tracks = response.json().get('tracks', [])
    
    # Shuffle the recommendations to avoid repetitiveness
   # random.shuffle(recommended_tracks)
    
    return recommended_tracks

@app.route('/')
def index():
    if 'user_id' in session:
        token_info = get_user_token(session['user_id'])
        if token_info:
            headers = {'Authorization': f"Bearer {token_info['access_token']}"}
            response = requests.get("https://api.spotify.com/v1/me/playlists", headers=headers)
            playlists = response.json()
            return render_template('index.html', playlists=playlists)
    return redirect(url_for('login'))

@app.route('/login')
def login():
    auth_url = get_spotify_auth_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_info = get_spotify_token(code)

    headers = {'Authorization': f"Bearer {token_info['access_token']}"}
    response = requests.get("https://api.spotify.com/v1/me", headers=headers)
    user_profile = response.json()
    user_id = user_profile['id']

    token_info['user_id'] = user_id
    save_token(user_id, token_info)

    session['user_id'] = user_id
    return redirect(url_for('index'))

@app.route('/recommendations')
def recommendations():
    if 'user_id' in session:
        token_info = get_user_token(session['user_id'])
        if token_info:
            headers = {'Authorization': f"Bearer {token_info['access_token']}"}
            user_id = session['user_id']

            # Fetch user's liked tracks
            liked_tracks = db.liked_tracks.find_one({'user_id': user_id})
            liked_track_ids = liked_tracks['track_ids'] if liked_tracks and liked_tracks['track_ids'] else []

            # Fetch user's top tracks
            response = requests.get("https://api.spotify.com/v1/me/top/tracks", headers=headers)
            top_tracks = response.json()
            top_track_ids = [track['id'] for track in top_tracks['items'][:5]]

            # Fetch user's recently played tracks
            response = requests.get("https://api.spotify.com/v1/me/player/recently-played", headers=headers)
            recently_played = response.json()
            recently_played_ids = [item['track']['id'] for item in recently_played['items'][:5]]

            # Combine the seeds, ensuring uniqueness and using a limited number
            seed_tracks = list(set(liked_track_ids + top_track_ids + recently_played_ids))[:5]

            # Utilizing Spotify's Recommendation API
            recommendations_url = "https://api.spotify.com/v1/recommendations"
            params = {
                'seed_tracks': ','.join(seed_tracks),
                'limit': 10,
                'min_popularity': 50  # Fine-tuning for more popular songs
            }
            recommendations_response = requests.get(recommendations_url, headers=headers, params=params)
            recommendations = recommendations_response.json()

            # Adding like button for user feedback
            for track in recommendations['tracks']:
                track['liked'] = False

            return render_template('recommendations.html', recommendations=recommendations['tracks'])
    return redirect(url_for('login'))

@app.route('/like_track', methods=['POST'])
def like_track():
    if 'user_id' in session:
        user_id = session['user_id']
        data = request.get_json()
        track_id = data.get('track_id')

        if not track_id:
            return jsonify({'status': 'error', 'message': 'Track ID not provided'}), 400

        liked_tracks = db.liked_tracks.find_one({'user_id': user_id})

        if liked_tracks:
            # Add track if it's not already in the liked tracks list
            if track_id not in liked_tracks['track_ids']:
                db.liked_tracks.update_one({'user_id': user_id}, {'$push': {'track_ids': track_id}})
        else:
            # Create a new entry if the user has no liked tracks yet
            db.liked_tracks.insert_one({'user_id': user_id, 'track_ids': [track_id]})

        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'User not authenticated'}), 401

@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'user_id' in session:
        if request.method == 'POST':
            query = request.form['query']
            token_info = get_user_token(session['user_id'])
            if token_info:
                headers = {'Authorization': f"Bearer {token_info['access_token']}"}
                search_url = "https://api.spotify.com/v1/search"
                params = {'q': query, 'type': 'track', 'limit': 10, 'offset': 0}
                response = requests.get(search_url, headers=headers, params=params)
                results = response.json()
                
                # Get the first track's ID from search results to fetch recommendations
                if results['tracks']['items']:
                    track_id = results['tracks']['items'][0]['id']
                    recommended_tracks = get_recommendations_based_on_track(track_id, token_info)
                    return render_template('search.html', results=recommended_tracks)
                
        return render_template('search.html', results=None)
    return redirect(url_for('login'))

@app.route('/profile')
def profile():
    if 'user_id' in session:
        token_info = get_user_token(session['user_id'])
        if token_info:
            headers = {'Authorization': f"Bearer {token_info['access_token']}"}
            user_response = requests.get("https://api.spotify.com/v1/me", headers=headers)
            user_profile = user_response.json()
            top_tracks_response = requests.get("https://api.spotify.com/v1/me/top/tracks", headers=headers)
            top_tracks = top_tracks_response.json()
            playlists_response = requests.get("https://api.spotify.com/v1/me/playlists", headers=headers)
            playlists = playlists_response.json()
            recent_tracks_response = requests.get("https://api.spotify.com/v1/me/player/recently-played", headers=headers)
            recent_tracks = recent_tracks_response.json()
            return render_template('profile.html', user=user_profile, top_tracks=top_tracks['items'], playlists=playlists['items'], recent_tracks=recent_tracks['items'])
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/api/get_playlists')
def get_playlists():
    if 'user_id' in session:
        token_info = get_user_token(session['user_id'])
        if token_info:
            headers = {'Authorization': f"Bearer {token_info['access_token']}"}
            response = requests.get("https://api.spotify.com/v1/me/playlists", headers=headers)
            playlists = response.json()
            return {'playlists': playlists['items']}
    return {'error': 'User not authenticated'}, 401

@app.route('/api/create_playlist', methods=['POST'])
def create_playlist():
    if 'user_id' in session:
        data = request.json
        playlist_name = data.get('name')
        token_info = get_user_token(session['user_id'])
        if token_info:
            headers = {'Authorization': f"Bearer {token_info['access_token']}", 'Content-Type': 'application/json'}
            payload = {'name': playlist_name, 'public': True}
            response = requests.post("https://api.spotify.com/v1/users/{user_id}/playlists".format(user_id=session['user_id']), json=payload, headers=headers)
            playlist = response.json()
            return {'playlist': playlist}
    return {'error': 'User not authenticated'}, 401

@app.route('/api/add_to_playlist', methods=['POST'])
def add_to_playlist():
    if 'user_id' in session:
        data = request.json
        playlist_id = data.get('playlist_id')
        track_id = data.get('track_id')
        token_info = get_user_token(session['user_id'])
        if token_info:
            headers = {'Authorization': f"Bearer {token_info['access_token']}", 'Content-Type': 'application/json'}
            payload = {'uris': [f'spotify:track:{track_id}']}
            response = requests.post(f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks", json=payload, headers=headers)
            return {'status': 'success', 'response': response.json()}
    return {'error': 'User not authenticated'}, 401

@app.route('/lyrics/<track_id>')
def lyrics(track_id):
    if 'user_id' in session:
        token_info = get_user_token(session['user_id'])
        if token_info:
            sp = spotipy.Spotify(auth=token_info['access_token'])
            track = sp.track(track_id)
            artist_name = track['artists'][0]['name']
            track_name = track['name']
            lyrics_url = f'https://api.lyrics.ovh/v1/{artist_name}/{track_name}'
            response = requests.get(lyrics_url)
            if response.status_code == 200:
                lyrics = response.json().get('lyrics', 'Lyrics not found.')
            else:
                lyrics = 'Lyrics not found.'
            return render_template('lyrics.html', track=track, lyrics=lyrics)
    return redirect(url_for('login'))

@app.route('/discover')
def discover():
    if 'user_id' in session:
        token_info = get_user_token(session['user_id'])
        if token_info:
            headers = {'Authorization': f"Bearer {token_info['access_token']}"}
            new_releases_response = requests.get("https://api.spotify.com/v1/browse/new-releases", headers=headers)
            new_releases = new_releases_response.json()
            categories_response = requests.get("https://api.spotify.com/v1/browse/categories", headers=headers)
            categories = categories_response.json()
            featured_playlists_response = requests.get("https://api.spotify.com/v1/browse/featured-playlists", headers=headers)
            featured_playlists = featured_playlists_response.json()
            return render_template('discover.html', new_releases=new_releases['albums']['items'], categories=categories['categories']['items'], featured_playlists=featured_playlists['playlists']['items'])
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)