document.addEventListener("DOMContentLoaded", () => {
	// Check authentication status
	checkAuthStatus();

	// Set up event listeners
	document.getElementById("login-button").addEventListener("click", login);
	document
		.getElementById("submit-button")
		.addEventListener("click", submitRequest);

	// Allow pressing Enter to submit
	document
		.getElementById("user-request")
		.addEventListener("keypress", (e) => {
			if (e.key === "Enter") {
				submitRequest();
			}
		});
});

async function checkAuthStatus() {
	try {
		const response = await fetch("/api/status");
		const data = await response.json();

		if (data.authenticated) {
			// User is authenticated, show app
			showApp();
		} else {
			// User is not authenticated, show login
			showLogin();
		}
	} catch (error) {
		console.error("Error checking authentication status:", error);
		showLogin();
	}
}

function showLogin() {
	// Hide app container
	document.getElementById("app-container").style.display = "none";
	document.getElementById("result-container").style.display = "none";

	// Show login container
	document.getElementById("login-container").style.display = "block";

	// Update auth status
	document.getElementById("auth-status").innerHTML = "";
}

function showApp() {
	// Hide login container
	document.getElementById("login-container").style.display = "none";

	// Show app container
	document.getElementById("app-container").style.display = "block";

	// Update auth status
	document.getElementById("auth-status").innerHTML =
		'<button id="logout-button" class="button secondary">Logout</button>';
	document.getElementById("logout-button").addEventListener("click", logout);
}

async function login() {
	try {
		const response = await fetch("/api/login");
		const data = await response.json();

		if (data.auth_url) {
			// Redirect to Spotify authorization page
			window.location.href = data.auth_url;
		} else {
			console.error("No authorization URL provided");
		}
	} catch (error) {
		console.error("Error initiating login:", error);
	}
}

async function logout() {
	try {
		const response = await fetch("/api/logout");
		const data = await response.json();

		if (data.success) {
			// User was logged out successfully
			showLogin();
		} else {
			console.error("Error logging out");
		}
	} catch (error) {
		console.error("Error logging out:", error);
	}
}

async function submitRequest() {
	// Get user request
	const userRequest = document.getElementById("user-request").value.trim();

	if (!userRequest) {
		alert("Please enter a request");
		return;
	}

	try {
		// Show loading spinner
		document.getElementById("loading").style.display = "block";
		document.getElementById("result-container").style.display = "none";

		// Send request to server
		const response = await fetch("/api/request", {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
			},
			body: JSON.stringify({ request: userRequest }),
		});

		const data = await response.json();

		// Hide loading spinner
		document.getElementById("loading").style.display = "none";

		// Process and display results
		if (data.error) {
			alert(`Error: ${data.error}`);
		} else {
			displayResults(data);
		}
	} catch (error) {
		console.error("Error submitting request:", error);
		document.getElementById("loading").style.display = "none";
		alert("An error occurred. Please try again.");
	}
}

function displayResults(data) {
	// Display the output
	const playlistResultContainer = document.getElementById("playlist-result");
	playlistResultContainer.innerHTML = data.output;

	// Display agent steps
	const agentStepsContainer = document.getElementById("agent-steps");
	agentStepsContainer.innerHTML = "";

	if (data.steps && data.steps.length > 0) {
		data.steps.forEach((step, index) => {
			const stepElement = document.createElement("div");
			stepElement.classList.add("step");

			const thought =
				data.thoughts && data.thoughts[index]
					? data.thoughts[index]
					: "No thought recorded";

			const action = step[0].tool;
			const result =
				typeof step[1] === "object"
					? JSON.stringify(step[1], null, 2)
					: step[1];

			stepElement.innerHTML = `
                <div class="step-header">
                    <span>Step ${index + 1}</span>
                </div>
                <div class="step-thought">${thought}</div>
                <div class="step-action">Action: ${action}</div>
                <pre class="step-result">${result}</pre>
            `;

			agentStepsContainer.appendChild(stepElement);
		});
	}

	// Extract playlist information
	let playlistInfo = null;
	if (data.steps) {
		for (const step of data.steps) {
			if (step[1] && typeof step[1] === "string") {
				try {
					const result = JSON.parse(step[1]);
					if (result.external_urls && result.external_urls.spotify) {
						playlistInfo = result;
						break;
					}
				} catch (e) {
					// Not a JSON string or not a playlist result
				}
			}
		}
	}

	// If we found playlist info, add a nice UI card for it
	if (playlistInfo) {
		const playlistCard = document.createElement("div");
		playlistCard.classList.add("playlist-card");

		playlistCard.innerHTML = `
            <div class="playlist-info">
                <div class="playlist-title">${
					playlistInfo.name || "Your Playlist"
				}</div>
                <div class="playlist-meta">${
					playlistInfo.tracks?.total || 0
				} tracks</div>
                <div class="playlist-actions">
                    <a href="${
						playlistInfo.external_urls?.spotify
					}" target="_blank" class="button primary">
                        Open in Spotify
                    </a>
                </div>
            </div>
        `;

		playlistResultContainer.prepend(playlistCard);
	}

	// Show result container
	document.getElementById("result-container").style.display = "block";
}
