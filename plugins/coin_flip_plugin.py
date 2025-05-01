# plugins/coin_flip_plugin.py

import random
import logging # Import logging

class CoinFlipPlugin:
    def __init__(self, ryan_ai_instance):
        """
        Initializes the Coin Flip Plugin.

        Args:
            ryan_ai_instance: The main RyanAI object.
        """
        self.ryan_ai = ryan_ai_instance
        logging.info("CoinFlipPlugin initialized.") # Added print for debugging

    def handle_command(self, user_input):
        """
        Processes the user input to detect and handle coin flip requests.

        Args:
            user_input: The raw string input from the user.

        Returns:
            A string with the coin flip result if a request was detected,
            otherwise None.
        """
        lower_input = user_input.lower()

        # --- Intent Detection for Coin Flip Request ---
        if "flip a coin" in lower_input or "coin flip" in lower_input:
            logging.info("Detected coin flip request.")
            # Simulate a coin flip
            result = random.choice(["Heads", "Tails"])
            return f"Okay, I'll flip a coin... It landed on **{result}**!" # Use markdown for emphasis

        # If none of the coin flip phrases were found, return None
        return None
