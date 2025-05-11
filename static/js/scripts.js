document.addEventListener('DOMContentLoaded', () => {
    const themeToggle = document.getElementById('theme-toggle');
    const currentTheme = localStorage.getItem('theme') || 'light-mode';
    document.body.classList.add(currentTheme);

    const navbar = document.querySelector('.navbar');
    if (currentTheme === 'dark-mode') {
        navbar.classList.add('dark-mode');
        themeToggle.checked = true;
    } else {
        navbar.classList.add('light-mode');
    }

    themeToggle.addEventListener('change', () => {
        if (themeToggle.checked) {
            document.body.classList.replace('light-mode', 'dark-mode');
            navbar.classList.replace('light-mode', 'dark-mode');
            localStorage.setItem('theme', 'dark-mode');
        } else {
            document.body.classList.replace('dark-mode', 'light-mode');
            navbar.classList.replace('dark-mode', 'light-mode');
            localStorage.setItem('theme', 'light-mode');
        }
    });
});

document.addEventListener('DOMContentLoaded', () => {
    const recommendationsBtn = document.getElementById('recommendations-btn');
    const magnifyingGlassIcon = document.querySelector('.magnifying-glass-icon');
    const buttonText = document.querySelector('.button-text');
    const progressBarContainer = document.querySelector('.progress-bar');
    const progress = document.querySelector('.progress');

    // Click event for the Get Recommendations button
    recommendationsBtn.addEventListener('click', () => {
        // Hide text and show the magnifying glass animation
        buttonText.classList.add('hidden');
        magnifyingGlassIcon.classList.add('animate-search');

        // Show progress bar
        progressBarContainer.classList.remove('hidden');

        // Animate progress bar (duration matched with recommendation algorithm)
        let progressValue = 0;
        const progressInterval = setInterval(() => {
            if (progressValue < 100) {
                progressValue += 5; // Adjust the increment based on recommendation algo time
                progress.style.width = `${progressValue}%`;
            } else {
                clearInterval(progressInterval);
                // Trigger the recommendations once progress is complete
                window.location.href = '/recommendations';
            }
        }, 300); // Adjust speed to sync with the server request time
    });
});

// Function to handle like button click
function toggleLike(button, trackId) {
    // Toggle the active state of the like button
    button.classList.toggle('active');

    // Play the sound
    const sound = document.getElementById('like-sound');
    sound.play();

    // Send the like request to the server
    fetch('/like_track', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ track_id: trackId }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            console.log('Track liked successfully');
        } else {
            alert('Error liking track: ' + data.message);
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    let currentlyPlayingAudio = null;

    function stopCurrentlyPlayingAudio() {
        if (currentlyPlayingAudio) {
            currentlyPlayingAudio.pause();
            currentlyPlayingAudio.currentTime = 0;
        }
    }

    document.querySelectorAll('.track-preview').forEach(audio => {
        audio.addEventListener('play', () => {
            if (currentlyPlayingAudio && currentlyPlayingAudio !== audio) {
                stopCurrentlyPlayingAudio();
            }
            currentlyPlayingAudio = audio;
        });

        audio.addEventListener('ended', () => {
            currentlyPlayingAudio = null;
        });
    });
});

let temporaryTrackId = null;

function showAddToPlaylistPopup(trackId) {
    temporaryTrackId = trackId;
    const popup = document.getElementById('playlist-popup');
    const playlistList = document.getElementById('playlist-list');
    playlistList.innerHTML = ''; // Clear existing items

    fetch('/api/get_playlists')
        .then(response => response.json())
        .then(data => {
            if (data.playlists) {
                data.playlists.forEach(playlist => {
                    const listItem = document.createElement('li');
                    const button = document.createElement('button');
                    button.innerText = playlist.name;
                    button.onclick = () => addToPlaylist(temporaryTrackId, playlist.id);
                    listItem.appendChild(button);
                    playlistList.appendChild(listItem);
                });
            }
            popup.classList.remove('hidden');
        });
        document.getElementById('close-button').addEventListener('click', hideAddToPlaylistPopup);
}

function hideAddToPlaylistPopup() {
    document.getElementById('playlist-popup').classList.add('hidden');
}

function triggerCancelButton() {
    const closeButton = document.getElementById('close-button');
    if (closeButton) {
        closeButton.click();
    }
}

function createNewPlaylist() {
    const playlistName = prompt("Enter new playlist name:");
    if (playlistName) {
        fetch('/api/create_playlist', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name: playlistName })
        })
        .then(response => response.json())
        .then(data => {
            if (data.playlist) {
                triggerCancelButton(); // Trigger the cancel button to close the popup
                setTimeout(() => {
                    showAddToPlaylistPopup(temporaryTrackId); // Reopen the popup after a delay with the stored track ID
                }, 100); // 1 second delay
            }
        });
    }
}

function addToPlaylist(trackId, playlistId) {
    fetch('/api/add_to_playlist', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ track_id: trackId, playlist_id: playlistId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert("Track added to playlist!");
            hideAddToPlaylistPopup(); // Close popup after adding
        } else {
            alert("Failed to add track to playlist.");
        }
    })
    .catch(error => {
        console.error("An error occurred while adding the track to the playlist:", error);
        alert("An error occurred while adding the track to the playlist.");
    });
}

//like button fuctionality
document.addEventListener("DOMContentLoaded", function() {
    let icons = document.querySelectorAll('ion-icon');
    icons.forEach(icon => {
        icon.onclick = function() {
            icon.classList.toggle('active');
            let trackId = icon.getAttribute('data-track-id');
            likeTrack(trackId);
        }
    });
});

// Add this to your scripts.js file
let searchInput = document.querySelector('input[name="query"]');
searchInput.addEventListener('input', function() {
    fetch('/autocomplete?query=' + this.value)
        .then(response => response.json())
        .then(data => {
            // Show suggestions in a dropdown or list below the input field
        });
});

