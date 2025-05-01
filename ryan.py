from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import time
import logging
import traceback
import json
from typing import Optional, Dict, Any, List
import os
from datetime import datetime, timedelta
try:
    from firebase_admin import firestore
except ImportError:
    firestore = None

# Import RyanAI, db, and CURRENT_USER_ID from the ryan_ai module
try:
    from ryan_ai import RyanAI, db, CURRENT_USER_ID
    if db is None:
        logging.error("Firebase db connection is None in ryan_ai.py. Memory functions will not work.")
    if CURRENT_USER_ID is None:
         logging.error("CURRENT_USER_ID is None in ryan_ai.py.")

except ImportError as e:
    logging.error(f"Failed to import RyanAI or db from ryan_ai: {e}")
    logging.error(traceback.format_exc())
    RyanAI = None
    db = None
    CURRENT_USER_ID = "unknown_user"


if RyanAI:
    ryan = RyanAI(db)
    logging.info("RyanAI instance created in ryan.py.")
else:
    ryan = None
    logging.error("RyanAI instance could not be created due to import failure.")


app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup logging
if not logging.getLogger().handlers:
    logging.basicConfig(filename="app.log", level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logging.info("Logging configured for ryan.py")
else:
    logging.info("Logging already configured, reusing existing handlers.")


# Pydantic models (Keep existing models)
class Message(BaseModel):
    message: str
    creative_context: Optional[str] = None

class DocumentUpload(BaseModel):
    fileName: str
    fileContent: str

class MemoryItem(BaseModel):
    key: str
    value: Any
    category: Optional[str] = "general"
    timestamp: Any

class MemoryUpdate(BaseModel):
    value: Any

class DailyUsageData(BaseModel):
    date: str
    count: int

class UsageStats(BaseModel):
    daily_usage: List[DailyUsageData]
    total_messages: int

# --- New Pydantic Models for Coding Tasks ---
class CodeExecutionRequest(BaseModel):
    code: str
    language: str

class CodeDebugRequest(BaseModel):
    code: str
    error_output: str
    language: str
    context: Optional[str] = None

class CodeFixRequest(BaseModel):
    original_code: str
    suggested_fix: str
    language: str
    context: Optional[str] = None

class CodeAnalysisRequest(BaseModel):
    code: str
    task_description: Optional[str] = None
    context: Optional[str] = None

# --- Existing Chat Endpoint ---
@app.post("/chat")
async def chat(message: Message):
    logging.info(f"Received chat message: {message.message[:100]}...")
    logging.debug(f"Received creative_context: {message.creative_context[:100] if message.creative_context else 'None'}...")

    if ryan is None:
         logging.error("RyanAI instance is not available, cannot process chat.")
         return JSONResponse(content={"type": "error", "content": "AI backend is not available."}, status_code=500)

    try:
        response_dict = ryan.chatbot(message.message, creative_context=message.creative_context)
        logging.info(f"Generated response (type: {response_dict.get('type', 'unknown')}): {str(response_dict.get('content', 'No content'))[:100]}...")
        return JSONResponse(content=response_dict)
    except Exception as e:
        logging.error(f"Error processing chat message: {e}")
        logging.error(traceback.format_exc())
        return JSONResponse(content={"type": "error", "content": f"An internal error occurred: {str(e)}"}, status_code=500)

# --- Existing Document Upload Endpoint ---
@app.post("/upload_document")
async def upload_document(document: DocumentUpload):
    logging.info(f"Received document upload: {document.fileName}")

    if ryan is None or not hasattr(ryan, 'process_document'):
         logging.error("RyanAI instance or process_document method is not available, cannot process document upload.")
         return JSONResponse(content={"type": "error", "content": "Document processing is not available."}, status_code=500)

    try:
        confirmation_message = ryan.process_document(document.fileName, document.fileContent)
        logging.info(f"Document '{document.fileName}' processed. Confirmation: {confirmation_message[:100]}...")
        return JSONResponse(content={"type": "text", "content": confirmation_message})
    except Exception as e:
        logging.error(f"Error processing document upload '{document.fileName}': {e}")
        logging.error(traceback.format_exc())
        return JSONResponse(content={"type": "error", "content": f"Error processing document: {str(e)}"}, status_code=500)

# --- Existing Logs Endpoint ---
@app.get("/logs")
async def get_logs(limit: int = Query(50, ge=1), offset: int = Query(0, ge=0)):
    logging.info(f"Received request for logs with limit={limit}, offset={offset}")
    log_file_path = "app.log"
    try:
        if not os.path.exists(log_file_path):
            logging.warning(f"Log file not found at {log_file_path}")
            return JSONResponse(content={"type": "logs", "content": "Log file not found."}, status_code=404)

        with open(log_file_path, 'r') as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)
        logging.debug(f"Total log lines found: {total_lines}")

        all_lines.reverse()

        start_index = offset
        end_index = offset + limit

        paginated_lines = all_lines[start_index:min(end_index, total_lines)]

        paginated_lines.reverse()

        has_more = end_index < total_lines
        logging.debug(f"Returning {len(paginated_lines)} lines. Has more logs: {has_more}")

        logs_content = "".join(paginated_lines)

        return JSONResponse(content={
            "type": "logs",
            "content": logs_content,
            "next_offset": offset + len(paginated_lines),
            "has_more": has_more
        })

    except Exception as e:
        logging.error(f"Error reading log file: {e}")
        logging.error(traceback.format_exc())
        return JSONResponse(content={"type": "error", "content": f"Error reading log file: {str(e)}"}, status_code=500)

# --- Existing Memory Endpoints ---
@app.get("/memory", response_model=List[MemoryItem])
async def get_memory():
    logging.info("Received request for memory.")
    if ryan is None or ryan.db is None:
        logging.error("RyanAI instance or Firebase db is not available, cannot fetch memory.")
        raise HTTPException(status_code=500, detail={"type": "error", "content": "Memory system not available."})

    try:
        memory_ref = ryan.db.collection('users').document(CURRENT_USER_ID).collection('memory')
        docs = memory_ref.stream()

        memory_list = []
        for doc in docs:
            memory_data = doc.to_dict()
            memory_list.append({
                "key": doc.id,
                "value": memory_data.get("value", "N/A"),
                "category": memory_data.get("category", "general"),
                "timestamp": memory_data.get("timestamp", None)
            })

        logging.info(f"Fetched {len(memory_list)} memory entries.")
        return memory_list

    except Exception as e:
        logging.error(f"Error fetching memory for user {CURRENT_USER_ID}: {e}")
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail={"type": "error", "content": f"Error fetching memory: {str(e)}"})

@app.put("/memory/{key}")
async def update_memory(key: str, memory_update: MemoryUpdate):
    logging.info(f"Received request to update memory key: {key}")
    if ryan is None or ryan.db is None:
        logging.error("RyanAI instance or Firebase db is not available, cannot update memory.")
        raise HTTPException(status_code=500, detail={"type": "error", "content": "Memory system not available."})

    if not key:
         logging.warning("Received request to update memory with empty key.")
         raise HTTPException(status_code=400, detail={'type': 'error', 'content': 'Memory key is missing from path.'})

    try:
        doc_ref = ryan.db.collection('users').document(CURRENT_USER_ID).collection('memory').document(key)
        doc = doc_ref.get()

        if doc.exists:
            update_data = {'value': memory_update.value}
            if firestore:
                 update_data['timestamp'] = firestore.SERVER_TIMESTAMP
            doc_ref.update(update_data)

            logging.info(f"Memory updated for user '{CURRENT_USER_ID}', key '{key}'.")
            return JSONResponse(content={"type": "success", "content": f"Memory entry for '{key}' updated successfully."})
        else:
            logging.warning(f"Attempted to update non-existent memory key '{key}' for user '{CURRENT_USER_ID}'.")
            raise HTTPException(status_code=404, detail={"type": "error", "content": f"Memory entry '{key}' not found for update."})

    except Exception as e:
        logging.error(f"Error updating memory for user {CURRENT_USER_ID}, key '{key}': {e}")
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail={"type": "error", "content": f"Error updating memory: {str(e)}"})

@app.delete("/memory/{key}")
async def delete_memory(key: str):
    logging.info(f"Received request to delete memory key: {key}")
    if ryan is None or ryan.db is None:
        logging.error("RyanAI instance or Firebase db is not available, cannot delete memory.")
        raise HTTPException(status_code=500, detail={"type": "error", "content": "Memory system not available."})

    if not key:
         logging.warning("Received request to delete memory with empty key.")
         raise HTTPException(status_code=400, detail={'type': 'error', 'content': 'Memory key is missing from path.'})

    try:
        doc_ref = ryan.db.collection('users').document(CURRENT_USER_ID).collection('memory').document(key)
        doc = doc_ref.get()

        if doc.exists:
            doc_ref.delete()
            logging.info(f"Memory deleted for user '{CURRENT_USER_ID}', key '{key}'.")
            return JSONResponse(content={"type": "success", "content": f"Memory entry for '{key}' deleted successfully."})
        else:
            logging.warning(f"Attempted to delete non-existent memory key '{key}' for user '{CURRENT_USER_ID}'.")
            raise HTTPException(status_code=404, detail={"type": "error", "content": f"Memory entry '{key}' not found for deletion."})

    except Exception as e:
        logging.error(f"Error deleting memory for user {CURRENT_USER_ID}: {e}")
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail={"type": "error", "content": f"Error deleting memory: {str(e)}"})

# --- Existing Stats Endpoint ---
@app.get("/stats", response_model=UsageStats)
async def get_stats():
    logging.info("Received request for usage statistics.")
    daily_usage_list = []
    total_messages = 0
    today = datetime.now()

    for i in range(7):
        date = today - timedelta(days=i)
        message_count = (i + 1) * 5 + 10
        total_messages += message_count
        daily_usage_list.append({
            "date": date.strftime("%Y-%m-%d"),
            "count": message_count
        })

    daily_usage_list.reverse()

    stats_data = {
        "daily_usage": daily_usage_list,
        "total_messages": total_messages
    }
    logging.info(f"Generated sample usage statistics: {stats_data}")

    return UsageStats(**stats_data)


# --- New Endpoints for Coding Tasks ---

@app.post("/execute_code")
async def execute_code_endpoint(request: CodeExecutionRequest):
    logging.info(f"Received request to execute {request.language} code.")
    if ryan is None or not hasattr(ryan, 'execute_code'):
         logging.error("RyanAI instance or execute_code method is not available.")
         return JSONResponse(content={"type": "error", "content": "Code execution service is not available."}, status_code=500)
    try:
        # Call the execute_code method from RyanAI
        result = ryan.execute_code(request.code, request.language)
        logging.info(f"Code execution result: Success={result.get('success')}, ReturnCode={result.get('return_code')}")
        return JSONResponse(content=result)
    except Exception as e:
        logging.error(f"Error executing code: {e}")
        logging.error(traceback.format_exc())
        return JSONResponse(content={"type": "error", "content": f"An internal error occurred during code execution: {str(e)}"}, status_code=500)


@app.post("/debug_code")
async def debug_code_endpoint(request: CodeDebugRequest):
    logging.info(f"Received request to debug {request.language} code.")
    if ryan is None or not hasattr(ryan, 'debug_code'):
         logging.error("RyanAI instance or debug_code method is not available.")
         return JSONResponse(content={"type": "error", "content": "Code debugging service is not available."}, status_code=500)
    try:
        # Call the debug_code method from RyanAI
        result = ryan.debug_code(request.code, request.error_output, request.language, context=request.context)
        logging.info(f"Code debugging result: Success={result.get('success')}")
        return JSONResponse(content=result)
    except Exception as e:
        logging.error(f"Error debugging code: {e}")
        logging.error(traceback.format_exc())
        return JSONResponse(content={"type": "error", "content": f"An internal error occurred during code debugging: {str(e)}"}, status_code=500)


@app.post("/fix_code")
async def fix_code_endpoint(request: CodeFixRequest):
    logging.info(f"Received request to fix {request.language} code.")
    if ryan is None or not hasattr(ryan, 'fix_code'):
         logging.error("RyanAI instance or fix_code method is not available.")
         return JSONResponse(content={"type": "error", "content": "Code fixing service is not available."}, status_code=500)
    try:
        # Call the fix_code method from RyanAI
        result = ryan.fix_code(request.original_code, request.suggested_fix, request.language, context=request.context)
        logging.info(f"Code fixing result: Success={result.get('success')}")
        return JSONResponse(content=result)
    except Exception as e:
        logging.error(f"Error fixing code: {e}")
        logging.error(traceback.format_exc())
        return JSONResponse(content={"type": "error", "content": f"An internal error occurred during code fixing: {str(e)}"}, status_code=500)


@app.post("/analyze_code")
async def analyze_code_endpoint(request: CodeAnalysisRequest):
    logging.info(f"Received request to analyze code.")
    if ryan is None or not hasattr(ryan, 'analyze_code'):
         logging.error("RyanAI instance or analyze_code method is not available.")
         return JSONResponse(content={"type": "error", "content": "Code analysis service is not available."}, status_code=500)
    try:
        # Call the analyze_code method from RyanAI
        result = ryan.analyze_code(request.code, request.task_description, context=request.context)
        logging.info(f"Code analysis result: Success={result.get('success')}")
        return JSONResponse(content=result)
    except Exception as e:
        logging.error(f"Error analyzing code: {e}")
        logging.error(traceback.format_exc())
        return JSONResponse(content={"type": "error", "content": f"An internal error occurred during code analysis: {str(e)}"}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

