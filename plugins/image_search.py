# plugins/image_search.py

import requests
import os
import json # Import json to potentially format response for frontend

# Define the class for the Image Search plugin
class ImageSearch:
    def __init__(self, ryan_ai_instance):
        """
        Initializes the Image Search plugin.
        Args:
            ryan_ai_instance: The main RyanAI object (can be used for accessing
                              core AI functionalities if needed, though not
                              strictly required for this basic image search).
        """
        self.ryan_ai = ryan_ai_instance # Store the AI instance
        # Retrieve API keys from environment variables (already loaded in ryan_ai.py)
        self.search_api_key = os.getenv("SEARCH_API_KEY")
        self.search_engine_id = os.getenv("SEARCH_ENGINE_ID")

        # Basic check to ensure API keys are available
        if not self.search_api_key or not self.search_engine_id:
            print("Warning: Google Custom Search API keys (SEARCH_API_KEY, SEARCH_ENGINE_ID) not found. Image search plugin will not function.")
            self.is_functional = False # Flag to indicate if the plugin can work
        else:
            self.is_functional = True
            print("ImageSearch plugin initialized and functional.") # Added print for debugging


    def handle_command(self, user_input):
        """
        Processes the user input to detect and handle image search requests.

        Args:
            user_input: The raw string input from the user.

        Returns:
            A string response if the plugin handled the command, otherwise None.
            For image results, this will be a formatted string.
        """
        if not self.is_functional:
            # If the plugin is not functional due to missing keys, inform the user
            return "I'm sorry, the image search feature is not configured properly."

        lower_input = user_input.lower()

        # --- Intent Detection for Image Search ---
        # Look for phrases indicating an image search request
        # We'll use a few common phrases. You can add more as needed.
        image_search_phrases = [
            "search for images of",
            "find pictures of",
            "show me images of",
            "show me pictures of",
            "image search for"
        ]

        query = None
        for phrase in image_search_phrases:
            if phrase in lower_input:
                # Extract the part of the input after the phrase as the search query
                query = lower_input.split(phrase, 1)[1].strip()
                break # Stop checking phrases once one is found

        # If a query was successfully extracted
        if query:
            print(f"Detected image search command. Searching for: '{query}'") # Added print
            # Perform the image search
            image_results = self.perform_image_search(query)

            # Format the results into a response string
            if image_results is None:
                # Handle API error case
                return "I encountered an error while trying to perform the image search."
            elif image_results:
                # If results were found, format them
                response = f"Here are some images of {query}:\n"
                # You can adjust the formatting based on how you want it displayed in the chat
                # For a simple text-based chat, listing URLs is common.
                # For a web UI, you might return a structured object for the frontend to render.
                for img in image_results:
                    # Add a simple markdown link format for potential web UI rendering
                    response += f"- [{img.get('title', 'Image')}]({img.get('url', '#')})\n"

                # --- Alternative: Return a structured object for frontend ---
                # If your frontend (script.js) is capable of parsing JSON responses
                # with specific types, you could return a dictionary like this:
                # return {
                #     "type": "image_results",
                #     "query": query,
                #     "results": image_results,
                #     "text_response": response # Include the text response as a fallback
                # }
                # This would require changes in script.js to handle the "image_results" type.
                # For now, we'll stick to returning a simple string as per the current ryan_ai structure.

                return response
            else:
                # If no results were found
                return f"Sorry, I couldn't find any images for '{query}'."
        else:
            # If none of the image search phrases were found in the input
            return None # Return None to indicate this plugin didn't handle the command


    def perform_image_search(self, query, num_results=5):
        """
        Searches for images using the Google Custom Search JSON API.

        Args:
            query: The search query string.
            num_results: The maximum number of results to return.

        Returns:
            A list of dictionaries containing image information (title, url, snippet)
            or an empty list if no results, or None if an API error occurred.
        """
        # Ensure API keys are available before making the request
        if not self.search_api_key or not self.search_engine_id:
            print("Error: search_images called but API keys are missing.") # Added print
            return None

        # Google Custom Search API endpoint
        search_url = "https://www.googleapis.com/customsearch/v1"

        params = {
            'q': query, # The search query
            'key': self.search_api_key, # Your API key
            'cx': self.search_engine_id, # Your Custom Search Engine ID
            'searchType': 'image', # Specify image search
            'num': num_results # Number of results to return (max 10 per request)
            # Add other parameters as needed, e.g., imgSize, imgType, etc.
            # See Google Custom Search JSON API documentation for more options.
        }

        try:
            # Make the GET request to the API
            response = requests.get(search_url, params=params)
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)

            search_results = response.json()

            images = []
            # Check if 'items' are present in the response
            if 'items' in search_results:
                for item in search_results['items']:
                    images.append({
                        'title': item.get('title'),
                        'url': item.get('link'), # The direct link to the image
                        'snippet': item.get('snippet', '') # Often a description or context
                    })
            # If 'items' is not in the response or is empty, it means no results were found.
            return images

        except requests.exceptions.RequestException as e:
            print(f"Error during Google Image Search API request: {e}") # Added print
            return None # Return None to indicate an error occurred
        except json.JSONDecodeError:
            print("Error decoding JSON response from Google Image Search API.") # Added print
            return None # Handle potential JSON decoding errors
        except Exception as e:
            print(f"An unexpected error occurred during image search: {e}") # Added print
            return None # Catch any other unexpected errors

# --- Note on API Keys ---
# Make sure your ryanEnv.env file contains:
# SEARCH_API_KEY=YOUR_GOOGLE_CLOUD_SEARCH_API_KEY
# SEARCH_ENGINE_ID=YOUR_GOOGLE_CUSTOM_SEARCH_ENGINE_ID
# And that you have enabled the Custom Search API in your Google Cloud Console
# and configured a Custom Search Engine for images.
