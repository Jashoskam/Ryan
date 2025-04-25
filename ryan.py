from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import time
import numpy as np
import faiss
import pickle
import logging
import openai
import requests
import random
import os
import traceback
from fastapi.responses import PlainTextResponse, JSONResponse

app = FastAPI()

# enable cors for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# setup logging
logging.basicConfig(filename="app.log", level=logging.INFO, format="%(asctime)s - %(message)s")

# load ai model with tracing
try:
    logging.info("attempting to load model and tokenizer")
    tokenizer = AutoTokenizer.from_pretrained("facebook/opt-125m")
    model = AutoModelForCausalLM.from_pretrained("facebook/opt-125m")
    logging.info("model and tokenizer loaded successfully")
except Exception as e:
    tokenizer = None
    model = None
    logging.error(f"model loading failed: {e}")
    logging.error(traceback.format_exc())

def dummy_response(input_text):
    return f"i'm still learning, but here's what i think: '{input_text[::-1]}'"

class AIMemory:
    def __init__(self, dimension=512, memory_file="memory.pkl"):
        self.memory = faiss.IndexFlatIP(dimension)
        self.data = []
        self.memory_file = memory_file
        self.load_memory()

    def store_memory(self, user_input, ai_response, embedding):
        embedding = embedding / np.linalg.norm(embedding)
        embedding = embedding.astype('float32').reshape(1, -1)
        self.memory.add(embedding)
        self.data.append((time.time(), user_input, ai_response))
        self.save_memory()
        logging.info(f"stored memory: input='{user_input}' response='{ai_response}'")

    def save_memory(self):
        with open(self.memory_file, "wb") as f:
            pickle.dump(self.data, f)
            logging.info("memory saved")

    def load_memory(self):
        try:
            with open(self.memory_file, "rb") as f:
                self.data = pickle.load(f)
            logging.info(f"loaded {len(self.data)} memories")
        except FileNotFoundError:
            logging.info("no saved memory found")

    def reset(self):
        self.memory = faiss.IndexFlatIP(512)
        self.data = []
        self.save_memory()
        logging.info("memory reset")

    def get_recent(self):
        return self.data[-5:] if len(self.data) >= 5 else self.data

    def stats(self):
        total = len(self.data)
        last_chat_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.data[-1][0])) if total else "no chats yet"
        return {
            "total_chats": total,
            "last_chat_time": last_chat_time,
            "memory_size": self.memory.ntotal
        }

memory = AIMemory(dimension=512)

class Message(BaseModel):
    message: str

@app.post("/chat")
async def chat(message: Message):
    return await chat_with_ai(message)

async def chat_with_ai(message: Message):
    user_input = message.message.lower()
    logging.info(f"received input: {user_input}")

    if user_input == "reset memory":
        memory.reset()
        return {"response": "all memory has been wiped. i'm starting fresh."}

    if user_input.startswith("generate code for"):
        language = user_input.replace("generate code for", "").strip()
        return {"response": generate_code(language)}

    if "search the web for" in user_input:
        query = user_input.replace("search the web for", "").strip()
        return {"response": web_search(query)}

    try:
        logging.info("step 1: entered try block")
        if tokenizer and model:
            logging.info("step 2: tokenizer and model available")
            tokens = tokenizer(user_input, return_tensors="pt")
            logging.info("step 3: tokens created")
            output = model.generate(**tokens, max_length=100, num_return_sequences=1)
            logging.info("step 4: output generated")
            response = tokenizer.decode(output[0], skip_special_tokens=True)
            logging.info(f"step 5: decoded response: {response}")
            if response.lower().startswith(user_input):
                response = response[len(user_input):].strip()
                logging.info("step 6: trimmed repeated user input from response")
        else:
            logging.warning("step 7: tokenizer or model missing, using dummy response")
            response = dummy_response(user_input)

        logging.info("step 8: analyzing emotion")
        emotion_score = analyze_emotion(user_input)
        logging.info(f"step 9: emotion score: {emotion_score}")

        logging.info("step 10: generating curiosity")
        curious_question = generate_curiosity(user_input)
        logging.info(f"step 11: curiosity question: {curious_question}")

        if curious_question:
            response += f" by the way, {curious_question}"

        logging.info("step 12: generating dummy embedding")
        embedding = np.random.rand(512).astype('float32')
        memory.store_memory(user_input, response, embedding)
        logging.info("step 13: memory stored")

    except Exception as e:
        logging.error(f"processing error: {e}")
        logging.error(traceback.format_exc())
        response = "i encountered an issue processing your request."
        emotion_score = "unknown"
        logging.info(f"user: {user_input} | ai: {response} | emotion: {emotion_score}")
        return {"response": response, "emotion_score": emotion_score}

    log_entry = f"user: {user_input} | ai: {response} | emotion: {emotion_score}"
    logging.info(log_entry)

    return {"response": response, "emotion_score": emotion_score}

@app.get("/logs")
async def get_logs():
    try:
        with open("app.log", "r") as f:
            lines = f.readlines()[-50:]  # get last 50 log lines
        clean_lines = [line.strip() for line in lines if line.strip()]
        return JSONResponse(content={"logs": clean_lines})
    except Exception as e:
        return JSONResponse(content={"logs": [f"error reading logs: {str(e)}"]})

@app.get("/stats")
async def get_stats():
    return memory.stats()

def generate_code(language):
    code_templates = {
        "python": "def hello_world():\n    print('hello, world!')",
        "html": "<!DOCTYPE html>\n<html>\n<head><title>my page</title></head>\n<body><h1>hello, world!</h1></body>\n</html>",
        "css": "body {\n    background-color: #121212;\n    color: white;\n    font-family: 'Inter', sans-serif;\n}"
    }
    return code_templates.get(language, "i don't know how to generate that language.")

def web_search(query):
    try:
        url = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data.get("AbstractText", "no relevant information found.")
        else:
            return "failed to fetch results from the web."
    except Exception as e:
        logging.error(f"web search error: {e}")
        logging.error(traceback.format_exc())
        return "web search failed."

def analyze_emotion(text):
    emotions = {"happy": ["great", "awesome", "fantastic"], "sad": ["bad", "terrible", "horrible"], "neutral": []}
    for emotion, words in emotions.items():
        if any(word in text for word in words):
            return emotion
    return "neutral"

def generate_curiosity(user_input):
    prompts = [
        "why do you think that is?",
        "can you tell me more about it?",
        "what made you say that?",
        "how often do you feel that way?",
        "have you experienced that recently?"
    ]
    if any(word in user_input for word in ["i think", "i feel", "i like", "i don't like"]):
        return random.choice(prompts)
    return ""

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5001)
