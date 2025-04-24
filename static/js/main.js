document.addEventListener('DOMContentLoaded', () => {
    // Get references to all UI elements
    const loginPrompt = document.getElementById('login-prompt');
    const appContainer = document.getElementById('app-container');
    const loadingContainer = document.getElementById('loading-container');
    const errorContainer = document.getElementById('error-container');
    const resultContainer = document.getElementById('result-container');

    const authStatus = document.getElementById('auth-status');
    const loginButton = document.getElementById('login-button');
    const userInfo = document.getElementById('user-info');
    const userDisplayName = document.getElementById('user-display-name');
    const logoutButton = document.getElementById('logout-button');

    const requestForm = document.getElementById('request-form');
    const userRequestInput = document.getElementById('user-request');
    const submitButton = document.getElementById('submit-button');
    const submitButtonText = submitButton ? submitButton.textContent : 'Submit';

    const errorMessage = document.getElementById('error-message');

    let originalUserPrompt = '';

    // Updates UI elements based on authentication state
    function updateUIForAuthState(isLoggedIn, userData = {}) {
        if (loginPrompt) loginPrompt.style.display = isLoggedIn ? 'none' : 'block';
        if (appContainer) appContainer.style.display = isLoggedIn ? 'block' : 'none';
        if (loginButton) loginButton.style.display = isLoggedIn ? 'none' : 'inline-block';
        if (userInfo) userInfo.style.display = isLoggedIn ? 'flex' : 'none';
        if (userDisplayName) userDisplayName.textContent = userData.display_name || 'Logged In';
        if (logoutButton) logoutButton.style.display = isLoggedIn ? 'inline-block' : 'none';
        if (!isLoggedIn) {
            if (resultContainer) { resultContainer.style.display = 'none'; resultContainer.innerHTML = ''; }
            if (errorContainer) errorContainer.style.display = 'none';
        }
        if (loadingContainer) loadingContainer.style.display = 'none';
    }

    // Checks if user is authenticated with server
    async function checkAuthStatus() {
        try {
            const response = await fetch('/api/status');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            updateUIForAuthState(data.authenticated, data.user || {});
        } catch (error) {
            console.error('Error checking auth status:', error);
            updateUIForAuthState(false);
            if (errorMessage && errorContainer) {
                 errorMessage.textContent = 'Could not connect to server.';
                 errorContainer.style.display = 'block';
            }
        }
    }

    // Starts Spotify OAuth flow
    async function initiateLogin() {
        try {
            const response = await fetch('/api/login');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            if (data.auth_url) { window.location.href = data.auth_url; }
            else { throw new Error('No auth URL received.'); }
        } catch (error) {
            console.error('Error initiating login:', error);
             if (errorMessage && errorContainer) {
                 errorMessage.textContent = 'Could not initiate login.';
                 errorContainer.style.display = 'block';
             }
        }
    }

    // Logs out user and clears session
    async function logoutUser() {
        try {
            const response = await fetch('/api/logout');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            if (data.success) { updateUIForAuthState(false); }
            else { throw new Error('Logout failed.'); }
        } catch (error) {
            console.error('Error logging out:', error);
            updateUIForAuthState(false);
        }
    }

    // Sanitizes strings for safe HTML insertion
     function escapeHtml(unsafe) {
        if (typeof unsafe !== 'string') { return unsafe === null || unsafe === undefined ? '' : String(unsafe); }
        return unsafe.replace(/&/g, "&").replace(/</g, "<").replace(/>/g, ">").replace(/"/g, "'").replace(/'/g, '"');
     }

    // Creates HTML for individual track list items
    function createTrackListItem(track, playlistId) {
        const listItem = document.createElement('li');
        listItem.dataset.trackUri = escapeHtml(track.uri);
        listItem.innerHTML = `
            <span class="track-info">${escapeHtml(track.name)} by ${escapeHtml(Array.isArray(track.artists) ? track.artists.join(', ') : '')}</span>
            <button class="button button-remove remove-track-btn"
                    data-track-uri="${escapeHtml(track.uri)}"
                    data-playlist-id="${escapeHtml(playlistId)}"
                    title="Remove this track">
                ×
            </button>
        `;
        return listItem;
    }

    // Renders playlist creation success view
    function renderSuccess(data) {
        if (!resultContainer) { console.error("Result container not found"); return; }
        resultContainer.innerHTML = '';
        if (errorContainer) errorContainer.style.display = 'none';

        if (!data || !data.playlist || !data.playlist.url || !data.playlist.id) {
            console.error("RenderSuccess playlist data missing/incomplete:", data);
            renderError({ error: "Incomplete playlist data from server." });
            return;
        }

        const playlist = data.playlist;
        const resultCard = document.createElement('div');
        resultCard.className = 'card playlist-result-card';
        resultCard.dataset.playlistId = playlist.id;

        let coverImageHtml = playlist.cover_image_url
            ? `<img src="${escapeHtml(playlist.cover_image_url)}" alt="Playlist Cover Art" class="playlist-cover">`
            : '<div class="playlist-cover placeholder-cover">🎵</div>';

        // Generate track preview list if tracks exist
        let tracksPreviewHtml = '';
        if (playlist.tracks_preview && Array.isArray(playlist.tracks_preview) && playlist.tracks_preview.length > 0) {
            tracksPreviewHtml = `
                <div class="playlist-tracks-preview">
                    <h4>Featuring tracks like:</h4>
                    <ul id="playlist-tracks-list">
                        ${playlist.tracks_preview.map(track => createTrackListItem(track, playlist.id).outerHTML).join('')}
                    </ul>
                    <div class="track-list-actions">
                         <div class="track-list-loader" style="display: none;"></div>
                         <button class="button button-secondary-dark show-all-tracks-btn" data-playlist-id="${escapeHtml(playlist.id)}">
                             Show All Tracks
                         </button>
                     </div>
                </div>`;
        }

        resultCard.innerHTML = `
            <h2>Your Playlist is Ready!</h2>
            <div class="playlist-details">
                ${coverImageHtml}
                <div class="playlist-info">
                    <h3 id="playlist-title">${escapeHtml(playlist.name || 'Unnamed Playlist')}</h3>
                    <p id="playlist-description">${escapeHtml(playlist.description || 'No description.')}</p>
                    <p class="track-count" id="playlist-track-count-display">
                       ${playlist.track_count !== undefined ? `<span>${playlist.track_count}</span> tracks` : ''}
                    </p>
                    <a href="${escapeHtml(playlist.url)}" target="_blank" rel="noopener noreferrer" class="button button-spotify">Open in Spotify</a>
                </div>
            </div>
            ${tracksPreviewHtml}
        `;
        resultContainer.appendChild(resultCard);

        // Add explanation of how playlist was created
        if (data.agent_steps_explanation) {
            const agentStepsCard = document.createElement('div');
            agentStepsCard.className = 'card agent-steps-card';
            const stepsHeader = document.createElement('h3'); stepsHeader.textContent = 'How It Was Made';
            agentStepsCard.appendChild(stepsHeader);
            const stepsDiv = document.createElement('div'); stepsDiv.id = 'agent-steps';
            stepsDiv.style.cssText = 'font-family: monospace; font-size: 0.85rem; color: var(--spotify-text-grey); background-color: var(--spotify-black); padding: 15px; border-radius: 4px; white-space: pre-wrap; max-height: 300px; overflow-y: auto;';
            stepsDiv.textContent = data.agent_steps_explanation;
            agentStepsCard.appendChild(stepsDiv);
            resultContainer.appendChild(agentStepsCard);
        }

        resultContainer.style.display = 'block';
        if (resultContainer.scrollIntoView) { resultContainer.scrollIntoView({ behavior: 'smooth' }); }
    }

    // Renders generic success message from agent
    function renderGenericSuccess(data) {
        if (!resultContainer) { console.error("Result container not found"); return; }
        resultContainer.innerHTML = '';
        if (errorContainer) errorContainer.style.display = 'none';
        if (!data || !data.message) { console.error("GenericSuccess message missing:", data); renderError({ error: "Incomplete success data." }); return; }

        const genericResultCard = document.createElement('div');
        genericResultCard.className = 'card generic-result-card';
        const originalPromptForButton = originalUserPrompt;

        genericResultCard.innerHTML = `
            <h2>TuneSmith Found This:</h2>
            <div class="agent-response-text" style="white-space: pre-wrap; margin-bottom: 20px;">${escapeHtml(data.message)}</div>
            <button id="force-create-playlist-btn" class="button button-secondary-dark" data-original-prompt="${escapeHtml(originalPromptForButton)}">Create Playlist from This Description</button>
        `;
        resultContainer.appendChild(genericResultCard);

        // Add explanation steps if available
        if (data.agent_steps_explanation) {
            const agentStepsCard = document.createElement('div');
            agentStepsCard.className = 'card agent-steps-card';
            const stepsHeader = document.createElement('h3'); stepsHeader.textContent = 'How It Was Done';
            agentStepsCard.appendChild(stepsHeader);
            const stepsDiv = document.createElement('div'); stepsDiv.id = 'agent-steps';
            stepsDiv.style.cssText = 'font-family: monospace; font-size: 0.85rem; color: var(--spotify-text-grey); background-color: var(--spotify-black); padding: 15px; border-radius: 4px; white-space: pre-wrap; max-height: 300px; overflow-y: auto;';
            stepsDiv.textContent = data.agent_steps_explanation;
            agentStepsCard.appendChild(stepsDiv);
            resultContainer.appendChild(agentStepsCard);
        }

        resultContainer.style.display = 'block';
        if (resultContainer.scrollIntoView) { resultContainer.scrollIntoView({ behavior: 'smooth' }); }
    }

    // Displays error messages to user
    function renderError(errorData) {
        if (!resultContainer || !errorContainer || !errorMessage) { console.error("UI elements for error rendering missing"); return; }
        resultContainer.style.display = 'none'; resultContainer.innerHTML = '';
        let message = 'An unknown error occurred.';
        if (typeof errorData === 'string') { message = errorData; }
        else if (errorData?.error) { message = errorData.error; }
        else if (errorData?.message) { message = errorData.message; }
        else if (errorData?.output) { message = errorData.output; }
        errorMessage.textContent = escapeHtml(message);
        errorContainer.style.display = 'block';
    }

    // Sends user request to backend API
     async function processApiRequest(promptToSend) {
        originalUserPrompt = promptToSend;
        if (submitButton) { submitButton.disabled = true; submitButton.textContent = 'Working...'; }
        const forceCreateBtn = document.getElementById('force-create-playlist-btn'); if (forceCreateBtn) forceCreateBtn.disabled = true;
        const showAllBtn = document.querySelector('.show-all-tracks-btn'); if (showAllBtn) showAllBtn.disabled = true;
        if (loadingContainer) loadingContainer.style.display = 'block';
        if (errorContainer) errorContainer.style.display = 'none';
        if (resultContainer) { resultContainer.style.display = 'none'; resultContainer.innerHTML = ''; }

        try {
            const response = await fetch('/api/request', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ request: promptToSend }), });
            const data = await response.json();
            if (!response.ok) { throw data || new Error(`HTTP error ${response.status}`); }
            if (data?.success === true) {
                if (data.type === "playlist" && data.playlist) { renderSuccess(data); }
                else if (data.type === "generic" && data.message) { renderGenericSuccess(data); }
                else { console.warn("Success/unexpected format:", data); renderError({ error: "Unexpected success format." }); }
            } else { console.warn("Backend failure/structure:", data); throw data || { error: "Unspecified server error." }; }
        } catch (error) {
            console.error('Error processing request:', error);
            renderError(error || { error: 'Communication error.' });
        } finally {
            if (submitButton) { submitButton.disabled = false; submitButton.textContent = submitButtonText; }
            if (forceCreateBtn) forceCreateBtn.disabled = false;
            if (showAllBtn) showAllBtn.disabled = false;
            if (loadingContainer) loadingContainer.style.display = 'none';
        }
     }

    // Removes track from playlist
     async function handleRemoveTrack(playlistId, trackUri, listItemToRemove) {
         console.log(`Removing track ${trackUri} from ${playlistId}`);
         const removeButton = listItemToRemove.querySelector('.remove-track-btn');
         if(removeButton) { removeButton.disabled = true; removeButton.innerHTML = '...'; }

         try {
            const response = await fetch('/api/playlist/remove_track', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ playlist_id: playlistId, track_uri: trackUri })
            });
            const data = await response.json();
            if (!response.ok || !data.success) { throw data || new Error(`HTTP error ${response.status}`); }
            console.log("Track removed", data);
            listItemToRemove.remove();
            const trackCountDisplay = document.getElementById('playlist-track-count-display');
            if (trackCountDisplay && data.new_track_count !== undefined) {
                 trackCountDisplay.innerHTML = `<span>${data.new_track_count}</span> tracks`;
            }

         } catch (error) {
            console.error('Error removing track:', error);
            alert(`Failed to remove track: ${error?.error || error?.message || 'Unknown error'}`);
            if(removeButton) { removeButton.disabled = false; removeButton.innerHTML = '×'; }
         }
     }

    // Fetches and displays all tracks in playlist
     async function handleShowAllTracks(playlistId, trackListUl, showAllButton, loaderElement) {
        console.log(`Fetching all tracks for ${playlistId}`);
        showAllButton.style.display = 'none';
        loaderElement.style.display = 'inline-block';
        loaderElement.textContent = 'Loading all tracks...';

        try {
            const response = await fetch(`/api/playlist/items/${playlistId}`);
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw data || new Error(`HTTP error ${response.status}`);
            }

            if (data.tracks && Array.isArray(data.tracks)) {
                trackListUl.innerHTML = '';
                data.tracks.forEach(track => {
                    const listItem = createTrackListItem(track, playlistId);
                    trackListUl.appendChild(listItem);
                });
                const trackCountDisplay = document.getElementById('playlist-track-count-display');
                 if (trackCountDisplay) {
                      trackCountDisplay.innerHTML = `<span>${data.tracks.length}</span> tracks`;
                 }

            } else {
                 throw { error: "Received invalid track data from server." };
            }

        } catch (error) {
             console.error('Error fetching all tracks:', error);
             trackListUl.innerHTML += `<li style="color: var(--error-red); font-style: italic;">Error loading all tracks: ${escapeHtml(error?.error || error?.message || 'Unknown error')}</li>`;
             showAllButton.style.display = 'block';
        } finally {
             loaderElement.style.display = 'none';
        }
     }

    // Set up event listeners
    if (loginButton) loginButton.addEventListener('click', initiateLogin);
    if (logoutButton) logoutButton.addEventListener('click', logoutUser);

    if (requestForm) {
        requestForm.addEventListener('submit', (event) => {
            event.preventDefault(); if (!userRequestInput) return;
            const userInput = userRequestInput.value.trim();
            if (!userInput) { alert('Describe music.'); userRequestInput.focus(); return; }
            processApiRequest(userInput);
        });
    }

    // Handle clicks in result container
    if (resultContainer) {
        resultContainer.addEventListener('click', (event) => {
            const target = event.target;
            // Handle playlist creation from description
            if (target && target.id === 'force-create-playlist-btn') {
                const originalPrompt = target.dataset.originalPrompt;
                if (originalPrompt) {
                    const creationPrompt = `Create a playlist based on my previous request: "${originalPrompt}"`;
                    processApiRequest(creationPrompt);
                } else { console.error("Missing original prompt."); renderError({error: "Missing original prompt."}); }
            }
            // Handle track removal
            else if (target && target.classList.contains('remove-track-btn')) {
                const trackUri = target.dataset.trackUri; const playlistId = target.dataset.playlistId;
                const listItem = target.closest('li');
                if (trackUri && playlistId && listItem) { handleRemoveTrack(playlistId, trackUri, listItem); }
                else { console.error("Missing data for track removal."); }
            }
            // Handle showing all tracks
             else if (target && target.classList.contains('show-all-tracks-btn')) {
                 const playlistId = target.dataset.playlistId;
                 const trackListUl = target.closest('.playlist-tracks-preview')?.querySelector('#playlist-tracks-list');
                 const loaderElement = target.closest('.track-list-actions')?.querySelector('.track-list-loader');

                 if (playlistId && trackListUl && loaderElement) {
                    handleShowAllTracks(playlistId, trackListUl, target, loaderElement);
                 } else {
                     console.error("Could not find playlist ID, track list UL, or loader for 'Show All'.");
                 }
             }
        });
    }

    // Check auth status on page load
    checkAuthStatus();

});