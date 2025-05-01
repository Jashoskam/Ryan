// Global variable to control speech output
let speechEnabled = true;

// Base URL for your backend API
// Make sure this matches the host and port your FastAPI app is running on
const API_BASE_URL = "http://127.0.0.1:8000"; // Corrected IP address

// Variables for resizing functionality (for the creative sidebar)
let resizingElement = null; // This will be the #creative-sidebar
let initialMouseX = 0;
let initialWidth = 0; // Only need initialWidth for horizontal resize

// Array to store all generated creative outputs
let creativeOutputs = [];
// Index of the currently displayed creative output
let currentCreativeOutputIndex = -1;

// Variables for Orb animation control
let orbAnimationIntensity = 0; // 0 for idle, > 0 for active
let orbAnimationTimer = null; // Timer to reduce intensity over time
let isErrorState = false; // New: Flag to indicate if the orb should show an error state

// Three.js variables - declared in a scope accessible to animation functions
let scene, camera, renderer, orb, initialPositions; // Removed orbMaterial as it will be PointsMaterial
let orbMaterial; // Declare orbMaterial here
// Using a blue color for the particle orb
let initialOrbColor = new THREE.Color(0x0077ff); // A vibrant blue
let errorOrbColor = new THREE.Color(0xff0000); // Red color for error state

// --- Variables for Logs Pagination ---
let logsBoxElement = null; // Reference to the logs box element
let logOffset = 0; // Start at the beginning
const logLimit = 50; // Number of log entries to fetch per request (matches backend default)
let isFetchingLogs = false; // Flag to prevent multiple simultaneous fetch calls
let allLogsLoaded = false; // Flag to indicate if all logs have been loaded

// --- Functions for Orb Animation ---

// Function to trigger orb animation on response, now accepts isError flag
function triggerOrbAnimation(isError = false) {
    console.log(`Triggering orb animation. isError: ${isError}`);
    orbAnimationIntensity = 1; // Start at full intensity
    isErrorState = isError; // Set the error state flag

    if (orbMaterial) {
        if (isError) {
            orbMaterial.color.set(errorOrbColor); // Set color to red on error
            // Optionally increase size temporarily for a pulse effect on error
            orbMaterial.size = 0.1; // Larger points for glow
        } else {
            orbMaterial.color.set(0x3399ff); // Set color to brighter blue on success
            orbMaterial.size = 0.05; // Reset size on success
        }
    }

    // Clear any existing timer to prevent overlapping animations
    if (orbAnimationTimer) {
        clearTimeout(orbAnimationTimer);
    }
    // Set a timer to gradually reduce intensity and fade color/size over a few seconds
    // Adjust the duration (e.g., 2000ms = 2 seconds) and reduction steps (0.05 every 50ms)
    // to control how quickly the animation fades
    orbAnimationTimer = setTimeout(reduceOrbAnimationIntensity, 50); // Start reducing after a short delay
}

// Function to gradually reduce orb animation intensity and fade color/size
function reduceOrbAnimationIntensity() {
    if (orbAnimationIntensity > 0) {
        // Reduce intensity by a small amount
        orbAnimationIntensity = Math.max(0, orbAnimationIntensity - 0.05);

        if (orbMaterial) {
            if (isErrorState) {
                 // Interpolate color from red back to the initial blue
                 orbMaterial.color.lerpColors(initialOrbColor, errorOrbColor, orbAnimationIntensity);
                 // Interpolate size back to normal
                 orbMaterial.size = 0.05 + (0.1 - 0.05) * orbAnimationIntensity;
            } else {
                 // Interpolate color from the triggered brighter blue back to the initial blue
                 orbMaterial.color.lerpColors(initialOrbColor, new THREE.Color(0x3399ff), orbAnimationIntensity);
                 // Interpolate size back to normal (if it was temporarily increased on success)
                 // In this case, we set size back to 0.05 immediately on success trigger, so no size interpolation needed here unless we change that.
            }
        }

        // Continue reducing until intensity is 0
        orbAnimationTimer = setTimeout(reduceOrbAnimationIntensity, 50); // Continue reducing every 50ms
    } else {
        orbAnimationIntensity = 0; // Ensure it hits zero
        orbAnimationTimer = null; // Clear the timer
        isErrorState = false; // Reset error state when animation finishes
        // Ensure the color and size are set back to the initial state at the end
        if (orbMaterial) {
             orbMaterial.color.set(initialOrbColor);
             orbMaterial.size = 0.05; // Ensure size is reset
        }
         console.log("Orb animation finished. State reset.");
    }
}


// Initialize the page once the DOM is fully loaded
window.addEventListener("DOMContentLoaded", () => {
    // Set up the toggle switch for enabling/disabling speech
    setupSpeechToggle();

    // Setup sidebar toggle - Attach event listener here instead of onclick in HTML
    const sidebarToggleButton = document.getElementById('toggle-sidebar');
    if (sidebarToggleButton) {
        sidebarToggleButton.addEventListener('click', toggleSidebar);
    } else {
        console.warn("Sidebar toggle button with ID 'toggle-sidebar' not found.");
    }

    // Setup for showing different sections (like chat, logs, memory, creative)
    // based on button clicks - Attach event listeners here instead of onclick in HTML
    const chatButton = document.getElementById('chat-button');
    const logsButton = document.getElementById('logs-button');
    const settingsButton = document.getElementById('settings-button');
    const memoryButton = document.getElementById('memory-button');

    // Event listeners for sidebar buttons
    if (chatButton) chatButton.addEventListener('click', () => showSection('chat-container'));
    if (logsButton) logsButton.addEventListener('click', () => {
        showSection('logs-container');
        // When showing the logs section, reset pagination and fetch the first page
        logOffset = 0;
        allLogsLoaded = false;
        // Clear existing logs before fetching the first page
        if (logsBoxElement) logsBoxElement.innerHTML = '';
        fetchLogs(logOffset, logLimit);
    });
    if (settingsButton) settingsButton.addEventListener('click', () => showSection('settings-container'));
     if (memoryButton) memoryButton.addEventListener('click', () => {
        showSection('memory-container');
        fetchMemory(); // Fetch memory when the memory section is shown
    });

    // Get the chat input field
    const inputField = document.getElementById("chat-input");
    // Attach keypress listener to the input field instead of onkeypress in HTML
    if (inputField) {
        inputField.addEventListener("keypress", handleKeyPress);
    } else {
         console.warn("Chat input element with ID 'chat-input' not found.");
    }

    // Attach click listener to the send button (assuming it has an onclick in HTML)
    // If your send button has an ID, it's better to attach the listener here:
    // Removed send button event listener as the button was removed from HTML
    // const sendButton = document.querySelector('.input-container button');
    // if (sendButton) {
    //     sendButton.addEventListener('click', sendMessage);
    // } else {
    //     console.warn("Send button not found.");
    // }

    // Add mousedown listener to the creative sidebar's resize handle
    const creativeResizeHandle = document.querySelector('#creative-sidebar .resize-handle-creative');
    if (creativeResizeHandle) {
        creativeResizeHandle.addEventListener('mousedown', startResize);
    } else {
         console.warn("Creative sidebar resize handle not found.");
    }

    // Add global mousemove and mouseup listeners for resizing
    document.addEventListener('mousemove', resizeElement);
    document.addEventListener('mouseup', stopResize);

    // Add event listener for the new close button on the creative sidebar
    const closeCreativeSidebarButton = document.getElementById('close-creative-sidebar');
    if (closeCreativeSidebarButton) {
        closeCreativeSidebarButton.addEventListener('click', hideCreativeSidebar);
    } else {
         console.warn("Close creative sidebar button with ID 'close-creative-sidebar' not found.");
    }

    // --- Attach listener for the creative output dropdown ---
    const creativeOutputSelect = document.getElementById('creative-output-select');
    if (creativeOutputSelect) {
        creativeOutputSelect.addEventListener('change', handleCreativeOutputSelectChange);
    } else {
         console.warn("Creative output select element with ID 'creative-output-select' not found.");
    }

    // --- Attach listeners for the per-block creative sidebar buttons (now operate on active) ---
    const saveActiveButton = document.getElementById('save-active-creative');
    const copyActiveButton = document.getElementById('copy-active-creative');
    const clearActiveButton = document.getElementById('clear-active-creative');
    // Removed the clearAllButton listener as the button is removed from HTML


    if (saveActiveButton) saveActiveButton.addEventListener('click', saveActiveCreativeOutput);
    if (copyActiveButton) copyActiveButton.addEventListener('click', copyActiveCreativeOutput);
    if (clearActiveButton) clearActiveButton.addEventListener('click', clearActiveCreativeOutput);
    // The clearAllCreativeOutputs function is still available but not tied to a button in this structure


    // Ensure the chat section is visible on load and creative sidebar is hidden
    showSection('chat-container'); // Show the chat section by default
    hideCreativeSidebar();

    // --- Get reference to logs box and add scroll listener ---
    logsBoxElement = document.getElementById("logs-box");
    if (logsBoxElement) {
        logsBoxElement.addEventListener('scroll', handleLogsScroll);
        // Add event listener for the refresh button
        const refreshLogsButton = document.getElementById('refresh-logs-button');
        if (refreshLogsButton) {
            refreshLogsButton.addEventListener('click', () => {
                // Reset pagination and fetch the first page
                logOffset = 0;
                allLogsLoaded = false;
                // Clear existing logs before fetching the first page
                logsBoxElement.innerHTML = '';
                fetchLogs(logOffset, logLimit);
            });
        } else {
            console.warn("Refresh logs button with ID 'refresh-logs-button' not found.");
        }

    } else {
         console.warn("Logs box element with ID 'logs-box' not found. Logs pagination will not work.");
    }


    // --- Three.js AI Orb Animation Setup ---
    // This block runs after the DOM is fully loaded, specifically for the Three.js setup.
    // Get the orb container, which is now inside the sidebar
    const orbContainer = document.getElementById('ai-orb');
      if (!orbContainer) {
          console.warn("AI Orb container element with ID 'ai-orb' not found. Three.js animation will not run.");
          // Don't return here, other parts of the script should still run
      } else {
           // Check if the container has dimensions before setting up Three.js
           // This check is helpful for debugging but doesn't prevent setup
           if (orbContainer.offsetWidth === 0 || orbContainer.offsetHeight === 0) {
               console.warn("AI Orb container has zero dimensions. Three.js animation might not be visible.");
           }

           // Create a Three.js scene
           scene = new THREE.Scene(); // Assign to global variable
           // Create a perspective camera
           camera = new THREE.PerspectiveCamera(75, orbContainer.offsetWidth / orbContainer.offsetHeight, 0.1, 1000); // Assign to global variable

           // Create a WebGL renderer with antialiasing and transparency
           renderer = new THREE.WebGLRenderer({ // Assign to global variable
               antialias: true,
               alpha: true // Allow transparency so the background shows through
           });
           // Set the size of the renderer to match the container
           renderer.setSize(orbContainer.offsetWidth, orbContainer.offsetHeight);
           // Append the renderer's canvas to the orb container
           orbContainer.appendChild(renderer.domElement);

           // Create a sphere geometry - maybe with more vertices for smoother distortion
           // Increased segments for a more detailed surface to distort
           const geometry = new THREE.SphereGeometry(4, 128, 128); // Radius 4, with 128 segments

           // Create a PointsMaterial for a particle-like appearance
           orbMaterial = new THREE.PointsMaterial({ // Assign to global variable
               color: initialOrbColor, // Use the initial blue color
               size: 0.05, // Size of each point (adjust as needed)
               transparent: true,
               opacity: 0.7, // Adjust opacity for a cloud-like effect
               blending: THREE.AdditiveBlending // Additive blending can make points appear brighter where they overlap
           });


           // Create a Points object (particle system)
           orb = new THREE.Points(geometry, orbMaterial); // Assign to global variable
           // Add the orb to the scene
           scene.add(orb);

           // Set the camera's initial position
           camera.position.z = 10; // Position the camera 10 units back on the Z axis

           // Clone original vertex positions to use as a base for distortion
           initialPositions = geometry.attributes.position.array.slice(); // Assign to global variable

           // Vertex colors setup (optional for PointsMaterial, but can be used for variations)
           // Keeping this for now, but the primary color is set by orbMaterial.color
           const colors = [];
           const positionAttribute = geometry.attributes.position; // Get the position attribute
           const tempColor = new THREE.Color(); // Temporary color object
           for (let i = 0; i < positionAttribute.count; i++) {
               // Get the vertex position as a Vector3
               const vertex = new THREE.Vector3().fromBufferAttribute(positionAttribute, i);
               // Set color based on the vertex's Y position (creating a vertical gradient)
               // Using shades of blue for the orb color
               // Interpolate between a darker blue and the initial blue
               const blueShade = 0.5 + 0.5 * (vertex.y / 4); // Vary shade based on Y position
               tempColor.setRGB(0, 0, blueShade); // Set R and G to 0, vary B
               colors.push(tempColor.r, tempColor.g, tempColor.b);
           }
           // Set the 'color' attribute for the geometry
           geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));

           // Audio setup for potential microphone input to drive animation (kept for possibility)
           let analyser, dataArray, audioContext, hasMic = false;

           // Function to distort the sphere's vertices based on audio frequency data or simulated data
           // Modified to apply more significant and fluid distortion
           function distortSphere(data, baseAmplitude, responseAmplitude) {
               const positions = geometry.attributes.position.array; // Get the current vertex positions
               const time = Date.now() * 0.001; // Time variable for animation

               // Calculate the current effective amplitude based on animation intensity
               const currentAmplitude = baseAmplitude + orbAnimationIntensity * (responseAmplitude - baseAmplitude);

               // Use a simple noise-like function for distortion
               // You might need a more complex noise function (like Perlin noise) for better results
               // For simplicity, let's use combined sine waves and randomness
               const distortionScale = currentAmplitude * 0.8; // Slightly increased Scale for more pronounced distortion

               // Iterate through each vertex (3 components per vertex: x, y, z)
               for (let i = 0; i < positions.length; i += 3) {
                   const ix = i;
                   const iy = i + 1;
                   const iz = i + 2;

                   // Get the original, undistorted position of the vertex
                   const ox = initialPositions[ix];
                   const oy = initialPositions[iy];
                   const oz = initialPositions[iz];

                   // Calculate distortion for each axis using time, position, and data
                   // Combine multiple sine waves with different frequencies and phases for more complexity
                   // Added more terms and varied frequencies/phases further
                   const distortionX = (
                       Math.sin(time * 1.5 + ox * 1.0 + oy * 0.7) * 0.7 +
                       Math.sin(time * 1.0 + oy * 1.2 + oz * 0.9) * 0.5 +
                       Math.sin(time * 1.8 + ox * 0.5 + oz * 1.4) * 0.4 +
                       Math.sin(time * 0.9 + ox * 1.3 + oy * 0.6) * 0.3
                   ) * distortionScale;

                   const distortionY = (
                       Math.cos(time * 1.8 + oy * 1.0 + oz * 0.8) * 0.8 +
                       Math.cos(time * 1.2 + ox * 1.1 + oz * 0.5) * 0.6 +
                       Math.cos(time * 1.0 + oy * 0.6 + ox * 1.4) * 0.5 +
                       Math.cos(time * 1.6 + oy * 1.4 + oz * 0.9) * 0.4
                   ) * distortionScale;

                   const distortionZ = (
                       Math.sin(time * 1.3 + oz * 1.1 + ox * 0.6) * 0.9 +
                       Math.sin(time * 1.6 + ox * 0.8 + oy * 1.3) * 0.7 +
                       Math.sin(time * 0.8 + oz * 1.5 + oy * 1.0) * 0.5 +
                       Math.sin(time * 1.1 + oz * 0.7 + ox * 1.2) * 0.4
                   ) * distortionScale;


                   // Optionally incorporate audio data (if available)
                   let audioDistortion = 0;
                   if (data && data.length > 0) {
                        const dataIndex = Math.floor((i / 3) % data.length);
                        audioDistortion = (data[dataIndex] || 0) / 256 * currentAmplitude * 0.4; // Slightly increased contribution from audio
                   }

                   // Add a small, subtle random displacement for a twinkling/jittering effect
                   const randomDisplacement = (Math.random() - 0.5) * 0.1 * currentAmplitude; // Random value scaled by intensity

                   // Apply distortion along the normal vector
                   const normal = new THREE.Vector3(ox, oy, oz).normalize();
                   positions[ix] = ox + normal.x * (distortionX + audioDistortion + randomDisplacement);
                   positions[iy] = oy + normal.y * (distortionY + audioDistortion + randomDisplacement);
                   positions[iz] = oz + normal.z * (distortionZ + audioDistortion + randomDisplacement);
               }

               // Indicate that the position attribute needs to be updated in the GPU
               geometry.attributes.position.needsUpdate = true;
           }


           // The main animation loop for the Three.js scene
           function animate() {
               // Request the next animation frame
               requestAnimationFrame(animate);

               let dataToDistort = null; // Data for distortion
               const baseAmplitude = 0.9; // Base distortion amplitude for idle (Increased)
               const responseAmplitude = 2.5; // Higher distortion amplitude for response (Increased)


               // Check if text-to-speech is currently speaking
               if (speechSynthesis.speaking) {
                   // --- Generate Simulated Data for Speech Animation ---
                   const speechTime = Date.now() * 0.004; // Slightly faster time variable for speed
                   // Create a data array matching the number of vertices
                   dataToDistort = new Uint8Array(geometry.attributes.position.count / 3);
                   const amplitude = 80; // Increased amplitude
                   const frequency = 0.15; // Increased frequency

                   for (let i = 0; i < dataToDistort.length; i++) {
                       // Generate data based on a sine wave pattern
                       dataToDistort[i] = 128 + Math.sin(speechTime + i * frequency) * amplitude;
                   }
                    // Use higher amplitudes for distortion when speaking
                   distortSphere(dataToDistort, 1.5, 3.0);


               } else if (hasMic && analyser) {
                   // --- Use Real Mic Data if Available (and not speaking) ---
                   analyser.getByteFrequencyData(dataArray);
                   dataToDistort = dataArray;
                   distortSphere(dataToDistort, baseAmplitude, responseAmplitude); // Use real data
               } else {
                   // --- Use Fake Data for Idle Animation (when not speaking and no mic) ---
                   // No need to generate fake data array here, distortSphere uses internal time/position
                   distortSphere(null, baseAmplitude, responseAmplitude); // Pass null for data, use base/response amplitudes
               }


               // Rotate the orb (rotation continues regardless of speech/audio/response)
               orb.rotation.y += 0.0015; // Slightly increased rotation speed
               orb.rotation.x += 0.0008; // Slightly increased rotation speed

               // Render the scene from the camera's perspective
               renderer.render(scene, camera);
           }

           // Handle window resizing to keep the Three.js canvas responsive
           window.addEventListener('resize', () => {
               // Get the updated dimensions of the orb container
               const updatedOrbContainer = document.getElementById('ai-orb');
               if (updatedOrbContainer && renderer && camera) { // Add checks for renderer and camera
                   // Update camera aspect ratio
                   camera.aspect = updatedOrbContainer.offsetWidth / updatedOrbContainer.offsetHeight;
                   // Update camera projection matrix
                   camera.updateProjectionMatrix();
                   // Update renderer size
                   renderer.setSize(updatedOrbContainer.offsetWidth, updatedOrbContainer.offsetHeight);
               } else {
                   console.warn("Orb container, renderer, or camera not found during resize.");
               }
           });

           // Start the animation loop
           animate();

           // --- Microphone Access and Audio Analysis Setup ---
           // This part attempts to get microphone access and set up the audio analyser.
           // It should ideally be triggered by a user action (like clicking the mic button)
           // due to browser security requirements for microphone access.
           // Leaving it commented out here to avoid prompting for mic access on every page load.
           // If you want the orb to react to the mic when *not' speaking, uncomment the line below
           // or call it from a user event handler (e.g., a button click).

           // async function setupAudioAnalysis() {
           //     try {
           //         const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
           //         audioContext = new (window.AudioContext || window.webkitAudioContext)();
           //         analyser = audioContext.createAnalyser();
           //         const source = audioContext.createMediaStreamSource(stream);
           //         source.connect(analyser);
           //         analyser.fftSize = 128;
           //         const bufferLength = analyser.frequencyBinCount;
           //         dataArray = new Uint8Array(bufferLength);
           //         hasMic = true;
           //         console.log("Microphone access granted for audio analysis.");
           //     } catch (err) {
           //         console.error("Error accessing microphone for audio analysis:", err);
           //         hasMic = false;
           //     }
           // }
           // setupAudioAnalysis(); // Uncomment to enable mic reaction when not speaking
      }
}); // End of DOMContentLoaded listener


// --- Core Functionality ---

// Speech Toggle Setup: Attaches an event listener to the speech toggle checkbox
function setupSpeechToggle() {
    const toggle = document.getElementById("speech-toggle");
    if (toggle) {
        // Set the initial state of the toggle based on the global variable
        toggle.checked = speechEnabled;
        // Add a change listener to update speechEnabled when the toggle is switched
        toggle.addEventListener("change", (event) => { // Added event parameter
            speechEnabled = event.target.checked; // Use event.target.checked
            console.log("Speech Enabled:", speechEnabled);
             // If speech is disabled while speaking, cancel the current speech
            if (!speechEnabled && speechSynthesis.speaking) {
                speechSynthesis.cancel();
            }
        });
    } else {
        console.warn("Speech toggle element with ID 'speech-toggle' not found.");
    }
}

// Sidebar Toggle: Collapses or expands the sidebar and changes button text/emojis
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
        // Toggle the 'collapsed' class on the sidebar element
        sidebar.classList.toggle('collapsed');
        // The CSS handles showing/hiding the span text based on the 'collapsed' class.
        // Trigger a window resize event after toggling to help Three.js adjust
        window.dispatchEvent(new Event('resize'));
    } else {
        console.warn("Sidebar element with ID 'sidebar' not found.");
    }
}

// Speech Response Function: Uses the Web Speech API to speak a given text
function speakResponse(response) {
    // Only speak if speech is enabled and response is not empty
    if (!speechEnabled || !response) return;

    // Create a new SpeechSynthesisUtterance object with the response text
    const utterance = new SpeechSynthesisUtterance(response);

    // Optional: Set voice, pitch, rate
    const voices = speechSynthesis.getVoices();
    const preferredVoice = voices.find(voice => voice.name.includes('Google') && voice.lang.startsWith('en'));
    if (preferredVoice) {
        utterance.voice = preferredVoice;
    } else if (voices.length > 0) {
         utterance.voice = voices[0];
    }

    utterance.onstart = () => { console.log('Speech started'); };
    utterance.onend = () => { console.log('Speech ended'); };
    utterance.onerror = (event) => { console.error('Speech error:', event.error); };

    speechSynthesis.speak(utterance);
}

// Function to simulate typing effect
function typeMessage(messageElement, text, speed = 10) { // speed in milliseconds per character
    let i = 0;
    // Use innerHTML to allow for HTML tags (like <a> and <strong>)
    messageElement.innerHTML = ''; // Clear existing content

    // Convert the processed HTML string back to plain text for typing simulation
    // This is a simplification; a more advanced approach would type out the HTML structure
    // For now, we'll just type the visible text.
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = text;
    const plainText = tempDiv.textContent || tempDiv.innerText || '';


    function type() {
        if (i < plainText.length) {
            // Append one character at a time to the message element's textContent
            // This will not interpret HTML tags during typing
            messageElement.textContent += plainText.charAt(i);
            i++;
            // Scroll chat box to bottom as text is added
            const chatBox = document.getElementById("chat-box");
            if (chatBox) {
                chatBox.scrollTop = chatBox.scrollHeight;
            }
            setTimeout(type, speed);
        } else {
            // Typing finished, set the final HTML content
            messageElement.innerHTML = text; // Set the processed HTML
            // Remove typing indicator if any
            const typingIndicator = messageElement.nextSibling;
            if (typingIndicator && typingIndicator.classList.contains('typing-indicator')) {
                typingIndicator.remove();
            }
             // Ensure final scroll to bottom
             const chatBox = document.getElementById("chat-box");
             if (chatBox) {
                 chatBox.scrollTop = chatBox.scrollHeight;
             }
        }
    }

    type();
}


// Send Message Function: Sends user input to a backend server and handles the response
async function sendMessage() {
    const inputField = document.getElementById("chat-input");
    const chatBox = document.getElementById("chat-box");
    // We no longer need creativeOutputContainer here for context capture

    if (!inputField || !chatBox) {
         console.error("Required HTML elements not found.");
         return;
    }

    const message = inputField.value.trim();
    if (message === "") {
        return; // Don't send empty messages
    }

    // Display the user's message in the chat box immediately
    displayMessage({ type: 'text', content: message }, 'user');
    inputField.value = ""; // Clear the input field

    // --- Capture Creative Content Context ---
    // Now, get the content of the *currently displayed* creative output
    let creativeContext = null;
    if (currentCreativeOutputIndex !== -1 && creativeOutputs.length > currentCreativeOutputIndex) {
        creativeContext = creativeOutputs[currentCreativeOutputIndex].content;
        console.log("Including creative context in message:", creativeContext.substring(0, 100) + '...'); // Log snippet
    } else {
         console.log("No active creative output to include as creative context.");
    }
    // --- End Capture Creative Content Context ---


    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            // --- Include creative_context in the request body ---
            body: JSON.stringify({ message: message, creative_context: creativeContext })
            // --- End Include creative_context ---
        });

        if (!response.ok) {
            const errorData = await response.json();
            console.error('HTTP error!', response.status, errorData);
            displayMessage(errorData, 'error');
            speakResponse(`Error: ${errorData.content || 'An unknown error occurred.'}`);
            // Trigger orb animation on error
            triggerOrbAnimation(true); // Pass true for error state
            return;
        }

        const responseData = await response.json();
        console.log("Received response data:", responseData);

        const responseType = responseData.type || 'text';
        const responseContent = responseData.content;

        // Trigger orb animation on successful response
        triggerOrbAnimation(false); // Pass false for success state


        if (responseContent === undefined || responseContent === null) {
            console.warn(`Received response with no content for type: ${responseType}`, responseData);
            displayMessage({ type: 'text', content: `Ryan responded with type '${responseType}', but there was no content.` }, 'ryan');
             speakResponse(`Ryan responded with type ${responseType}, but there was no content.`);
            return;
        }

        // Use the modified displayMessage function
        displayMessage(responseData, 'ryan');


    } catch (error) {
        console.error('Error sending message:', error);
        const errorResponse = { type: 'error', content: `An error occurred while communicating with the AI: ${error.message}` };
        displayMessage(errorResponse, 'error');
         if (speechEnabled) {
             speakResponse("An error occurred while communicating with the AI.");
         }
         // Trigger orb animation on network errors
         triggerOrbAnimation(true); // Pass true for error state
    }
}

// Modified Display Message Function: Adds a message to the chat box and handles different types
function displayMessage(responseData, senderType) {
    const chatBox = document.getElementById("chat-box");
     if (!chatBox) {
         console.error("Chat box element not found.");
         return;
     }

    const messageElement = document.createElement("div");
    messageElement.classList.add("chat-message", senderType);

    const responseType = responseData.type || 'text';
    let responseContent = responseData.content; // Use let as we will modify this


    console.log(`Attempting to display message of type: ${responseType} from sender: ${senderType}`);


    if (responseContent === undefined || responseContent === null) {
        console.warn(`Displaying message with no content for type: ${responseType}`, responseData);
        messageElement.textContent = `[No content for type: ${responseType}]`;
        messageElement.classList.add('error');
        chatBox.appendChild(messageElement); // Append immediately if no content
    } else {
        switch (responseType) {
            case 'text':
                 // For text responses from Ryan, add a typing effect and process content
                 if (senderType === 'ryan') {

                     // --- Process Ryan's text content: Hyperlinks and Bold 'i' ---
                     let processedContent = responseContent;

                     // 1. Make URLs into hyperlinks
                     // This regex looks for common URL patterns (http, https, www, or just domain.tld)
                     // It's a basic regex and might not catch all valid URLs.
                     const urlRegex = /(\b(https?:\/\/|www\.)[-A-Z0-9+&@#\/%?=~_|!:,.;]*[-A-Z0-9+&@#\/%=~_|])/ig;
                     processedContent = processedContent.replace(urlRegex, (match) => {
                         let url = match;
                         // Add http:// if it's missing (for www. or domain.tld cases)
                         if (!url.match(/^https?:\/\//i)) {
                             url = 'http://' + url;
                         }
                         // Create the anchor tag
                         return `<a href="${url}" target="_blank">${match}</a>`;
                     });

                     // 2. Make single letter 'i' bold
                     // This regex looks for 'i' surrounded by word boundaries (space, punctuation, start/end of string)
                     // It avoids matching 'i' within words like 'with' or 'this'.
                     // It also handles common punctuation around 'i'.
                     const iRegex = /(^|\W)(i)($|\W)/g;
                     processedContent = processedContent.replace(iRegex, '$1<strong>$2</strong>$3');


                     console.log("Original Ryan text:", responseContent);
                     console.log("Processed Ryan text:", processedContent);
                     // --- End Processing ---


                     chatBox.appendChild(messageElement); // Append the message element first
                     // Add a temporary typing indicator
                     const typingIndicator = document.createElement('span');
                     typingIndicator.classList.add('typing-indicator');
                     typingIndicator.textContent = '...'; // Simple dots
                     chatBox.appendChild(typingIndicator);
                     chatBox.scrollTop = chatBox.scrollHeight; // Scroll to show indicator

                     // Start the typing animation with the processed content
                     typeMessage(messageElement, processedContent);

                     // Speak the response after a short delay or when typing finishes (optional)
                     // For now, let's speak immediately for responsiveness
                     if (speechEnabled) {
                         speakResponse(responseContent); // Speak the original text, not the HTML
                     }

                 } else {
                     // For user text messages, display immediately
                     messageElement.innerHTML = responseContent;
                     chatBox.appendChild(messageElement);
                     chatBox.scrollTop = chatBox.scrollHeight;
                 }
                break;

            case 'error':
                 messageElement.innerHTML = responseContent;
                 messageElement.classList.add('error');
                 chatBox.appendChild(messageElement);
                 chatBox.scrollTop = chatBox.scrollHeight;
                 if (speechEnabled) {
                     speakResponse(responseContent);
                 }
                break;

            case 'image_results':
                 // Assuming image_results content is HTML or similar to be inserted directly
                 messageElement.innerHTML = responseContent;
                 chatBox.appendChild(messageElement);
                 chatBox.scrollTop = chatBox.scrollHeight;
                 if (speechEnabled) {
                     const textToSpeak = responseData.query ? `I found some images for ${responseData.query}.` : `I found some images.`;
                     speakResponse(textToSpeak);
                 }
                 break;

            case 'logs': // Logs response type is now handled by fetchLogs
            case 'memory': // Memory response type is now handled by fetchMemory
                // These types are not displayed as chat bubbles in this design
                console.warn(`Attempted to display '${responseType}' type as chat message. This type should be handled by dedicated sections.`);
                // Optionally display a simple text message indicating this
                messageElement.textContent = `[Received ${responseType} data, see the dedicated section.]`;
                messageElement.classList.add('info'); // Use info styling
                chatBox.appendChild(messageElement);
                chatBox.scrollTop = chatBox.scrollHeight;
                break;

            case 'code':
            case 'creative':
                 // These types are handled by adding to creativeOutputs and showing the sidebar
                 console.log(`Received response of type '${responseType}'. Adding to creative outputs.`);
                 // Add the creative/code output to the array
                 addCreativeOutput(responseContent, responseType);

                 // Create a chat message linking to the creative output
                 messageElement.innerHTML = `Generated ${responseType}. <button class="view-creative-link">View</button>`;
                 chatBox.appendChild(messageElement);
                 chatBox.scrollTop = chatBox.scrollHeight;

                 // Add event listener to the "View" button
                 const viewButton = messageElement.querySelector('.view-creative-link');
                 if (viewButton) {
                     viewButton.addEventListener('click', viewLatestCreativeOutput);
                 }

                 // Automatically show the creative sidebar and display the latest output
                 viewLatestCreativeOutput();

                 // Speak a confirmation message
                 if (speechEnabled) {
                     speakResponse(`I have generated the ${responseType}. You can view it in the creative outputs panel.`);
                 }
                break;


            default:
                console.warn(`Received unknown response type: ${responseType}`, responseData);
                messageElement.textContent = `Received an unexpected response type: ${responseType}`;
                messageElement.classList.add('error');
                chatBox.appendChild(messageElement);
                chatBox.scrollTop = chatBox.scrollHeight;
                 if (speechEnabled) {
                     speakResponse("I received an unexpected response type.");
                 }
                break;
        }
    }
}


// Show Section Function: Hides/shows main content sections and absolute overlay sections
function showSection(sectionId) {
    const chatContainer = document.getElementById('chat-container');
    const creativeSidebar = document.getElementById('creative-sidebar');
    const logsContainer = document.getElementById('logs-container');
    const settingsContainer = document.getElementById('settings-container');
    const memoryContainer = document.getElementById('memory-container');

    if (!chatContainer || !creativeSidebar || !logsContainer || !settingsContainer || !memoryContainer) {
        console.error("One or more section containers not found.");
        return;
    }

    // Hide all absolute overlay sections first
    logsContainer.style.display = 'none';
    settingsContainer.style.display = 'none';
    memoryContainer.style.display = 'none';

    // Determine which main content layout to show
    if (sectionId === 'chat-container') {
        // Show chat and creative sidebar side-by-side
        chatContainer.style.display = 'flex';
        // Creative sidebar visibility is controlled by showCreativeSidebar/hideCreativeSidebar
        // Ensure it's visible if it wasn't explicitly hidden before
        // showCreativeSidebar(); // Decided against auto-showing creative sidebar here
        console.log("Showing chat section.");
    } else if (sectionId === 'logs-container' || sectionId === 'settings-container' || sectionId === 'memory-container') {
        // Hide main content and show the selected absolute overlay section
        chatContainer.style.display = 'none';
        hideCreativeSidebar(); // Explicitly hide creative sidebar

        const targetSection = document.getElementById(sectionId);
        if (targetSection) {
             targetSection.style.display = 'flex';
             console.log(`Showing absolute section: ${sectionId}`);
        } else {
            console.error(`Target section '${sectionId}' not found.`);
        }
    } else {
        console.warn(`Attempted to show unknown section: ${sectionId}`);
    }
}


// Function to explicitly show the creative sidebar
function showCreativeSidebar() {
    const creativeSection = document.getElementById('creative-sidebar');
    if (creativeSection) {
        creativeSection.style.display = 'flex'; // Ensure it's visible
        console.log("Showing creative sidebar.");
        // When showing the sidebar, ensure the latest creative output is displayed
        if (creativeOutputs.length > 0) {
             displayCreativeOutput(creativeOutputs.length - 1);
        } else {
             // If no outputs, clear the display area
             const creativeOutputDisplay = document.getElementById('creative-output-display');
             if (displayArea) displayArea.innerHTML = '';
        }

    } else {
        console.warn("Creative sidebar element not found.");
    }
}

// Function to explicitly hide the creative sidebar
function hideCreativeSidebar() {
     const creativeSection = document.getElementById('creative-sidebar');
    if (creativeSection) {
        creativeSection.style.display = 'none'; // Hide it
        console.log("Hiding creative sidebar.");
    } else {
        console.warn("Creative sidebar element not found.");
    }
}


// Handle Keypress to Send Message: Allows sending message by pressing Enter
function handleKeyPress(event) {
    const inputField = document.getElementById("chat-input");
    if (event.key === "Enter" && document.activeElement === inputField) {
        sendMessage();
    }
}


// Fetch Logs Function: Retrieves logs from a backend server and displays them
// Now accepts offset and limit for pagination
async function fetchLogs(offset, limit) {
    console.log(`Fetching logs with offset=${offset}, limit=${limit}`);
    if (!logsBoxElement) {
        console.warn("Logs box element with ID 'logs-box' not found.");
        return;
    }
    if (isFetchingLogs) {
        console.log("Already fetching logs, skipping.");
        return; // Prevent multiple simultaneous fetches
    }
    if (allLogsLoaded && offset > 0) { // Don't try to fetch more if all are loaded (unless it's the initial fetch)
        console.log("All logs already loaded.");
        return;
    }


    isFetchingLogs = true; // Set flag to true

    // Add a loading indicator at the top
    const loadingIndicator = document.createElement('div');
    loadingIndicator.textContent = "Loading logs...";
    loadingIndicator.classList.add('loading-indicator'); // Add a class for styling
    // Prepend the loading indicator if we are fetching older logs (offset > 0)
    // Otherwise, if offset is 0, it's the initial fetch or refresh, clear existing content first
    if (offset > 0) {
        logsBoxElement.prepend(loadingIndicator);
    } else {
        logsBoxElement.innerHTML = ''; // Clear existing content for initial load/refresh
        logsBoxElement.appendChild(loadingIndicator); // Append for initial load
    }


    try {
        // Use port 8000 for the logs endpoint and pass limit and offset as query parameters
        const response = await fetch(`${API_BASE_URL}/logs?limit=${limit}&offset=${offset}`);
        if (!response.ok) {
            const errorData = await response.json();
            console.error('HTTP error fetching logs!', response.status, errorData);
            // Remove loading indicator
            if (loadingIndicator.parentNode) loadingIndicator.remove();
            const errorElement = document.createElement('div');
            errorElement.textContent = `Error fetching logs: ${errorData.content || response.statusText}`;
            errorElement.classList.add('log-message', 'error'); // Use log-message and error classes
            logsBoxElement.appendChild(errorElement);
            isFetchingLogs = false;
            return;
        }
        const responseData = await response.json();
        console.log("Received logs response data:", responseData);

        // Remove loading indicator
        if (loadingIndicator.parentNode) loadingIndicator.remove();

        // Assuming the backend returns type 'logs' and content is the raw log string
        if (responseData.type === 'logs' && responseData.content !== undefined) {
            const logsContent = responseData.content;
            const nextOffset = responseData.next_offset || (offset + (logsContent.split('\n').length -1)); // Calculate next offset if not provided
             // Subtract 1 from length if the last line is empty due to split('\n')
            const hasMore = responseData.has_more !== undefined ? responseData.has_more : true; // Assume true if not provided

            // Process log content line by line and create bubbles
            if (typeof logsContent === 'string') {
                const logLines = logsContent.split('\n').filter(line => line.trim() !== ''); // Split and filter empty lines

                // Store current scroll position if loading older logs
                const oldScrollHeight = logsBoxElement.scrollHeight;

                logLines.forEach(line => {
                    const logMessageElement = document.createElement('div');
                    logMessageElement.classList.add('log-message'); // Add base log message class
                    logMessageElement.textContent = line; // Set the log line as text content

                    // Determine log level and add corresponding class for styling
                    if (line.includes(' - DEBUG - ')) {
                        logMessageElement.classList.add('debug');
                    } else if (line.includes(' - INFO - ')) {
                        logMessageElement.classList.add('info');
                    } else if (line.includes(' - WARNING - ')) {
                        logMessageElement.classList.add('warning');
                    } else if (line.includes(' - ERROR - ')) {
                        logMessageElement.classList.add('error');
                    } else if (line.includes(' - CRITICAL - ')) {
                        logMessageElement.classList.add('critical');
                    } else {
                        logMessageElement.classList.add('info'); // Default to info if level not detected
                    }

                    // Prepend or append logs based on whether we are loading older or initial logs
                    if (offset > 0) {
                        logsBoxElement.prepend(logMessageElement); // Prepend older logs
                    } else {
                        logsBoxElement.appendChild(logMessageElement); // Append initial logs
                    }
                });

                // Update pagination state
                logOffset = nextOffset;
                allLogsLoaded = !hasMore;

                // Adjust scroll position if loading older logs
                if (offset > 0) {
                    const newScrollHeight = logsBoxElement.scrollHeight;
                    logsBoxElement.scrollTop = newScrollHeight - oldScrollHeight;
                } else {
                     // Scroll to the bottom for the initial load
                    logsBoxElement.scrollTop = logsBoxElement.scrollHeight;
                }


            } else {
                const errorElement = document.createElement('div');
                errorElement.textContent = "Received logs data in unexpected format.";
                 errorElement.classList.add('log-message', 'error'); // Use log-message and error classes
                logsBoxElement.appendChild(errorElement);
            }
        } else if (responseData.type === 'error' && responseData.content !== undefined) {
             const errorElement = document.createElement('div');
             errorElement.textContent = `Error: ${responseData.content}`;
             errorElement.classList.add('log-message', 'error'); // Use log-message and error classes
             logsBoxElement.appendChild(errorElement);
        }
        else {
            const errorElement = document.createElement('div');
            errorElement.textContent = "Received logs data in unexpected format.";
            errorElement.classList.add('log-message', 'error');
            logsBoxElement.appendChild(errorElement);
        }
    } catch (error) {
        console.error('Error fetching logs:', error);
        // Remove loading indicator
        if (loadingIndicator.parentNode) loadingIndicator.remove();
        const errorElement = document.createElement('div');
        errorElement.textContent = `An error occurred while fetching logs: ${error.message}`;
        errorElement.classList.add('log-message', 'error'); // Use log-message and error classes
        logsBoxElement.appendChild(errorElement);
    } finally {
        isFetchingLogs = false; // Reset flag
        console.log(`Finished fetching logs. Next offset: ${logOffset}, All logs loaded: ${allLogsLoaded}`);
         // Add "End of logs" message if all logs are loaded
         if (allLogsLoaded && logsBoxElement.querySelector('.end-of-logs') === null) {
             const endMessage = document.createElement('div');
             endMessage.textContent = "--- End of Logs ---";
             endMessage.classList.add('log-message', 'end-of-logs');
             logsBoxElement.prepend(endMessage); // Prepend to the top
         }
    }
}

// Handle Logs Scroll Function: Checks if the user has scrolled to the top to load more logs
function handleLogsScroll() {
    // Check if scrolled to the very top (or very close to the top)
    // Using a small threshold (e.g., 10 pixels) to account for potential rendering differences
    const isAtTop = logsBoxElement.scrollTop <= 10;

    console.debug(`Logs scroll event. scrollTop: ${logsBoxElement.scrollTop}, isAtTop: ${isAtTop}, isFetchingLogs: ${isFetchingLogs}, allLogsLoaded: ${allLogsLoaded}`);

    // If at the top, not currently fetching, and there are more logs to load
    if (isAtTop && !isFetchingLogs && !allLogsLoaded) {
        console.log("Scrolled to top, attempting to fetch more logs.");
        fetchLogs(logOffset, logLimit); // Fetch the next page of logs
    }
}


// Fetch Memory Function: Retrieves chat memory from a backend server and displays it
// ... (existing global variables and functions)

// Add a variable to keep track of the currently edited memory item's original key
let editingMemoryKey = null;


// Fetch Memory Function: Retrieves chat memory from a backend server and displays it
async function fetchMemory() {
    const memoryBox = document.getElementById("memory");
    if (!memoryBox) {
        console.error("Memory box element with ID 'memory' not found.");
        return;
    }
    memoryBox.innerHTML = ''; // Clear previous memory display
    const loadingElement = document.createElement('div');
    loadingElement.textContent = "Fetching memory...";
    memoryBox.appendChild(loadingElement);

    try {
        // Fetch returns JSON directly now
        const response = await fetch(`${API_BASE_URL}/memory`);

         if (!response.ok) {
             const errorData = await response.json();
             console.error('HTTP error fetching memory!', response.status, errorData);
             memoryBox.innerHTML = '';
             const errorElement = document.createElement('div');
             errorElement.textContent = `Error fetching memory: ${errorData.content || response.statusText}`;
             errorElement.classList.add('log-error');
             memoryBox.appendChild(errorElement);
             return;
         }

        const memoryList = await response.json(); // Parse the JSON array

        memoryBox.innerHTML = ''; // Clear loading indicator and prepare for memory list

        if (memoryList.length > 0) {
            // Sort memory by timestamp if needed (optional, depends on backend sort)
            // memoryList.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)); // Example sort by latest timestamp

            memoryList.forEach(memoryItem => {
                const itemElement = document.createElement('div');
                itemElement.classList.add('memory-item');
                itemElement.dataset.key = memoryItem.key; // Store the key on the element

                const detailsElement = document.createElement('div');
                detailsElement.classList.add('memory-details');

                const keyElement = document.createElement('strong');
                keyElement.classList.add('memory-key');
                keyElement.textContent = `${memoryItem.key}:`;

                const valueElement = document.createElement('span');
                valueElement.classList.add('memory-value');
                // Display value appropriately - handle objects/arrays if necessary
                valueElement.textContent = typeof memoryItem.value === 'object' ? JSON.stringify(memoryItem.value) : memoryItem.value;

                detailsElement.appendChild(keyElement);
                detailsElement.appendChild(valueElement);


                const actionsElement = document.createElement('div');
                actionsElement.classList.add('memory-actions');

                // Edit Button
                const editButton = document.createElement('button');
                editButton.classList.add('edit-memory-button');
                editButton.title = "Edit";
                editButton.innerHTML = '<i class="fas fa-edit"></i>';
                editButton.addEventListener('click', () => {
                    // When edit button is clicked, make the value editable
                    makeMemoryEditable(itemElement, memoryItem.key, memoryItem.value);
                });
                actionsElement.appendChild(editButton);


                // Delete Button
                const deleteButton = document.createElement('button');
                deleteButton.classList.add('delete-memory-button');
                deleteButton.title = "Delete";
                deleteButton.innerHTML = '<i class="fas fa-trash-alt"></i>';
                deleteButton.addEventListener('click', () => {
                    // Confirm deletion and call delete function
                    if (confirm(`Are you sure you want to delete memory key: "${memoryItem.key}"?`)) {
                        deleteMemory(memoryItem.key);
                    }
                });
                actionsElement.appendChild(deleteButton);


                itemElement.appendChild(detailsElement);
                itemElement.appendChild(actionsElement);

                memoryBox.appendChild(itemElement);
            });

        } else {
            const noMemoryElement = document.createElement('div');
            noMemoryElement.textContent = "No memory entries found yet.";
             noMemoryElement.classList.add('log-message', 'info'); // Reuse log-message/info styling
            memoryBox.appendChild(noMemoryElement);
        }

        console.log(`Fetched ${memoryList.length} memory entries.`);

    } catch (error) {
        console.error('Error fetching memory:', error);
        memoryBox.innerHTML = '';
        const errorElement = document.createElement('div');
        errorElement.textContent = `An error occurred while fetching memory: ${error.message}`;
        errorElement.classList.add('log-message', 'error'); // Use log-message and error classes for styling
        memoryBox.appendChild(errorElement);
    }
}

// Delete Memory Function: Sends a DELETE request to the backend
async function deleteMemory(key) {
    console.log(`Attempting to delete memory key: ${key}`);
    try {
        const response = await fetch(`${API_BASE_URL}/memory/${encodeURIComponent(key)}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const errorData = await response.json();
             console.error(`HTTP error deleting memory key "${key}":`, response.status, errorData);
             alert(`Error deleting memory: ${errorData.content || response.statusText}`);
             // No need to fetch memory if delete failed, let the user see the error
        } else {
             const successData = await response.json();
             console.log(`Memory key "${key}" deleted successfully:`, successData);
             // Refresh the memory list after successful deletion
             fetchMemory();
             alert(successData.content || `Memory entry "${key}" deleted successfully.`);
        }

    } catch (error) {
        console.error(`Error deleting memory key "${key}":`, error);
        alert(`An error occurred while deleting memory: ${error.message}`);
    }
}

// Function to make a memory item editable
function makeMemoryEditable(itemElement, key, currentValue) {
    // Prevent editing multiple items at once
    if (editingMemoryKey !== null) {
        alert("Please save or cancel the current edit first.");
        return;
    }

    editingMemoryKey = key; // Set the key of the item being edited

    const valueElement = itemElement.querySelector('.memory-value');
    const actionsElement = itemElement.querySelector('.memory-actions');

    if (!valueElement || !actionsElement) {
        console.error("Could not find value or actions element for memory item.");
        editingMemoryKey = null; // Reset
        return;
    }

    // Create an input field (or textarea for multi-line values)
    const inputField = document.createElement('input');
    // Use textarea for values that likely have newlines or are long
    if (typeof currentValue === 'string' && currentValue.includes('\n')) {
         inputField.tagName = 'textarea'; // Change element type
         inputField.value = currentValue;
         inputField.rows = 4; // Set initial rows
         inputField.style.width = '100%'; // Make textarea take full width
         inputField.style.boxSizing = 'border-box'; // Include padding/border in width
    } else {
         inputField.type = 'text';
         inputField.value = currentValue;
    }

    inputField.classList.add('memory-edit-input');
    inputField.placeholder = "Edit Value";


    // Replace the value element with the input field
    valueElement.replaceWith(inputField);

    // Create Save and Cancel buttons
    const saveButton = document.createElement('button');
    saveButton.classList.add('save-memory-button'); // Add a specific class
    saveButton.title = "Save";
    saveButton.innerHTML = '<i class="fas fa-save"></i>'; // Use Font Awesome icon

    const cancelButton = document.createElement('button');
    cancelButton.classList.add('cancel-memory-button'); // Add a specific class
    cancelButton.title = "Cancel";
    cancelButton.innerHTML = '<i class="fas fa-times"></i>'; // Use Font Awesome icon

    // Clear existing action buttons (edit and delete)
    actionsElement.innerHTML = '';

    // Add Save and Cancel buttons
    actionsElement.appendChild(saveButton);
    actionsElement.appendChild(cancelButton);

    // Add event listeners for Save and Cancel
    saveButton.addEventListener('click', () => {
        const newValue = inputField.value.trim();
        if (newValue !== '') {
            updateMemory(key, newValue); // Call the update function
        } else {
            alert("Memory value cannot be empty.");
            // Revert to original state without saving
            revertMemoryEditable(itemElement, key, currentValue);
        }
    });

    cancelButton.addEventListener('click', () => {
        // Revert to original state without saving
        revertMemoryEditable(itemElement, key, currentValue);
    });

    // Focus on the input field
    inputField.focus();
}

// Function to revert a memory item from editable state
function revertMemoryEditable(itemElement, key, originalValue) {
    const inputField = itemElement.querySelector('.memory-edit-input');
    const actionsElement = itemElement.querySelector('.memory-actions');

    if (!inputField || !actionsElement) {
        console.error("Could not find input field or actions element to revert.");
        editingMemoryKey = null; // Reset
        return;
    }

    // Recreate the original value element
    const valueElement = document.createElement('span');
    valueElement.classList.add('memory-value');
    valueElement.textContent = typeof originalValue === 'object' ? JSON.stringify(originalValue) : originalValue;

    // Replace the input field with the value element
    inputField.replaceWith(valueElement);

     // Clear existing action buttons (save and cancel)
    actionsElement.innerHTML = '';

    // Recreate the original Edit and Delete buttons and their listeners
    const editButton = document.createElement('button');
    editButton.classList.add('edit-memory-button');
    editButton.title = "Edit";
    editButton.innerHTML = '<i class="fas fa-edit"></i>';
    editButton.addEventListener('click', () => {
        makeMemoryEditable(itemElement, key, originalValue); // Use originalValue for potential future edits if needed
    });
    actionsElement.appendChild(editButton);

    const deleteButton = document.createElement('button');
    deleteButton.classList.add('delete-memory-button');
    deleteButton.title = "Delete";
    deleteButton.innerHTML = '<i class="fas fa-trash-alt"></i>';
    deleteButton.addEventListener('click', () => {
        if (confirm(`Are you sure you want to delete memory key: "${key}"?`)) {
            deleteMemory(key);
        }
    });
    actionsElement.appendChild(deleteButton);

    editingMemoryKey = null; // Reset the editing state
}


// Function to send PUT request to update memory
async function updateMemory(key, newValue) {
    console.log(`Attempting to update memory key "${key}" with value: "${newValue}"`);
     // Use a temporary element to show "Saving..." or similar if desired

    try {
        const response = await fetch(`${API_BASE_URL}/memory/${encodeURIComponent(key)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ value: newValue })
        });

        if (!response.ok) {
             const errorData = await response.json();
             console.error(`HTTP error updating memory key "${key}":`, response.status, errorData);
             alert(`Error updating memory: ${errorData.content || response.statusText}`);
             // Revert to editable state or show error message next to the item
             // For simplicity, let's just refresh the list (which might show the old value)
             fetchMemory(); // Refresh the list
        } else {
             const successData = await response.json();
             console.log(`Memory key "${key}" updated successfully:`, successData);
             // Refresh the memory list after successful update
             fetchMemory();
             alert(successData.content || `Memory entry "${key}" updated successfully.`);
        }

    } catch (error) {
        console.error(`Error updating memory key "${key}":`, error);
        alert(`An error occurred while updating memory: ${error.message}`);
        // Revert to editable state or show error message
        fetchMemory(); // Refresh the list
    } finally {
         editingMemoryKey = null; // Reset editing state regardless of success/failure
    }
}


// ... (existing functions like editMemory placeholder, document handling, Three.js setup, etc.)

// Ensure fetchMemory is called when the memory button is clicked (this should already be set up)
// const memoryButton = document.getElementById('memory-button');
// if (memoryButton) {
//     memoryButton.addEventListener('click', () => {
//         showSection('memory-container');
//         fetchMemory(); // Fetch memory when the memory section is shown
//     });
// } // This part is already in the DOMContentLoaded listener

// --- Functions for managing Creative Outputs Array and Display ---

// Function to add a new creative output to the array and update the dropdown
function addCreativeOutput(content, type) {
    console.log(`Adding creative output of type '${type}' to array.`);
    const timestamp = new Date();
    const title = `${type.charAt(0).toUpperCase() + type.slice(1)} - ${timestamp.toLocaleTimeString()}`; // e.g., "Code - 10:30:00 AM"

    creativeOutputs.push({
        id: `creative-${Date.now()}-${Math.random().toString(16).slice(2)}`, // Unique ID
        title: title,
        content: content,
        type: type
    });
    console.log(`Creative outputs array updated. Current length: ${creativeOutputs.length}`);

    // Update the dropdown
    updateCreativeOutputDropdown();

    // Automatically display the newly added output
    displayCreativeOutput(creativeOutputs.length - 1);
}

// Function to update the creative output dropdown (select element)
function updateCreativeOutputDropdown() {
    console.log("Updating creative output dropdown.");
    const selectElement = document.getElementById('creative-output-select');
    if (!selectElement) {
        console.warn("Creative output select element not found.");
        return;
    }

    // Clear existing options
    selectElement.innerHTML = '';

    if (creativeOutputs.length === 0) {
        const option = document.createElement('option');
        option.value = -1;
        option.textContent = "No Creative Outputs";
        selectElement.appendChild(option);
        selectElement.disabled = true; // Disable dropdown if empty
        currentCreativeOutputIndex = -1; // Reset index
        console.log("Dropdown updated: No creative outputs.");
    } else {
        selectElement.disabled = false; // Enable dropdown
        creativeOutputs.forEach((output, index) => {
            const option = document.createElement('option');
            option.value = index;
            option.textContent = output.title;
            selectElement.appendChild(option);
        });
        // Select the latest output by default
        selectElement.value = creativeOutputs.length - 1;
        console.log(`Dropdown updated with ${creativeOutputs.length} outputs.`);
    }
    // Ensure the display is updated to match the selected option
    handleCreativeOutputSelectChange();
}

// Function to display a specific creative output based on its index
function displayCreativeOutput(index) {
    console.log(`Attempting to display creative output at index: ${index}`);
    const displayArea = document.getElementById('creative-output-display');
    const creativeOutputSelect = document.getElementById('creative-output-select');
    if (!displayArea || !creativeOutputSelect) {
        console.warn("Creative output display area or select not found.");
        return;
    }

    if (index >= 0 && index < creativeOutputs.length) {
        const output = creativeOutputs[index];
        displayArea.innerHTML = ''; // Clear previous content

        if (output.type === 'code') {
             displayArea.classList.add('code-content'); // Add code-specific class
             displayArea.classList.remove('text-content'); // Remove text class

            // Create elements for line numbers and code inner wrapper
            const lineNumbersDiv = document.createElement('div');
            lineNumbersDiv.classList.add('line-numbers');

            const codeInnerDiv = document.createElement('div'); // Wrapper for code and highlighting
            codeInnerDiv.classList.add('code-inner');

            const preElement = document.createElement('pre');
            const codeElement = document.createElement('code');

            // Set the raw text content to the code element
            codeElement.textContent = output.content;

            // Append code element to pre, and pre to the code inner div
            preElement.appendChild(codeElement);
            codeInnerDiv.appendChild(preElement);

            // --- Add Line Numbers ---
            const lines = output.content.split('\n');
            let lineNumbersHtml = '';
            for (let i = 1; i <= lines.length; i++) {
                lineNumbersHtml += `${i}\n`; // Add each number followed by a newline
            }
            lineNumbersDiv.textContent = lineNumbersHtml.trim(); // Set textContent and trim trailing newline

            // Append line numbers and code inner div to the content area
            displayArea.appendChild(lineNumbersDiv);
            displayArea.appendChild(codeInnerDiv);

            // --- Apply Syntax Highlighting ---
            try {
                if (window.hljs) {
                    // Use the correct language if known, otherwise let highlight.js auto-detect
                    // Attempt to detect language based on content or type
                    let language = 'plaintext'; // Default
                    if (output.type === 'code') {
                       // Simple attempt to guess language based on content
                       // Corrected 'or' to '||'
                       if (output.content.includes('def ') || output.content.includes('import ')) language = 'python';
                       else if (output.content.includes('<html') || output.content.includes('<body')) language = 'html';
                       else if (output.content.includes('function ') || output.content.includes('console.log')) language = 'javascript';
                       // Add more language detections as needed
                    }
                    console.log(`Applying syntax highlighting with language: ${language}`);
                    // Set the language class on the code element before highlighting
                    codeElement.classList.add(`language-${language}`);
                    hljs.highlightElement(codeElement); // highlight.js can auto-detect if class is not set
                } else {
                    console.warn("Highlight.js not loaded. Syntax highlighting skipped.");
                }
            } catch (error) {
                console.error("Error during Highlight.js highlighting:", error);
            }

            // Scroll to the top of the code content area within the display
            codeInnerDiv.scrollTop = 0;
            codeInnerDiv.scrollLeft = 0;


        } else { // Handle 'creative' or other text types
             displayArea.classList.add('text-content'); // Add text class
             displayArea.classList.remove('code-content'); // Remove code class
             displayArea.textContent = output.content; // Set text content directly
             // Scroll to the top of the text content area
             displayArea.scrollTop = 0;
        }


        currentCreativeOutputIndex = index; // Update the current index
        creativeOutputSelect.value = index; // Ensure dropdown matches display

        console.log(`Displayed creative output index: ${index}`);

    } else {
        // Handle case where index is invalid (e.g., no outputs)
        displayArea.innerHTML = ''; // Clear display
        displayArea.classList.remove('code-content', 'text-content');
        currentCreativeOutputIndex = -1; // Reset index
        console.warn(`Invalid creative output index: ${index}. Clearing display.`);
    }
}

// Handler for when the creative output dropdown selection changes
function handleCreativeOutputSelectChange() {
    const selectElement = document.getElementById('creative-output-select');
    if (selectElement) {
        const selectedIndex = parseInt(selectElement.value, 10);
        if (selectedIndex !== -1) {
            displayCreativeOutput(selectedIndex);
        } else {
             // If "No Creative Outputs" is selected (should be disabled), clear display
             const displayArea = document.getElementById('creative-output-display');
             if (displayArea) displayArea.innerHTML = '';
             displayArea.classList.remove('code-content', 'text-content');
             currentCreativeOutputIndex = -1;
        }
    }
}


// Function to view the latest creative output (used by the chat link)
function viewLatestCreativeOutput() {
    console.log("viewLatestCreativeOutput called.");
    if (creativeOutputs.length > 0) {
        console.log("Creative outputs exist. Showing sidebar and displaying latest.");
        showCreativeSidebar(); // Ensure sidebar is visible
        displayCreativeOutput(creativeOutputs.length - 1); // Display the last one
        // No need for highlighting a specific block element anymore, as there's only one display area
    } else {
        alert("No creative output to view.");
        console.warn("Attempted to view latest creative output, but none exist.");
    }
}


// Function to save the currently active creative output
function saveActiveCreativeOutput() {
    if (currentCreativeOutputIndex !== -1 && creativeOutputs.length > currentCreativeOutputIndex) {
        const activeOutput = creativeOutputs[currentCreativeOutputIndex];
        const contentToSave = activeOutput.content;
        const title = activeOutput.title; // Use the generated title
        const type = activeOutput.type; // Use the type

        // Implement save logic here (e.g., send to backend, download as file)
        // For now, just logging and alerting
        alert(`Save functionality not yet implemented for "${title}" (${type}).`);
        console.log(`Content to save (Active Output: "${title}"):`, contentToSave);
    } else {
         alert("No creative output is currently displayed to save.");
         console.warn("No active creative output to save.");
    }
}

// Function to copy the currently active creative output
function copyActiveCreativeOutput() {
     if (currentCreativeOutputIndex !== -1 && creativeOutputs.length > currentCreativeOutputIndex) {
        const activeOutput = creativeOutputs[currentCreativeOutputIndex];
        const contentToCopy = activeOutput.content;
        const title = activeOutput.title;

        navigator.clipboard.writeText(contentToCopy).then(() => {
            alert(`Content from "${title}" copied to clipboard!`);
        }).catch(err => {
            console.error(`Failed to copy content from "${title}":`, err);
            alert(`Failed to copy content from "${title}".`);
        });
    } else {
         alert("No creative output is currently displayed to copy.");
         console.warn("No active creative output to copy.");
    }
}

// Function to clear (remove) the currently active creative output
function clearActiveCreativeOutput() {
    if (currentCreativeOutputIndex !== -1 && creativeOutputs.length > currentCreativeOutputIndex) {
        const removedTitle = creativeOutputs[currentCreativeOutputIndex].title;
        // Remove the item from the array
        creativeOutputs.splice(currentCreativeOutputIndex, 1);

        // Update the dropdown and display
        updateCreativeOutputDropdown();

        // If there are still outputs, display the new last one; otherwise, clear the display
        if (creativeOutputs.length > 0) {
            displayCreativeOutput(creativeOutputs.length - 1);
        } else {
            const displayArea = document.getElementById('creative-output-display');
            if (displayArea) displayArea.innerHTML = '';
            displayArea.classList.remove('code-content', 'text-content');
            currentCreativeOutputIndex = -1;
        }

        console.log(`Cleared active creative output: "${removedTitle}"`);
        alert(`Cleared "${removedTitle}".`);

    } else {
        alert("No creative output is currently displayed to clear.");
        console.warn("No active creative output to clear.");
    }
}

// Clear All Creative Outputs Function
// This function is still available but not tied to a button in the current HTML structure
function clearAllCreativeOutputs() {
    const creativeOutputContainer = document.getElementById("creative-output-container"); // This container is now just a wrapper
    if (creativeOutputContainer) {
        creativeOutputs = []; // Clear the array
        updateCreativeOutputDropdown(); // Update the dropdown
        // Clear the display area
        const displayArea = document.getElementById('creative-output-display');
        if (displayArea) displayArea.innerHTML = '';
        displayArea.classList.remove('code-content', 'text-content');
        currentCreativeOutputIndex = -1; // Reset index

        console.log("All creative outputs cleared.");
        // Removed the alert for clearing all
    } else {
        console.warn("Creative output container not found for clearing all.");
    }
}


// --- Speech Recognition (Microphone) Integration ---

let recognizing = false;
let recognition;

if ('webkitSpeechRecognition' in window) {
    recognition = new webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
        recognizing = true;
        const micButton = document.getElementById("mic-button");
        if (micButton) micButton.textContent = "🎙️";
    };

    recognition.onend = () => {
        recognizing = false;
        const micButton = document.getElementById("mic-button");
        if (micButton) micButton.textContent = "🎤";
    };

    recognition.onresult = event => {
        const transcript = event.results[0][0].transcript.trim();
        console.log("Voice Input:", transcript);
        const inputField = document.getElementById("chat-input");
        if (inputField) {
             inputField.value = transcript;
             sendMessage(); // Automatically send the message
        } else {
             console.warn("Chat input element not found, cannot set voice transcript.");
        }
    };

    recognition.onerror = event => {
        console.error("Speech recognition error:", event.error);
        const micButton = document.getElementById("mic-button");
         if (micButton) micButton.textContent = "🎤";
         recognizing = false;
         alert(`Speech recognition error: ${event.error}. Please check microphone permissions.`);
    };

} else {
    console.warn("Webkit Speech Recognition not supported in this browser.");
    const micButton = document.getElementById("mic-button");
    if (micButton) {
        micButton.style.display = 'none';
    }
}

const micButton = document.getElementById("mic-button");
if (micButton) {
    micButton.addEventListener("click", () => {
        if (!speechEnabled || !recognition) return;

        if (recognizing) {
            recognition.stop();
        } else {
            recognition.start();
        }
    });
} else {
     console.warn("Microphone button element with ID 'mic-button' not found.");
}

// --- Resizing Logic (for the creative sidebar) ---

function startResize(event) {
    event.preventDefault();
    resizingElement = document.getElementById('creative-sidebar');

    if (resizingElement) {
        initialMouseX = event.clientX;
        initialWidth = resizingElement.offsetWidth;
        document.body.style.cursor = 'ew-resize';
        resizingElement.style.userSelect = 'none';
        resizingElement.style.transition = 'none';
    }
}

function resizeElement(event) {
    if (resizingElement) {
        const deltaX = event.clientX - initialMouseX;
        // Subtract deltaX because the handle is on the LEFT side
        let newWidth = initialWidth - deltaX;

        const minWidth = 250;
        const maxWidth = 800;
        newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));

        resizingElement.style.width = `${newWidth}px`;
        event.preventDefault();
    }
}

function stopResize() {
    if (resizingElement) {
        resizingElement = null;
        document.body.style.cursor = 'default';
        resizingElement.style.userSelect = '';
        resizingElement.style.transition = '';
    }
}

// --- Document Attachment Functions ---

// Handles the file selection and reads the file content
function handleDocumentSelection(event) {
    const file = event.target.files[0]; // Get the selected file

    if (file) {
        const reader = new FileReader();

        reader.onload = (e) => {
            const fileContent = e.target.result;
            const fileName = file.name;

            console.log(`File selected: ${fileName}`);
            console.log(`File content (first 100 chars): ${fileContent.substring(0, 100)}...`);

            // Send the file content to the backend
            uploadDocumentToBackend(fileName, fileContent);

            // Clear the file input so the same file can be selected again
            event.target.value = '';
        };

        reader.onerror = (e) => {
            console.error("Error reading file:", e);
            alert("Error reading file. Please try again.");
        };

        // Read the file as text
        reader.readAsText(file);
    }
}

// Sends the document content to the backend
async function uploadDocumentToBackend(fileName, fileContent) {
    console.log(`Uploading document '${fileName}' to backend...`);
    try {
        const response = await fetch(`${API_BASE_URL}/upload_document`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ fileName: fileName, fileContent: fileContent })
        });

        if (!response.ok) {
            const errorData = await response.json();
            console.error('HTTP error uploading document!', response.status, errorData);
            displayMessage({ type: 'error', content: `Error uploading document: ${errorData.content || response.statusText}` }, 'error');
            return;
        }

        const responseData = await response.json();
        console.log("Document upload response:", responseData);

        // Display the backend's confirmation message in the chat
        if (responseData.type === 'text' && responseData.content) {
            // Use displayMessage, which now handles typing for Ryan's text
            displayMessage(responseData, 'ryan');
             // Speech is handled within displayMessage for text type
        } else {
             console.warn("Received unexpected response format for document upload:", responseData);
             // Display a simple text message if the response format is unexpected
             displayMessage({ type: 'text', content: `Document '${fileName}' uploaded, but received unexpected confirmation.` }, 'ryan');
             if (speechEnabled) {
                  speakResponse(`Document ${fileName} uploaded.`);
             }
        }

    } catch (error) {
        console.error('Error uploading document:', error);
        displayMessage({ type: 'error', content: `An error occurred while uploading the document: ${error.message}` }, 'error');
         if (speechEnabled) {
             speakResponse("An error occurred while uploading the document.");
         }
    }
}
// --- End Document Attachment Functions ---

// Attach event listener to the attach button
const attachButton = document.getElementById('attach-button');
if (attachButton) {
    attachButton.addEventListener('click', () => {
        const documentInput = document.getElementById('document-input');
        if (documentInput) {
            documentInput.click(); // Trigger the hidden file input click
        } else {
            console.warn("Document input element not found.");
        }
    });
} else {
    console.warn("Attach button element with ID 'attach-button' not found.");
}

// Attach event listener to the hidden file input
const documentInput = document.getElementById('document-input');
if (documentInput) {
    documentInput.addEventListener('change', handleDocumentSelection);
} else {
    console.warn("Document input element with ID 'document-input' not found.");
}
