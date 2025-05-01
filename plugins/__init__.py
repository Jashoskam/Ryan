# plugins/example_plugin.py

# You can import necessary libraries here
# import requests
# import os

class ExamplePlugin:
    def __init__(self, ryan_ai_instance):
        """
        Initialize the plugin.
        The ryan_ai_instance is the main RyanAI object, allowing the plugin
        to access core functionalities like querying the language model or memory.
        """
        self.ryan_ai = ryan_ai_instance
        print("ExamplePlugin initialized.") # Added print for debugging

    def handle_command(self, user_input):
        """
        Process the user input.
        If the plugin can handle the input, process it and return a response string.
        If the plugin cannot handle the input, return None.
        """
        lower_input = user_input.lower()

        # --- Example Plugin Logic ---
        # This is a simple example. Replace with your plugin's specific logic.
        if "hello plugin" in lower_input:
            return "Hello from the Example Plugin!"

        if "ask ryan about" in lower_input:
            query = lower_input.replace("ask ryan about", "").strip()
            if query:
                # Example of a plugin using the core AI's query_model function
                ai_response = self.ryan_ai.query_model(f"Tell me about {query}")
                return f"The AI says about {query}: {ai_response}"
            else:
                return "What would you like me to ask Ryan about?"

        # If the plugin doesn't handle the input, return None
        return None

# --- How to create a new plugin ---
# 1. Create a new file in the 'plugins' directory (e.g., 'image_search.py').
# 2. Define a class in that file (e.g., 'ImageSearch').
# 3. Add an __init__ method that accepts the ryan_ai_instance.
# 4. Add a handle_command(self, user_input) method.
# 5. Inside handle_command, check if the user_input is relevant to your plugin.
# 6. If it is, perform your plugin's task and return a response string.
# 7. If it's not, return None.
# 8. Ensure your class name is the capitalized version of your file name (e.g., ImageSearch for image_search.py).
