# Ryan AI - AI Assistant with Memory and Emotional Understanding

Ryan AI is an advanced AI assistant/chatbot designed to provide personalized conversations with memory, emotional understanding, and engaging responses. It can speak its replies, log conversations, and maintain a growing memory of chats. Ryan AI is fully customizable, with options for selective memory, emotion detection, and personalized follow-up questions.

## Tech Stack

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** FastAPI (Python)
- **AI Model:** `facebook/opt-350m` (via the Transformers library)
- **Memory Storage:** FAISS + Pickle
- **Logging:** Python's logging module (stored in `app.log`)

## Features

- **Speech Responses:** Ryan AI can speak its replies using speech synthesis.
- **Conversation Logging:** All conversations are logged with timestamps in `app.log`.
- **Memory Storage:** Ryan AI stores memory embeddings using FAISS and Pickle.
- **Emotion Detection:** The AI detects basic emotions like happy, sad, or neutral based on input.
- **Follow-Up Questions:** It generates curiosity-driven follow-up questions to keep conversations engaging.
- **Sidebar & Tabbed Interface:** A sidebar with tabs for chat, logs, and memory for easy navigation.
- **Local Setup:** Currently set up for a fully local environment with no cloud backend.

## Setup Instructions

### Prerequisites
Before setting up Ryan AI, ensure you have the following:

- Python 3.x
- FastAPI
- PyTorch
- Transformers library
- FAISS
- Requests
- Other dependencies in `requirements.txt`

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ryan-ai.git
   cd ryan-ai
