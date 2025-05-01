# plugins/joke_plugin.py

class JokePlugin:
    def __init__(self, ryan_ai_instance):
        """
        Initializes the Joke Plugin.

        Args:
            ryan_ai_instance: The main RyanAI object, used here to access
                              the query_model method for generating jokes.
        """
        self.ryan_ai = ryan_ai_instance
        print("JokePlugin initialized.") # Added print for debugging

    def handle_command(self, user_input):
        """
        Processes the user input to detect and handle requests for jokes.

        Args:
            user_input: The raw string input from the user.

        Returns:
            A string containing a joke if a joke request was detected,
            otherwise None.
        """
        lower_input = user_input.lower()

        # --- Intent Detection for Joke Request ---
        # Look for phrases indicating the user wants a joke
        joke_phrases = [
            "tell me a joke",
            "make me laugh",
            "got any jokes",
            "say something funny",
            "joke please"
        ]

        # Check if any of the joke phrases are in the user input
        if any(phrase in lower_input for phrase in joke_phrases):
            print("Detected joke request.") # Added print

            # Use the core AI's language model to generate a joke
            # We'll prompt the model to tell a short, funny joke.
            joke_prompt = "Tell me a short, funny joke."

            try:
                # Call the core AI's query_model method
                # Using a slightly higher temperature might result in more creative/varied jokes
                joke_response = self.ryan_ai.query_model(joke_prompt, temperature=0.8, max_new_tokens=100)

                if joke_response:
                    # Return the generated joke
                    return joke_response
                else:
                    # Fallback if the model didn't return a joke
                    return "Hmm, I can't think of a joke right now. My humor circuits might be offline!"

            except Exception as e:
                # Handle potential errors when calling the query_model
                print(f"Error generating joke with language model: {e}")
                return "Oops, something went wrong while trying to come up with a joke."

        # If none of the joke phrases were found, return None
        return None

# --- How to add this plugin ---
# 1. Save the code above as 'joke_plugin.py' inside your 'plugins' directory.
# 2. Make sure your ryan_ai.py file has the updated plugin loading logic
#    (from the 'ryan_ai_plugin_system_v2' immersive).
# 3. Run your Ryan AI application. The plugin should be automatically loaded.
# 4. In the chat, type a phrase like "tell me a joke" or "got any jokes?".
