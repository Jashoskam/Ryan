let speechEnabled = true;

// Initialize the page
window.addEventListener("DOMContentLoaded", () => {
    setupSpeechToggle();
    setupSidebarToggle();
});

function setupSpeechToggle() {
    const toggle = document.getElementById("speech-toggle");
    if (toggle) {
        toggle.checked = speechEnabled;
        toggle.addEventListener("change", () => {
            speechEnabled = toggle.checked;
            console.log("Speech Enabled:", speechEnabled);
        });
    }
}
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const chatButton = document.getElementById('chat-button');
  const logsButton = document.getElementById('logs-button');
  const settingsButton = document.getElementById('settings-button');
  sidebar.classList.toggle('collapsed');

  if (sidebar.classList.contains('collapsed')) {
    chatButton.textContent = '💬';
    logsButton.textContent = '📜';
    settingsButton.textContent = '⚙️';
  } else {
    chatButton.textContent = '💬 Chat';
    logsButton.textContent = '📜 Logs';
    settingsButton.textContent = '⚙️ Settings';
    
  }
}
function speakResponse(response) {
    if (!speechEnabled) return;

    const utterance = new SpeechSynthesisUtterance(response);
    animateOrbDuringSpeech(utterance);
    speechSynthesis.speak(utterance);
}

function animateOrbDuringSpeech(utterance) {
    const orb = document.getElementById("ai-orb");
    if (!orb) return;

    let scale = 1;
    let direction = 1;

    function pulse() {
        if (!speechSynthesis.speaking) return;

        scale += direction * 0.02;
        if (scale >= 1.3 || scale <= 1) direction *= -1;

        orb.style.transform = `scale(${scale})`;
        orb.style.boxShadow = `0 0 ${20 + (scale - 1) * 50}px #00ccff`;

        requestAnimationFrame(pulse);
    }

    utterance.onstart = pulse;
    utterance.onend = () => {
        orb.style.transform = "scale(1)";
        orb.style.boxShadow = "0 0 25px #00ccff";
    };
}

function sendMessage() {
    const inputField = document.getElementById("chat-input");
    const message = inputField.value.trim();
    if (!message) return;

    displayMessage("You", message);
    inputField.value = "";

    fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message })
    })
    .then(res => res.json())
    .then(data => {
        displayMessage("AI", data.response);
        speakResponse(data.response);
    })
    .catch(err => console.error("Error:", err));
}

function displayMessage(sender, message) {
    const chatBox = document.getElementById("chat-box");
    const msgElement = document.createElement("div");

    msgElement.className = `message ${sender === "You" ? "user" : "ai"}`;
    msgElement.innerHTML = `<strong>${sender}:</strong> ${message}`;

    chatBox.appendChild(msgElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function showSection(sectionId) {
    document.querySelectorAll(".section").forEach(sec => sec.style.display = "none");
    const section = document.getElementById(sectionId);
    if (section) section.style.display = "block";

    if (sectionId === "logs-container") fetchLogs();
}

document.addEventListener("keypress", event => {
    if (event.key === "Enter") sendMessage();
});

async function fetchLogs() {
    try {
        const res = await fetch("http://127.0.0.1:5001/logs");
        if (!res.ok) throw new Error(`HTTP error! Status: ${res.status}`);

        const { logs } = await res.json();
        const logsBox = document.getElementById("logs-box");
        logsBox.innerHTML = "";

        logs.forEach(line => {
            const div = document.createElement("div");
            div.classList.add("log-line");

            if (line.toLowerCase().includes("error")) {
                div.classList.add("error");
            } else if (line.toLowerCase().includes("warn")) {
                div.classList.add("warning");
            } else {
                div.classList.add("info");
            }

            div.textContent = line;
            logsBox.appendChild(div);
        });

        logsBox.scrollTop = logsBox.scrollHeight;
    } catch (err) {
        console.error("Failed to fetch logs:", err);
        alert("An error occurred while fetching logs.");
    }
}


function createLogEntry(rawLine) {
    const logDiv = document.createElement("div");
    logDiv.className = "log-entry";

    const timestampPattern = /\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}/;
    const match = rawLine.match(timestampPattern);
    const timestamp = match ? match[0] : "Unknown Time";
    const content = rawLine.replace(timestampPattern, "").trim();

    const timestampDiv = document.createElement("div");
    timestampDiv.className = "log-timestamp";
    timestampDiv.textContent = timestamp;

    const contentDiv = document.createElement("div");
    contentDiv.className = "log-content";
    contentDiv.textContent = content;

    logDiv.append(timestampDiv, contentDiv);

    if (/error|exception/i.test(content)) {
        logDiv.classList.add("error");
    }

    return logDiv;
}

async function loadMemory() {
    const res = await fetch("http://127.0.0.1:5001/memory");
    const { memory = [] } = await res.json();
    const memoryContainer = document.getElementById("memory");

    memoryContainer.innerHTML = "";

    memory.forEach(([timestamp, userInput, aiResponse]) => {
        const div = document.createElement("div");
        div.className = "memory-entry";
        div.innerHTML = `<strong>${new Date(timestamp * 1000).toLocaleString()}</strong><br>User: ${userInput}<br>AI: ${aiResponse}<hr>`;
        memoryContainer.appendChild(div);
    });
}

function showMemoryTab() {
    document.getElementById("memory-tab").style.display = "block";
    loadMemory();
}
let recognizing = false;
let recognition;

if ('webkitSpeechRecognition' in window) {
    recognition = new webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
        recognizing = true;
        document.getElementById("mic-button").textContent = "🎙️";
    };

    recognition.onend = () => {
        recognizing = false;
        document.getElementById("mic-button").textContent = "🎤";
    };

    recognition.onresult = event => {
        const transcript = event.results[0][0].transcript.trim();
        console.log("Voice Input:", transcript);
        document.getElementById("chat-input").value = transcript;
        sendMessage(); // send it like a normal typed message
    };
} else {
    console.warn("Speech Recognition not supported in this browser.");
}

document.getElementById("mic-button").addEventListener("click", () => {
    if (!speechEnabled) return;
    if (recognizing) {
        recognition.stop();
    } else {
        recognition.start();
    }
});