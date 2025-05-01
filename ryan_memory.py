import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv

# load environment
load_dotenv("ryanEnv.env")
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH")

# firebase setup
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)
db = firestore.client()

class RyanMemory:
    def __init__(self):
        self.memory_collection = db.collection('memory')

    def save(self, person, key, value):
        doc_ref = self.memory_collection.document(f"{person}_{key}")
        doc_ref.set({"person": person, "key": key, "value": value})

    def fetch_all(self):
        docs = self.memory_collection.stream()
        memories = []
        for doc in docs:
            data = doc.to_dict()
            memories.append(data)
        return memories

    def clear_all(self):
        docs = self.memory_collection.stream()
        for doc in docs:
            doc.reference.delete()
