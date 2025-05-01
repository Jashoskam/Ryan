import os
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
import re
import google.generativeai as genai
import time
import uuid
import importlib
import logging
import traceback
import json
from typing import Optional, Dict, Any, List
import subprocess # Import subprocess to run external commands (like code execution)
import sys # Import sys to get Python executable path

# load .env
dotenv_path = "ryanEnv.env"
load_dotenv(dotenv_path=dotenv_path)

# environment variables
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- Configure Logging ---
# Ensure logging is configured only once
if not logging.getLogger().handlers:
    # Set level to DEBUG temporarily to see more detailed logs for debugging
    logging.basicConfig(filename="app.log", level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # Add a StreamHandler to also see logs in the console during development
    # logging.getLogger().addHandler(logging.StreamHandler())

logging.info("ryan_ai.py started.")

# --- Firebase Initialization ---
db = None
CURRENT_USER_ID = "default_user" # Default user ID for now

if FIREBASE_CREDENTIALS_PATH and os.path.exists(FIREBASE_CREDENTIALS_PATH):
    try:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        logging.info("Firebase initialized successfully.")
    except Exception as e:
        logging.error(f"Firebase initialization failed: {e}")
        logging.error(traceback.format_exc())
        db = None
else:
    logging.warning(f"Firebase credentials file not found at {FIREBASE_CREDENTIALS_PATH}. Memory functions will be disabled.")
    db = None

# --- Google Generative AI Initialization ---
genai.configure(api_key=GOOGLE_API_KEY)

try:
    # Using a model good for chat and potentially function calling
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    logging.info("Google Generative AI model initialized.")
except Exception as e:
    logging.error(f"Google Generative AI model initialization failed: {e}")
    logging.error(traceback.format_exc())
    model = None


# --- RyanAI Class ---
class RyanAI:
    def __init__(self, db_instance):
        self.db = db_instance
        self.memory_collection = self.db.collection('users').document(CURRENT_USER_ID).collection('memory') if self.db else None
        logging.info(f"RyanAI instance created. Memory enabled: {self.db is not None}")

    # --- Memory Functions (Keep existing functions) ---
    # save_memory, get_memory, get_all_memory, delete_memory
    # ... (Paste your existing memory functions here)
    def save_memory(self, key: str, value: Any) -> bool:
        """Saves a key-value pair to the user's memory."""
        if not self.db or not self.memory_collection:
            logging.warning("Memory system not available. Cannot save memory.")
            return False
        if not key or not value:
             logging.warning(f"Attempted to save memory with empty key or value: key='{key}', value='{value}'. Aborting save.")
             return False
        try:
            # Use the key as the document ID for easy retrieval
            # Sanitize key to remove characters not allowed in Firestore document IDs
            # Firestore document IDs cannot contain '/', '.', '#', '[', ']', '*'
            # Replacing them with underscores or removing them
            sanitized_key = re.sub(r'[/.#\[\]*]', '_', key)
            # Ensure key is not empty after sanitization
            if not sanitized_key:
                 # If key becomes empty after sanitization, use a UUID as the key
                 logging.warning(f"Sanitized key for '{key}' is empty. Using UUID.")
                 sanitized_key = "memory_" + str(uuid.uuid4())

            # Use .set() with merge=True if you want to update existing fields
            # or just .set() to overwrite the document with the provided data.
            # For saving memory, overwriting with the latest value for a key seems appropriate.
            # Include a timestamp for sorting and tracking when it was saved/updated.
            self.memory_collection.document(sanitized_key).set({'value': value, 'timestamp': firestore.SERVER_TIMESTAMP})
            logging.info(f"Memory saved: '{key}' (saved as '{sanitized_key}') = '{value}' for user '{CURRENT_USER_ID}'.")
            return True
        except Exception as e:
            logging.error(f"Error saving memory '{key}' for user '{CURRENT_USER_ID}': {e}")
            logging.error(traceback.format_exc())
            return False

    def get_memory(self, key: str) -> Optional[Any]:
        """Retrieves a value from the user's memory by key."""
        if not self.db or not self.memory_collection:
            logging.warning("Memory system not available. Cannot get memory.")
            return None
        if not key:
             logging.warning("Attempted to get memory with empty key. Aborting get.")
             return None
        try:
            # Sanitize key for retrieval as well
            sanitized_key = re.sub(r'[/.#\[\]*]', '_', key)
             # If key was originally empty and saved with UUID, retrieval by original key won't work
             # This simple sanitization works if the original key was non-empty.
             # A more robust system might store the original key alongside the sanitized ID.
            if not sanitized_key:
                 logging.warning(f"Cannot retrieve memory for empty or invalid key '{key}'.")
                 return None

            doc = self.memory_collection.document(sanitized_key).get()
            if doc.exists:
                data = doc.to_dict()
                # Return the value if it exists in the document data
                if data and 'value' in data:
                    logging.info(f"Memory retrieved: '{key}' (from '{sanitized_key}') = '{data.get('value')}' for user '{CURRENT_USER_ID}'.")
                    return data.get('value')
                else:
                    logging.warning(f"Memory document '{sanitized_key}' exists but has no 'value' field for user '{CURRENT_USER_ID}'.")
                    return None # Document exists but doesn't have the expected 'value' field
            else:
                logging.info(f"Memory key '{key}' (sanitized to '{sanitized_key}') not found for user '{CURRENT_USER_ID}'.")
                return None # Document does not exist
        except Exception as e:
            logging.error(f"Error getting memory '{key}' for user '{CURRENT_USER_ID}': {e}")
            logging.error(traceback.format_exc())
            return None

    def get_all_memory(self) -> Dict[str, Any]:
        """Retrieves all memory entries for the user."""
        if not self.db or not self.memory_collection:
            logging.warning("Memory system not available. Cannot get all memory.")
            return {}
        try:
            docs = self.memory_collection.stream()
            # Build a dictionary of memory entries using the document ID as the key
            # and the 'value' field from the document data.
            all_memory = {}
            for doc in docs:
                memory_data = doc.to_dict()
                if memory_data and 'value' in memory_data:
                    all_memory[doc.id] = memory_data.get('value')

            logging.info(f"Retrieved all memory entries ({len(all_memory)} total) for user '{CURRENT_USER_ID}'.")
            return all_memory
        except Exception as e:
            logging.error(f"Error getting all memory for user '{CURRENT_USER_ID}': {e}")
            logging.error(traceback.format_exc())
            return {}

    def delete_memory(self, key: str) -> bool:
        """Deletes a memory entry by key."""
        if not self.db or not self.memory_collection:
            logging.warning("Memory system not available. Cannot delete memory.")
            return False
        if not key:
             logging.warning("Attempted to delete memory with empty key. Aborting delete.")
             return False
        try:
            # Sanitize key for deletion as well
            sanitized_key = re.sub(r'[/.#\[\]*]', '_', key)
            if not sanitized_key:
                 logging.warning(f"Cannot delete memory for empty or invalid key '{key}'.")
                 return False

            # Check if the document exists before attempting deletion
            doc_ref = self.memory_collection.document(sanitized_key)
            doc = doc_ref.get()

            if doc.exists:
                doc_ref.delete()
                logging.info(f"Memory deleted: '{key}' (using '{sanitized_key}') for user '{CURRENT_USER_ID}'.")
                return True
            else:
                logging.warning(f"Attempted to delete non-existent memory key '{key}' (using '{sanitized_key}') for user '{CURRENT_USER_ID}'.")
                return False # Indicate that the key was not found

        except Exception as e:
            logging.error(f"Error deleting memory '{key}' for user '{CURRENT_USER_ID}': {e}")
            logging.error(traceback.format_exc())
            return False


    # --- New Coding Genius Functions ---

    def execute_code(self, code_string: str, language: str) -> Dict[str, Any]:
        """
        Executes a string of code in the specified language on the local machine.
        Returns output, errors, and exit code.
        """
        logging.info(f"Attempting to execute {language} code.")
        logging.debug(f"Code:\n{code_string[:500]}...") # Log first 500 chars of code

        # Define commands to run code based on language
        # IMPORTANT: This is a basic implementation.
        # For a real application, consider security implications of running arbitrary code.
        # Sandboxing or containerization is highly recommended for untrusted code.
        commands = {
            'python': [sys.executable, '-c', code_string], # Use the current Python interpreter
            'javascript': ['node', '-e', code_string], # Requires Node.js installed
            # Add more languages as needed, e.g., 'java', 'c++', 'ruby', 'go'
            # Example for Java (requires saving to a .java file first):
            # 'java': ['javac', 'Temp.java', '&&', 'java', 'Temp'] # More complex
            # Example for C++ (requires saving to a .cpp file first):
            # 'cpp': ['g++', '-o', 'temp_exec', 'Temp.cpp', '&&', './temp_exec'] # More complex
        }

        language_lower = language.lower()
        if language_lower not in commands:
            logging.warning(f"Unsupported language for execution: {language}")
            return {"type": "code_execution_result", "success": False, "language": language, "output": "", "error": f"Unsupported language: {language}", "return_code": 1}

        command = commands[language_lower]
        process = None # Initialize process variable

        try:
            logging.debug(f"Executing command: {' '.join(command)}")
            # Use subprocess.run for Python 3.5+
            # capture_output=True captures stdout and stderr
            # text=True decodes stdout/stderr as text using default encoding
            # timeout can prevent infinite loops
            # Added check=False so it doesn't raise CalledProcessError for non-zero exit codes
            process = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False) # 30 second timeout

            logging.info(f"Code execution finished for {language}. Return code: {process.returncode}")
            logging.debug(f"STDOUT:\n{process.stdout[:500]}...")
            logging.debug(f"STDERR:\n{process.stderr[:500]}...")

            return {
                "type": "code_execution_result",
                "success": process.returncode == 0, # Success if return code is 0
                "language": language,
                "output": process.stdout,
                "error": process.stderr,
                "return_code": process.returncode
            }

        except FileNotFoundError:
            logging.error(f"Interpreter for {language} not found. Command: {command[0]}")
            return {"type": "code_execution_result", "success": False, "language": language, "output": "", "error": f"Interpreter for {language} not found. Make sure '{command[0]}' is installed and in your PATH.", "return_code": 1}
        except subprocess.TimeoutExpired:
            logging.warning(f"Code execution timed out after 30 seconds for {language}.")
            # If the process is still running after timeout, terminate it
            if process and process.poll() is None:
                 try:
                      process.terminate()
                      process.wait(timeout=5) # Wait a bit for termination
                 except subprocess.TimeoutExpired:
                      process.kill() # If termination fails, kill it
            return {"type": "code_execution_result", "success": False, "language": language, "output": "", "error": f"Code execution timed out after 30 seconds.", "return_code": 1}
        except Exception as e:
            logging.error(f"An error occurred during code execution for {language}: {e}")
            logging.error(traceback.format_exc())
            # Return a structured error response
            return {"type": "error", "content": f"An unexpected error occurred during code execution: {str(e)}"}


    def debug_code(self, code_string: str, error_output: str, language: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Uses the AI model to analyze code and an error message, suggesting fixes.
        Includes relevant memory as context.
        """
        logging.info(f"Attempting to debug {language} code using AI.")
        logging.debug(f"Code:\n{code_string[:500]}...")
        logging.debug(f"Error Output:\n{error_output[:500]}...")
        logging.debug(f"Context:\n{context[:500] if context else 'None'}...")

        if model is None:
            logging.error("AI model is not initialized. Cannot debug code.")
            return {"type": "ai_debug_result", "success": False, "suggestion": "AI model is not available."}

        # Fetch relevant memory entries to provide context to the AI
        # This is a simplified example; you might need more sophisticated context retrieval
        memory_context_string = ""
        if self.db:
            all_memory = self.get_all_memory()
            if all_memory:
                 # Simple approach: include all memory for now.
                 # A better approach would be to filter memory based on the code content,
                 # language, or error message.
                 memory_context_string = "Relevant Memory (for context):\n" + "\n".join([f"- {k}: {v}" for k, v in all_memory.items()]) + "\n\n"


        # Craft a detailed prompt for the AI
        prompt = f"""
You are Ryan, an expert coding assistant. Your task is to analyze the provided code and the error message, identify the root cause of the error, and suggest a fix.

{memory_context_string if memory_context_string else ''}

Code ({language}):
```{language}
{code_string}
```

Error Output:
```
{error_output}
```

Task:
1. Analyze the code and the error output.
2. Identify the specific line(s) causing the error if possible.
3. Explain the reason for the error in simple terms.
4. Provide a clear suggestion for how to fix the error.
5. If you can provide the corrected code, include it in a separate code block.

Respond in a helpful and clear manner. If you cannot determine the fix, explain why.
"""
        logging.debug(f"Prompt for AI Debugging:\n{prompt[:1000]}...") # Log first 1000 chars

        try:
            response = model.generate_content(prompt)

            if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                 logging.warning(f"AI Debugging prompt blocked: {response.prompt_feedback.block_reason}")
                 return {"type": "ai_debug_result", "success": False, "suggestion": "My analysis was blocked due to safety concerns."}
            if hasattr(response, 'candidates') and not response.candidates:
                 logging.warning("No AI candidates returned for debugging prompt.")
                 return {"type": "ai_debug_result", "success": False, "suggestion": "I couldn't generate a debugging suggestion at this time."}

            ai_response_text = ""
            try:
                ai_response_text = response.text
            except ValueError as e:
                logging.error(f"Error extracting text from AI debug response: {e}")
                return {"type": "ai_debug_result", "success": False, "suggestion": "I had trouble processing the AI's response."}

            logging.info(f"AI Debugging response received (text): '{ai_response_text[:500]}...'")

            # Parse the AI's response to extract the suggestion and potentially corrected code
            # This parsing logic might need refinement based on how the AI typically responds
            suggestion = ai_response_text # Default to the full text as suggestion
            corrected_code = None

            # Look for a code block in the response
            code_match = re.search(r'```(?:\w+)?\n(.*?)\n```', ai_response_text, re.DOTALL)
            if code_match:
                corrected_code = code_match.group(1).strip()
                # Optionally, remove the code block from the suggestion text
                suggestion = ai_response_text.replace(code_match.group(0), "").strip()


            return {
                "type": "ai_debug_result",
                "success": True,
                "suggestion": suggestion,
                "corrected_code": corrected_code,
                "raw_ai_response": ai_response_text # Include raw response for debugging
            }

        except Exception as e:
            logging.error(f"Error during AI debugging: {e}")
            logging.error(traceback.format_exc())
            # Return a structured error response
            return {"type": "error", "content": f"An error occurred during AI debugging: {str(e)}"}


    def fix_code(self, original_code: str, suggested_fix: str, language: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Applies a suggested fix to the original code.
        This could be as simple as replacing the code with the 'corrected_code' from debug_code,
        or more complex if the fix is a description.
        """
        logging.info(f"Attempting to apply fix to {language} code.")
        logging.debug(f"Original Code:\n{original_code[:500]}...")
        logging.debug(f"Suggested Fix:\n{suggested_fix[:500]}...")

        # Simple implementation: If the suggested_fix looks like code (e.g., starts with ```),
        # assume it's the corrected code and return it.
        # Otherwise, you might need to use the AI again to interpret the natural language suggestion
        # and apply it to the code.

        # Check if the suggested_fix is a code block
        code_match = re.match(r'```(?:\w+)?\n(.*?)\n```', suggested_fix.strip(), re.DOTALL)

        if code_match:
            corrected_code = code_match.group(1).strip()
            logging.info("Applied fix by replacing with provided code block.")
            return {
                "type": "code_fix_result",
                "success": True,
                "fixed_code": corrected_code,
                "message": "Applied fix using the provided code block."
            }
        else:
            # If the fix is not a code block, you might need to use the AI to apply it.
            # This is more complex and requires another AI call.
            logging.warning("Suggested fix is not a code block. Attempting to use AI to apply fix.")

            if model is None:
                 logging.error("AI model is not initialized. Cannot use AI to apply fix.")
                 return {"type": "code_fix_result", "success": False, "message": "AI model is not available to apply the fix."}

            # Craft a prompt for the AI to apply the natural language fix
            prompt = f"""
You are Ryan, an expert coding assistant. Apply the following suggested fix to the original code.

Original Code ({language}):
```{language}
{original_code}
```

Suggested Fix (Description):
{suggested_fix}

Task:
Apply the suggested fix to the original code and provide the complete corrected code in a code block. If you cannot apply the fix, explain why.

Provide only the corrected code in a code block, or an explanation if you cannot apply it.
"""
            logging.debug(f"Prompt for AI Fix Application:\n{prompt[:1000]}...")

            try:
                response = model.generate_content(prompt)

                if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                     logging.warning(f"AI Fix Application prompt blocked: {response.prompt_feedback.block_reason}")
                     return {"type": "code_fix_result", "success": False, "message": "My attempt to apply the fix was blocked due to safety concerns."}
                if hasattr(response, 'candidates') and not response.candidates:
                     logging.warning("No AI candidates returned for fix application prompt.")
                     return {"type": "code_fix_result", "success": False, "message": "I couldn't apply the fix using AI at this time."}

                ai_response_text = ""
                try:
                    ai_response_text = response.text
                except ValueError as e:
                    logging.error(f"Error extracting text from AI fix response: {e}")
                    return {"type": "code_fix_result", "success": False, "message": "I had trouble processing the AI's response for applying the fix."}

                logging.info(f"AI Fix Application response received (text): '{ai_response_text[:500]}...'")

                # Look for the corrected code block in the AI's response
                code_match_in_response = re.search(r'```(?:\w+)?\n(.*?)\n```', ai_response_text, re.DOTALL)

                if code_match_in_response:
                    corrected_code = code_match_in_response.group(1).strip()
                    logging.info("Applied fix using AI interpretation.")
                    return {
                        "type": "code_fix_result",
                        "success": True,
                        "fixed_code": corrected_code,
                        "message": "Applied fix using AI interpretation of the suggestion."
                    }
                else:
                    # If the AI didn't provide a code block, return its explanation
                    logging.warning("AI did not provide a code block for the fix.")
                    return {
                        "type": "code_fix_result",
                        "success": False,
                        "message": f"AI could not apply the fix or did not provide corrected code. AI response: {ai_response_text.strip()[:200]}..." # Return snippet of AI response
                    }

            except Exception as e:
                logging.error(f"Error during AI fix application: {e}")
                logging.error(traceback.format_exc())
                # Return a structured error response
                return {"type": "error", "content": f"An error occurred during AI fix application: {str(e)}"}


    def analyze_code(self, code_string: str, task_description: Optional[str] = None, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Uses the AI model to analyze code, explain it, or determine if it meets a task description.
        Includes relevant memory as context.
        """
        logging.info(f"Attempting to analyze code using AI.")
        logging.debug(f"Code:\n{code_string[:500]}...")
        logging.debug(f"Task Description: {task_description}")
        logging.debug(f"Context:\n{context[:500] if context else 'None'}...")

        if model is None:
            logging.error("AI model is not initialized. Cannot analyze code.")
            return {"type": "ai_analysis_result", "success": False, "analysis": "AI model is not available."}

        # Fetch relevant memory entries for context
        memory_context_string = ""
        if self.db:
            all_memory = self.get_all_memory()
            if all_memory:
                 memory_context_string = "Relevant Memory (for context):\n" + "\n".join([f"- {k}: {v}" for k, v in all_memory.items()]) + "\n\n"

        # Craft a prompt for the AI to analyze the code
        prompt = f"""
You are Ryan, an expert coding assistant. Analyze the provided code.

{memory_context_string if memory_context_string else ''}

Code:
```
{code_string}
```

Task:
{task_description if task_description else "Explain what this code does in detail."}

Provide a clear and concise analysis or explanation. If the task description asks if the code meets certain criteria, answer that question directly.
"""
        logging.debug(f"Prompt for AI Analysis:\n{prompt[:1000]}...")

        try:
            response = model.generate_content(prompt)

            if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                 logging.warning(f"AI Analysis prompt blocked: {response.prompt_feedback.block_reason}")
                 return {"type": "ai_analysis_result", "success": False, "analysis": "My analysis was blocked due to safety concerns."}
            if hasattr(response, 'candidates') and not response.candidates:
                 logging.warning("No AI candidates returned for analysis prompt.")
                 return {"type": "ai_analysis_result", "success": False, "analysis": "I couldn't perform the analysis at this time."}

            ai_response_text = ""
            try:
                ai_response_text = response.text
            except ValueError as e:
                logging.error(f"Error extracting text from AI analysis response: {e}")
                return {"type": "ai_analysis_result", "success": False, "analysis": "I had trouble processing the AI's response."}

            logging.info(f"AI Analysis response received (text): '{ai_response_text[:500]}...'")

            return {
                "type": "ai_analysis_result",
                "success": True,
                "analysis": ai_response_text.strip(),
                "raw_ai_response": ai_response_text # Include raw response for debugging
            }

        except Exception as e:
            logging.error(f"Error during AI analysis: {e}")
            logging.error(traceback.format_exc())
            # Return a structured error response
            return {"type": "error", "content": f"An error occurred during AI analysis: {str(e)}"}


    # --- Modified Chatbot Function to Route Coding Tasks ---

    def chatbot(self, user_input: str, creative_context: Optional[str] = None) -> Dict[str, Any]:
        """
        Processes user input, interacts with memory/tools, and generates a response.
        Now includes routing for coding tasks.
        """
        logging.info(f"Received user input: '{user_input}'")
        logging.debug(f"Received creative_context: {creative_context}")

        if model is None:
            logging.error("AI model is not initialized.")
            # Even if AI is down, we might still handle some commands like memory retrieval
            # For now, return error if AI is needed for the task.
            # If the task is a memory command, it will be handled before this check.
            # Let's allow memory commands to pass through.
            pass # Continue to check for memory commands

        lower_input = user_input.lower().strip()

        # --- Memory Interaction Logic (Keep existing logic) ---
        # Check for memory saving, retrieval, deletion commands first
        # ... (Paste your existing memory interaction logic here)
        # Use flags to track if a save command was detected
        save_command_detected = False
        memory_saved_successfully = False
        memory_save_response = None # To hold the response message after saving

        # 1. Specific structure: "remember that X is Y"
        # Adjusted regex to be more precise and handle potential leading/trailing spaces in groups
        save_is_match = re.match(r"^(remember|save|store)\s+that\s+(.*?)\s+is\s+(.*?)\s*$", lower_input)
        if save_is_match and self.db:
            save_command_detected = True
            key = save_is_match.group(2).strip()
            value = save_is_match.group(3).strip()
            logging.debug(f"Detected 'remember that X is Y' pattern. Key: '{key}', Value: '{value}'")
            if key and value:
                success = self.save_memory(key, value)
                if success:
                    memory_saved_successfully = True
                    memory_save_response = {"type": "text", "content": f"Okay, I'll remember that {key} is {value}."}
                else:
                    memory_save_response = {"type": "text", "content": "I had trouble saving that to memory."}
            else:
                 logging.warning(f"Detected 'remember that X is Y' pattern but extracted empty key or value. Key: '{key}', Value: '{value}'.")
                 # Don't set memory_save_response here, fall through to potentially general save or AI

        # 2. Specific structure: "remember I like X"
        # Adjusted regex
        i_like_match = re.match(r"^(remember|save|store)\s+(?:that\s+)?i\s+like\s+(.*?)\s*$", lower_input)
        if i_like_match and self.db and not save_command_detected: # Only check if specific 'is' pattern wasn't matched
            save_command_detected = True
            key = "user_likes" # Consistent key for user likes
            value = i_like_match.group(2).strip() # What the user likes
            logging.debug(f"Detected 'remember I like X' pattern. Key: '{key}', Value: '{value}'")
            if value:
                 success = self.save_memory(key, value)
                 if success:
                      memory_saved_successfully = True
                      memory_save_response = {"type": "text", "content": f"Okay, I'll remember that you like {value}."}
                 else:
                      memory_save_response = {"type": "text", "content": "I had trouble saving that to memory."}
            else:
                 logging.warning(f"Detected 'remember I like X' pattern but extracted empty value. Value: '{value}'.")
                 # Don't set memory_save_response here, fall through

        # 3. More general memory saving: "remember X", "save Y", "store that Z"
        # This should catch "remember Aryan likes dogs" and "Aryan prefers cool kids"
        # Refined regex to be more general after the trigger words
        # Added optional "me to" after remember/save/store
        # Adjusted regex to capture the rest of the sentence after the trigger
        save_general_match = re.match(r"^(remember|save|store)(?: me to)?\s+(?:that\s+)?(.*?)\s*$", lower_input)
        # Only check if a save command hasn't been detected by more specific patterns
        if save_general_match and self.db and not save_command_detected:
            save_command_detected = True
            fact_to_remember = save_general_match.group(2).strip()
            logging.debug(f"Detected general save pattern. Fact to remember: '{fact_to_remember}'")

            # Only proceed if a fact was actually provided after the trigger
            if fact_to_remember:
                # For general facts, we can try to extract a subject and predicate,
                # or just save the whole fact with a descriptive key.
                # Let's use a more robust approach to extract potential subject and predicate.
                # This is still a heuristic and might not be perfect for all sentences.

                key = None
                value = None

                # Attempt to find a simple subject-verb-object structure
                # Look for common verbs/phrases that indicate a fact
                # Added more potential relations
                # Made the relation match non-greedy (.*?) to avoid matching too much
                relation_match = re.match(r"^(.*?)\s+(likes|prefers|is|has|works at|lives in|enjoys|hates|loves|wants)\s+(.*?)\s*$", fact_to_remember)

                if relation_match:
                    key = relation_match.group(1).strip() # Subject (e.g., "aryan")
                    relation = relation_match.group(2).strip() # Relation (e.g., "likes", "prefers")
                    obj = relation_match.group(3).strip() # Object (e.g., "dogs", "cool kids")
                    # Combine relation and object for the value
                    value = f"{relation} {obj}"
                    logging.debug(f"Extracted key '{key}', value '{value}' from general fact.")
                else:
                    # Fallback for other general facts: use the first word as key prefix + UUID, and the whole fact as value
                    key_prefix_parts = fact_to_remember.split()[:3] # Use first up to 3 words for prefix
                    key_prefix = "_".join(key_prefix_parts).replace(' ', '_').replace('.', '').replace(',', '').replace('!', '').replace('?', '').lower()[:30] # Sanitize and limit length, lowercase
                    if not key_prefix:
                         key_prefix = "general"
                    # Ensure the key is valid and somewhat descriptive
                    key = f"fact_{key_prefix}_{str(uuid.uuid4())[:8]}" # Add UUID part for uniqueness
                    value = fact_to_remember # The full fact is the value
                    logging.debug(f"Using fallback save logic for fact: '{fact_to_remember}' with key '{key}'.")


                # Ensure extracted key and value are not empty before saving
                if key and value:
                    success = self.save_memory(key, value)
                    if success:
                        memory_saved_successfully = True
                        # Provide a confirmation that acknowledges the saved fact
                        # Make the confirmation slightly more dynamic based on the extracted key/value if possible
                        if relation_match:
                             # Reconstruct the original phrasing for the response if a relation was found
                             # Use original user_input parts if possible for better phrasing
                             original_subject = relation_match.group(1).strip()
                             original_relation = relation_match.group(2).strip()
                             original_object = relation_match.group(3).strip()
                             memory_save_response = {"type": "text", "content": f"Okay, I'll remember that {original_subject} {original_relation} {original_object}."}
                        else:
                             # Default confirmation for fallback saves using the full fact
                             memory_save_response = {"type": "text", "content": f"Okay, I'll remember that: {fact_to_remember}."}
                    else:
                        memory_save_response = {"type": "text", "content": "I had trouble saving that to memory."}
                else:
                    # If key or value extraction failed for a non-empty fact
                    logging.warning(f"Could not extract key/value from general fact: '{fact_to_remember}'. Skipping save.")
                    # Don't set memory_save_response here, fall through to AI

            # If fact_to_remember is empty after parsing, fall through

        # If a save command was detected and a response was generated, return it immediately
        if save_command_detected and memory_save_response:
             logging.info("Memory save command processed, returning save response.")
             return memory_save_response

        # If a save command was detected but no response was generated (e.g., empty key/value),
        # let the AI handle it as a regular query.
        if save_command_detected and not memory_save_response:
             logging.warning("Memory save command detected but no valid save occurred. Passing to AI.")


        # --- Check for specific memory retrieval commands (e.g., "what do I like", "what is my bday") ---
        # Prioritize these direct questions before general entity queries
        # Added a new pattern specifically for asking about user's likes
        get_my_likes_match = re.match(r"^(?:what do i like|what do you know i like|what are my likes)\s*\??$", lower_input)

        # Refined existing regexes to be more flexible with "my" or "your" and the attribute
        # Added more question words and made the attribute capture more flexible
        get_attribute_match = re.match(r"^(?:what|when|where|who) is (my|your)\s+(.*?)\s*$", lower_input) # Catches "what is my name", "when is my bday"
        get_do_you_know_match = re.match(r"^do you know (my|your)\s+(.*?)\s*$", lower_input) # Catches "do you know my name"
        get_what_about_match = re.match(r"^what about (my|your)\s+(.*?)\s*$", lower_input) # Catches "what about my job"


        retrieved_value = None
        retrieval_key = None
        retrieval_detected = False # Flag to indicate if a retrieval pattern was matched

        # --- Check for user likes retrieval first ---
        if get_my_likes_match and self.db:
             retrieval_detected = True
             logging.debug("Detected 'what do I like' pattern. Attempting to retrieve 'user_likes' memory.")
             retrieved_value = self.get_memory("user_likes")

             if retrieved_value is not None:
                  return {"type": "text", "content": f"You like {retrieved_value}."}
             else:
                  logging.debug("'user_likes' memory not found. Proceeding to AI.")
                  # Fall through to AI if not found

        # --- Check for other specific attribute retrievals ---
        elif get_attribute_match and self.db:
             retrieval_detected = True
             retrieval_key_part = get_attribute_match.group(2).strip() # e.g., "bday", "name"
             # Construct potential keys to check in memory
             potential_keys = [retrieval_key_part, f"my {retrieval_key_part}", f"your {retrieval_key_part}"]
             logging.debug(f"Detected 'what/when/where/who is my/your X' pattern. Potential keys: {potential_keys}")

             # Try retrieving with potential keys
             for key_to_try in potential_keys:
                  retrieved_value = self.get_memory(key_to_try)
                  if retrieved_value is not None:
                       retrieval_key = key_to_try # Store the key that worked
                       break # Stop searching once found

             if retrieved_value is not None:
                 # Construct response based on the original question type if possible
                 question_word = get_attribute_match.group(1).strip()
                 if question_word == 'what':
                      return {"type": "text", "content": f"Your {retrieval_key_part} is {retrieved_value}."}
                 elif question_word == 'when':
                      return {"type": "text", "content": f"Your {retrieval_key_part} is {retrieved_value}."} # Assuming bday/date
                 elif question_word == 'where':
                      return {"type": "text", "content": f"Your {retrieval_key_part} is {retrieved_value}."} # Assuming location
                 elif question_word == 'who':
                      return {"type": "text", "content": f"Your {retrieval_key_part} is {retrieved_value}."} # Assuming a person/role
                 else: # Fallback if question word is unexpected
                      return {"type": "text", "content": f"I remember your {retrieval_key_part} is {retrieved_value}."}

             else:
                 logging.debug(f"Specific memory keys not found for 'what/when/where/who is my/your X'. Proceeding to AI.")
                 pass # Fall through to AI if not found by direct key

        elif get_do_you_know_match and self.db:
             retrieval_detected = True
             retrieval_key_part = get_do_you_know_match.group(2).strip() # e.g., "name"
             potential_keys = [retrieval_key_part, f"my {retrieval_key_part}", f"your {retrieval_key_part}"]
             logging.debug(f"Detected 'do you know my/your X' pattern. Potential keys: {potential_keys}")

             for key_to_try in potential_keys:
                  retrieved_value = self.get_memory(key_to_try)
                  if retrieved_value is not None:
                       retrieval_key = key_to_try
                       break

             if retrieved_value is not None:
                 return {"type": "text", "content": f"Yes, I know your {retrieval_key_part} is {retrieved_value}."}
             else:
                 logging.debug(f"Specific memory keys not found for 'do you know my/your X'. Proceeding to AI.")
                 pass # Fall through

        elif get_what_about_match and self.db:
             retrieval_detected = True
             retrieval_key_part = get_what_about_match.group(2).strip() # e.g., "job"
             potential_keys = [retrieval_key_part, f"my {retrieval_key_part}", f"your {retrieval_key_part}"]
             logging.debug(f"Detected 'what about my/your X' pattern. Potential keys: {potential_keys}")

             for key_to_try in potential_keys:
                  retrieved_value = self.get_memory(key_to_try)
                  if retrieved_value is not None:
                       retrieval_key = key_to_try
                       break

             if retrieved_value is not None:
                 return {"type": "text", "content": f"Regarding your {retrieval_key_part}, I remember: {retrieved_value}."}
             else:
                 logging.debug(f"Specific memory keys not found for 'what about my/your X'. Proceeding to AI.")
                 pass # Fall through


        # --- Enhanced: Check if the user is asking about a specific entity in memory ---
        # This regex attempts to capture phrases like "what do you know about X", "tell me about Y", "who is Z", "what about X", "what does X like"
        # Added more flexible matching for the entity name and question phrasing.
        # Crucially, ensure group 2 is always captured if there's a match.
        # Made the entity capture more robust by including common possessives like "'s"
        # Added more question starters and made the entity capture more flexible
        # Added word boundaries (\b) around the trigger phrases for more accurate matching
        entity_query_match = re.search(r"\b(?:tell me about|what do you know about|who is|what about|what does|info on|details on)\b\s+(.+?)(?:'s)?(?:\s+like|\s+prefer|\s+have|\s+work at|\s+live in|enjoys?|hates?|loves?|wants?)?(?:\?)?$", lower_input) # Added more starters, 's, optional relations/question mark


        memory_context_string = ""
        queried_entity_name = None # Store the extracted entity name

        # Only perform general entity search if no specific retrieval pattern was matched
        if entity_query_match and self.db and not retrieval_detected:
            # Check if group 2 exists and is not empty before accessing it
            if len(entity_query_match.groups()) >= 1 and entity_query_match.group(1): # Corrected group index to 1 for the entity capture
                queried_entity_name = entity_query_match.group(1).strip()
                logging.info(f"Detected query about entity: '{queried_entity_name}'. Searching memory.")

                # Fetch all memory entries
                all_memory = self.get_all_memory()

                # Filter memory entries that contain the entity name in either the key or value
                # Also, include the "user_likes" memory if the entity name is related to what the user likes (e.g., "cats")
                relevant_memory_entries = {}
                for key, value in all_memory.items():
                     # Check if entity name is in the key or value (case-insensitive)
                     # This is a broad search; for better results, consider stemming or fuzzy matching
                     if queried_entity_name in key.lower() or (isinstance(value, str) and queried_entity_name in value.lower()):
                          # Prioritize exact key matches or specific structures if needed
                          relevant_memory_entries[key] = value
                     # Explicitly check the "user_likes" key if the entity name is the liked item
                     if key.lower() == "user_likes" and isinstance(value, str) and queried_entity_name in value.lower():
                          relevant_memory_entries[key] = value
                     # Add check for keys that are similar to the entity name after sanitization
                     sanitized_entity_name = re.sub(r'[/.#\[\]*]', '_', queried_entity_name)
                     if sanitized_entity_name and sanitized_entity_name in key.lower():
                          relevant_memory_entries[key] = value

                     # Also check for "my [entity_name]" or "[entity_name]'s" as a key, e.g., "my bday", "aryan_s_dog"
                     if f"my {queried_entity_name}" in key.lower() or f"{sanitized_entity_name}_s" in key.lower():
                          relevant_memory_entries[key] = value


                logging.debug(f"Found {len(relevant_memory_entries)} relevant memory entries for '{queried_entity_name}'.")

                # Format the relevant memory entries into a string to include in the prompt
                if relevant_memory_entries:
                    memory_context_string = "Relevant Memory:\n"
                    # Iterate through sorted keys for consistent order in the prompt
                    for key in sorted(relevant_memory_entries.keys()):
                        value = relevant_memory_entries[key]
                        # Format based on key structure or just key: value
                        if key == "user_likes":
                            memory_context_string += f"- User likes: {value}\n"
                        elif key.startswith("fact_"):
                             # For general facts saved with the 'fact_' prefix, just include the value (the full fact)
                             memory_context_string += f"- {value}\n"
                        # Add formatting for relations if the key is the subject
                        # This part might need refinement based on how you want to represent saved facts
                        # For now, keeping a simple key: value or subject relation object format
                        elif isinstance(value, str) and any(value.startswith(rel + " ") for rel in ["likes", "prefers", "is", "has", "works at", "lives in", "enjoys", "hates", "loves", "wants"]):
                             # Attempt to reconstruct the subject from the key if it's a relation type
                             # This is heuristic and might not be perfect
                             subject_from_key = key.replace('_s', '').replace('fact_', '').replace('_', ' ').strip()
                             if subject_from_key:
                                 memory_context_string += f"- {subject_from_key} {value}\n"
                             else:
                                 memory_context_string += f"- {key}: {value}\n" # Fallback
                        else:
                             # Default key: value format
                             memory_context_string += f"- {key}: {value}\n"

                    memory_context_string += "\n" # Add a newline to separate from the user query
                    logging.debug("Formatted memory context:\n" + memory_context_string)
                else:
                    logging.debug(f"No relevant memory found for '{queried_entity_name}'.")
            else:
                 # If entity_query_match was true but entity name could not be extracted
                 logging.warning(f"Entity query pattern matched, but entity name could not be extracted from '{user_input}'.")
                 # Fall through to general AI processing without memory context
                 pass # Continue to prompt preparation


        # --- New: Check for Coding Task Commands ---
        # These regexes are examples; you'll need to refine them based on
        # the natural language commands you want Ryan to understand.

        # Example: "run this python code: ```python ... ```"
        # Capture the language and the code block
        run_code_match = re.search(r"^(?:run|execute)(?: this)?\s+(python|javascript|java|cpp|c|ruby|go)?\s*code:\s*```(?:\w+)?\n(.*?)\n```", lower_input, re.DOTALL)

        # Example: "debug this error in my code: ```...``` Error: ..."
        # Capture the code block and the error message
        debug_code_match = re.search(r"^(?:debug|fix|help with)(?: this)?(?: error)?(?: in my)?\s+(python|javascript|java|cpp|c|ruby|go)?\s*code:\s*```(?:\w+)?\n(.*?)\n```(?:\s*error:?\s*(.*?))?$", lower_input, re.DOTALL)

        # Example: "analyze this code: ```...``` What does it do?"
        # Capture the code block and the task description
        analyze_code_match = re.search(r"^(?:analyze|explain|what does)(?: this)?\s+(python|javascript|java|cpp|c|ruby|go)?\s*code:\s*```(?:\w+)?\n(.*?)\n```(?:\s*(.*?))?$", lower_input, re.DOTALL)


        # --- Route to appropriate function based on command ---

        if run_code_match:
            logging.info("Detected 'run code' command.")
            language = run_code_match.group(1) or 'python' # Default to python if language not specified
            code_string = run_code_match.group(2).strip()
            # Call the new execute_code method
            return self.execute_code(code_string, language)

        elif debug_code_match:
            logging.info("Detected 'debug code' command.")
            language = debug_code_match.group(1) or 'unknown' # Default to unknown if language not specified
            code_string = debug_code_match.group(2).strip()
            error_output = debug_code_match.group(3).strip() if debug_code_match.group(3) else ""
            # Call the new debug_code method
            # Pass creative_context or relevant memory as context if available
            context_for_debug = creative_context if creative_context else memory_context_string
            return self.debug_code(code_string, error_output, language, context=context_for_debug)

        elif analyze_code_match:
            logging.info("Detected 'analyze code' command.")
            language = analyze_code_match.group(1) or 'unknown' # Language might not be strictly needed for analysis by AI
            code_string = analyze_code_match.group(2).strip()
            task_description = analyze_code_match.group(3).strip() if analyze_code_match.group(3) else None
            # Call the new analyze_code method
            context_for_analyze = creative_context if creative_context else memory_context_string
            return self.analyze_code(code_string, task_description, context=context_for_analyze)


        # --- If no specific command matched, proceed to general chat or memory retrieval ---

        # --- Check for specific memory retrieval commands (already handled above) ---
        # If a retrieval command was matched and returned a response, the code would have exited already.
        # If retrieval_detected is true but no response was returned, it means the key wasn't found,
        # so we can let the AI handle it as a general query.

        # --- Prepare Prompt for Generative AI (for general chat or memory queries) ---
        # Only prepare prompt if no coding task was detected
        if model is None:
            logging.error("AI model is not initialized. Cannot process general chat.")
            return {"type": "error", "content": "AI model is not available for general chat."}

        prompt_parts = []

        # Add a system instruction or persona
        prompt_parts.append("You are Ryan, a friendly, conversational, and helpful AI assistant. You aim to sound human-like. Your primary function is to chat with the user and remember facts they tell you. **CRITICAL INSTRUCTION:** Below, under 'Relevant Memory', I might provide facts I have saved about the topic the user is asking about. If 'Relevant Memory' is present and directly relates to the user's question, you ABSOLUTELY MUST use that information to answer the question. Do NOT ignore the 'Relevant Memory' if it's relevant. If the user asks about something and there is NO 'Relevant Memory' provided for that specific topic, then you can politely say you don't have information on that, maintaining a helpful and friendly tone. Be concise and directly address the user's input.\n\n")


        # Include the memory context if found (from entity query or general retrieval attempt)
        if memory_context_string:
            prompt_parts.append(memory_context_string)

        # Include the creative context if provided (e.g., from a UI)
        if creative_context:
            prompt_parts.append(f"User is currently viewing this content:\n{creative_context}\n\n")
            logging.debug("Including creative context in prompt.")

        # Add the user's current input
        prompt_parts.append(user_input)

        final_prompt = "".join(prompt_parts)
        logging.debug(f"Final prompt sent to AI:\n{final_prompt}")


        # --- Generate Response using AI Model (for general chat) ---
        try:
            response = model.generate_content(final_prompt)

            # Check for safety ratings
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                 logging.warning(f"Prompt blocked: {response.prompt_feedback.block_reason}")
                 return {"type": "error", "content": "Your prompt was blocked due to safety concerns."}
            if hasattr(response, 'candidates') and not response.candidates:
                 logging.warning("No candidates returned for the prompt.")
                 # If no candidates, it might be due to safety filters even without a block reason
                 # Or just the model couldn't generate a response.
                 # Provide a human-like response instead of a technical error.
                 # If memory was relevant but no response, indicate that.
                 if memory_context_string:
                      # If memory was found but AI failed to respond, mention the entity
                      return {"type": "text", "content": f"Hmm, I found some information about {queried_entity_name or 'that'}, but I'm having trouble forming a response right now. Could you try asking in a different way?"}
                 else:
                      # If no memory was found and AI failed to respond
                      return {"type": "text", "content": "Hmm, I'm not sure how to respond to that right now. Could you try rephrasing?"}


            # Extract the text response
            ai_response_text = ""
            try:
                ai_response_text = response.text
            except ValueError as e:
                logging.error(f"Error extracting text from AI response: {e}")
                logging.error(traceback.format_exc())
                return {"type": "text", "content": "Oops, I had a little trouble processing that response. Could you try again?"}


            logging.info(f"AI generated response (text): '{ai_response_text[:100]}...'") # Log first 100 chars

            # --- Response Type Detection (Basic) ---
            # This is a simple way to detect if the response might be code or creative.
            # You could make this more sophisticated, perhaps by asking the AI to
            # indicate the response type in a structured format.

            # Check for code blocks (basic detection)
            if '```' in ai_response_text:
                # Assuming content within ``` is code
                 # Extract content within the first pair of ``` if multiple exist
                code_match = re.search(r'```(?:\w+)?\n(.*?)\n```', ai_response_text, re.DOTALL)
                if code_match:
                    code_content = code_match.group(1).strip()
                    logging.info("Detected code response.")
                    # You might want to clean up the text outside the code block or include it separately
                    # For now, just returning the code content
                    return {"type": "code", "content": code_content}
                else:
                    # If ``` exists but format is unexpected, treat as text
                    logging.warning("Detected ``` but could not extract code block. Treating as text.")
                    # Fall through to return as text
                    pass


            # Check for other potential creative output indicators (example)
            # This is highly dependent on how your AI is prompted to generate creative outputs
            # if "story:" in lower_input or "poem:" in lower_input or "creative:" in lower_input:
            #     logging.info("Detected potential creative response.")
            #     return {"type": "creative", "content": ai_response_text}


            # Default to text response if no other type was detected and returned
            logging.info("Defaulting to text response.")
            return {"type": "text", "content": ai_response_text}

        except Exception as e:
            logging.error(f"Error generating AI response: {e}")
            logging.error(traceback.format_exc())
            # Provide a human-like error message for generation failures
            # If memory was relevant but generation failed, indicate that.
            if memory_context_string:
                 # If memory was found but AI failed to respond, mention the entity
                 return {"type": "text", "content": f"I found some information about {queried_entity_name or 'that'}, but I ran into a problem trying to generate a response. Could you try asking in a different way?"}
            else:
                 # If no memory was found and AI failed to respond
                 return {"type": "text", "content": f"I ran into a problem trying to generate a response. Could you try asking in a different way?"}


    # --- Placeholder for other functionalities like web search ---
    def web_search(self, query: str) -> Optional[Dict[str, Any]]:
        """Performs a web search using the Google Custom Search API."""
        if not SEARCH_API_KEY or not SEARCH_ENGINE_ID:
            logging.warning("Search API key or Engine ID not configured. Cannot perform web search.")
            return None
        try:
            search_url = "[https://www.googleapis.com/customsearch/v1](https://www.googleapis.com/customsearch/v1)" # Corrected URL
            params = {
                'key': SEARCH_API_KEY,
                'cx': SEARCH_ENGINE_ID,
                'q': query
            }
            response = requests.get(search_url, params=params)
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
            search_results = response.json()
            logging.info(f"Web search performed for '{query}'. Found {search_results.get('searchInformation', {}).get('totalResults', 0)} results.")
            # You would typically process search_results here to extract relevant snippets
            # and format them for the AI or the user.
            return {"type": "search_results", "content": search_results} # Return raw results for now
        except requests.exceptions.RequestException as e:
            logging.error(f"Error during web search for '{query}': {e}")
            logging.error(traceback.format_exc())
            return {"type": "error", "content": f"Error performing web search: {str(e)}"}
        except Exception as e:
            logging.error(f"An unexpected error occurred during web search for '{query}': {e}")
            logging.error(traceback.format_exc())
            return {"type": "error", "content": f"An unexpected error occurred during web search: {str(e)}"}


    # --- Placeholder for Plugin System ---
    def run_plugin(self, plugin_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Loads and runs a plugin dynamically."""
        try:
            # Example: Dynamically import a plugin module
            # Ensure the 'plugins' directory is in your Python path if using this
            plugin_module = importlib.import_module(f"plugins.{plugin_name}")
            if hasattr(plugin_module, 'run'):
                logging.info(f"Running plugin: {plugin_name}")
                # Assume plugin has a 'run' function that takes parameters and returns a dict
                result = plugin_module.run(parameters)
                return {"type": "plugin_result", "content": result}
            else:
                logging.warning(f"Plugin '{plugin_name}' does not have a 'run' function.")
                return {"type": "error", "content": f"Plugin '{plugin_name}' is not runnable."}
        except ImportError:
            logging.error(f"Plugin '{plugin_name}' not found. Make sure it's in a 'plugins' directory and the directory is accessible.")
            return {"type": "error", "content": f"Plugin '{plugin_name}' not found."}
        except Exception as e:
            logging.error(f"Error running plugin '{plugin_name}': {e}")
            logging.error(traceback.format_exc())
            return {"type": "error", "content": f"Error running plugin '{plugin_name}': {str(e)}"}

    # --- Placeholder for Document Processing ---
    # This method is called by the /upload_document endpoint in ryan.py
    # You need to implement the logic here to process the document content,
    # e.g., extract key facts and save them to memory.
    # This should be enhanced to handle code files specifically.
    def process_document(self, file_name: str, file_content: str) -> str:
        """
        Processes uploaded document content and potentially saves to memory.
        Should be enhanced to handle code files.
        """
        logging.info(f"Processing document: {file_name}")
        # --- Document Processing Logic Goes Here ---
        # Example: Simple processing - find key-value pairs like "Key: Value"
        # This is a very basic example; real document processing would be more complex.
        # For code files, you might want to:
        # 1. Identify the language based on file extension (.py, .js, .java, etc.)
        # 2. Store the code content in memory or a dedicated project structure.
        # 3. Use AI to summarize the code or identify key functions/classes and save that to memory.
        # 4. Potentially run static analysis tools on the code.

        processed_facts = []
        lines = file_content.splitlines()

        # Basic attempt to identify language by file extension
        file_extension = os.path.splitext(file_name)[1].lower()
        language = "unknown"
        if file_extension == ".py": language = "python"
        elif file_extension == ".js": language = "javascript"
        elif file_extension == ".java": language = "java"
        elif file_extension in [".cpp", ".cxx", ".cc"]: language = "cpp"
        elif file_extension in [".c", ".h"]: language = "c"
        # Add more extensions as needed

        logging.info(f"Detected potential language '{language}' for file '{file_name}'.")

        # Option 1: Save the entire file content to memory (be mindful of size limits)
        # Use a key that includes the filename and maybe a hash for versioning
        file_memory_key = f"file_content_{file_name.replace('.', '_').replace('/', '_')}"
        success_save_content = self.save_memory(file_memory_key, file_content)
        if success_save_content:
             processed_facts.append(f"Saved content of file '{file_name}' to memory.")
        else:
             processed_facts.append(f"Failed to save content of file '{file_name}' to memory.")


        # Option 2: Use AI to summarize or extract key info from the code
        if model and language != "unknown":
             logging.info(f"Attempting to use AI to analyze content of '{file_name}'.")
             analysis_result = self.analyze_code(file_content, task_description=f"Summarize this {language} code and explain its main purpose and key functions/classes.")
             if analysis_result.get("success"):
                  analysis_key = f"file_summary_{file_name.replace('.', '_').replace('/', '_')}"
                  success_save_analysis = self.save_memory(analysis_key, analysis_result.get("analysis"))
                  if success_save_analysis:
                       processed_facts.append(f"Saved AI analysis/summary of file '{file_name}' to memory.")
                  else:
                       processed_facts.append(f"Failed to save AI analysis of file '{file_name}' to memory.")
             else:
                  processed_facts.append(f"AI analysis of file '{file_name}' failed: {analysis_result.get('analysis', 'Unknown error')}")
                  logging.error(f"AI analysis of file '{file_name}' failed: {analysis_result.get('analysis', 'Unknown error')}")
        elif language == "unknown":
             processed_facts.append(f"Could not determine language for file '{file_name}'. Skipping AI analysis.")
        else:
             processed_facts.append(f"AI model not available for analysis of file '{file_name}'.")


        # Fallback for non-code files (keep existing Key: Value logic)
        if language == "unknown":
             for line in lines:
                 line = line.strip()
                 if line:
                     kv_match = re.match(r"^(.*?):\s*(.*?)$", line)
                     if kv_match:
                         key = kv_match.group(1).strip()
                         value = kv_match.group(2).strip()
                         if key and value:
                             success = self.save_memory(key, value)
                             if success:
                                 processed_facts.append(f"Saved fact '{key}': '{value}' from '{file_name}'")
                             else:
                                 processed_facts.append(f"Failed to save fact '{key}': '{value}' from '{file_name}'")
                     else:
                         logging.debug(f"Skipping line (not Key: Value format) in non-code file: {line[:100]}...")


        if processed_facts:
            confirmation = f"Successfully processed document '{file_name}'. Actions taken:\n" + "\n".join(processed_facts)
        else:
            confirmation = f"Successfully processed document '{file_name}', but did not find specific actions to take (e.g., no code or Key: Value facts)."

        logging.info(confirmation)
        return confirmation
    # --- End Document Processing ---


# --- Standalone Execution (for testing RyanAI directly via CLI) ---
if __name__ == "__main__":
    # This block allows you to run ryan_ai.py directly from the command line
    # for basic testing of the AI, memory, and now coding functions.
    # We'll add basic argument parsing here.
    import argparse

    logging.info("Starting RyanAI in standalone mode (CLI).")

    # Initialize RyanAI instance
    ryan = RyanAI(db)

    # Setup argument parser for CLI commands
    parser = argparse.ArgumentParser(description="RyanAI Command Line Interface")
    parser.add_argument("command", help="Command to run (chat, run, debug, analyze, memory_get, memory_save, memory_delete, memory_all, process_doc)")
    parser.add_argument("--text", help="Text input for chat or analysis task description")
    parser.add_argument("--code", help="Code string for run, debug, or analyze commands")
    parser.add_argument("--lang", help="Programming language for code commands (e.g., python, javascript)", default="python")
    parser.add_argument("--error", help="Error output for debug command")
    parser.add_argument("--fix", help="Suggested fix string for fix command")
    parser.add_argument("--key", help="Memory key for get, save, or delete commands")
    parser.add_argument("--value", help="Memory value for save command")
    parser.add_argument("--file_path", help="Path to a file for process_doc command")


    # If no arguments are provided, start interactive chat mode
    if len(sys.argv) == 1:
        print("RyanAI Standalone Mode (Interactive Chat). Type 'exit' to quit.")
        while True:
            user_input = input("You: ")
            if user_input.lower() == "exit":
                logging.info("User requested exit. Shutting down.")
                print("Ryan: Goodbye!")
                break
            # In interactive mode, we only support the chatbot for now
            response_dict = ryan.chatbot(user_input)
            response_type = response_dict.get('type', 'unknown')
            response_content = response_dict.get('content', 'No content in response')
            # Print response based on type
            if response_type == "code_execution_result":
                 print(f"--- Code Execution Result ({response_dict.get('language', 'unknown')}) ---")
                 print(f"Success: {response_dict.get('success')}")
                 print(f"Return Code: {response_dict.get('return_code')}")
                 if response_dict.get('output'):
                      print("--- STDOUT ---")
                      print(response_dict.get('output'))
                 if response_dict.get('error'):
                      print("--- STDERR ---")
                      print(response_dict.get('error'))
                 print("-----------------------------------------")
            elif response_type == "ai_debug_result":
                 print("--- AI Debug Suggestion ---")
                 print(f"Suggestion: {response_dict.get('suggestion')}")
                 if response_dict.get('corrected_code'):
                      print("--- Corrected Code ---")
                      print(response_dict.get('corrected_code'))
                      print("-----------------------")
                 print("---------------------------")
            elif response_type == "ai_analysis_result":
                 print("--- AI Analysis ---")
                 print(response_dict.get('analysis'))
                 print("---------------------")
            elif response_type == "text":
                 print(f"Ryan: {response_content}")
            elif response_type == "error":
                 print(f"Error: {response_content}")
            else:
                 # Handle other potential response types from chatbot if needed
                 print(f"Ryan ({response_type}): {response_content}")

            logging.info(f"Ryan's response (type: {response_type}): '{str(response_content)[:100]}...'") # Log snippet


    else: # Handle commands provided via arguments
        args = parser.parse_args()

        if args.command == "chat":
            if not args.text:
                print("Error: --text argument is required for 'chat' command.")
            else:
                response_dict = ryan.chatbot(args.text)
                print(json.dumps(response_dict, indent=2)) # Print response as JSON

        elif args.command == "run":
            if not args.code:
                 print("Error: --code argument is required for 'run' command.")
            else:
                 response_dict = ryan.execute_code(args.code, args.lang)
                 print(json.dumps(response_dict, indent=2))

        elif args.command == "debug":
             if not args.code or not args.error:
                  print("Error: --code and --error arguments are required for 'debug' command.")
             else:
                  # In CLI mode, no creative_context, but we can pass memory context
                  memory_context = ryan.get_all_memory() # Fetch all memory as context
                  context_string = "Memory:\n" + "\n".join([f"- {k}: {v}" for k, v in memory_context.items()]) if memory_context else None
                  response_dict = ryan.debug_code(args.code, args.error, args.lang, context=context_string)
                  print(json.dumps(response_dict, indent=2))

        elif args.command == "fix":
             if not args.code or not args.fix:
                  print("Error: --code and --fix arguments are required for 'fix' command.")
             else:
                  # In CLI mode, no creative_context, but we can pass memory context
                  memory_context = ryan.get_all_memory() # Fetch all memory as context
                  context_string = "Memory:\n" + "\n".join([f"- {k}: {v}" for k, v in memory_context.items()]) if memory_context else None
                  response_dict = ryan.fix_code(args.code, args.fix, args.lang, context=context_string)
                  print(json.dumps(response_dict, indent=2))

        elif args.command == "analyze":
             if not args.code:
                  print("Error: --code argument is required for 'analyze' command.")
             else:
                  # In CLI mode, no creative_context, but we can pass memory context
                  memory_context = ryan.get_all_memory() # Fetch all memory as context
                  context_string = "Memory:\n" + "\n".join([f"- {k}: {v}" for k, v in memory_context.items()]) if memory_context else None
                  response_dict = ryan.analyze_code(args.code, args.text, context=context_string) # Use --text for task description
                  print(json.dumps(response_dict, indent=2))

        elif args.command == "memory_get":
             if not args.key:
                 print("Error: --key argument is required for 'memory_get' command.")
             else:
                 value = ryan.get_memory(args.key)
                 print(f"Value for key '{args.key}': {value}")

        elif args.command == "memory_save":
             if not args.key or not args.value:
                 print("Error: --key and --value arguments are required for 'memory_save' command.")
             else:
                 success = ryan.save_memory(args.key, args.value)
                 print(f"Memory save successful: {success}")

        elif args.command == "memory_delete":
             if not args.key:
                 print("Error: --key argument is required for 'memory_delete' command.")
             else:
                 success = ryan.delete_memory(args.key)
                 print(f"Memory delete successful: {success}")

        elif args.command == "memory_all":
            all_memory = ryan.get_all_memory()
            print("All Memory Entries:")
            for key, value in all_memory.items():
                 print(f"  {key}: {value}")

        elif args.command == "process_doc":
             if not args.file_path:
                  print("Error: --file_path argument is required for 'process_doc' command.")
             else:
                  try:
                       with open(args.file_path, 'r') as f:
                            file_content = f.read()
                       file_name = os.path.basename(args.file_path)
                       confirmation = ryan.process_document(file_name, file_content)
                       print(confirmation)
                  except FileNotFoundError:
                       print(f"Error: File not found at '{args.file_path}'")
                  except Exception as e:
                       print(f"Error reading or processing file: {e}")


        else:
            print(f"Unknown command: {args.command}")
            parser.print_help()

