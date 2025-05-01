# plugins/time_plugin.py

import datetime
import logging # Import logging

class TimePlugin:
    def __init__(self, ryan_ai_instance):
        """
        Initializes the Time Plugin.

        Args:
            ryan_ai_instance: The main RyanAI object.
        """
        self.ryan_ai = ryan_ai_instance
        logging.info("TimePlugin initialized.") # Added print for debugging

    def handle_command(self, user_input):
        """
        Processes the user input to detect and handle requests for time or date.

        Args:
            user_input: The raw string input from the user.

        Returns:
            A string containing the current time/date if a request was detected,
            otherwise None.
        """
        lower_input = user_input.lower()

        # --- Intent Detection for Time/Date Request ---
        if "what time is it" in lower_input or "current time" in lower_input:
            logging.info("Detected time request.")
            # Get the current time
            now = datetime.datetime.now()
            # Format the time nicely
            current_time = now.strftime("%I:%M %p") # e.g., 03:30 PM
            return f"The current time is {current_time}."

        if "what is the date" in lower_input or "current date" in lower_input:
            logging.info("Detected date request.")
            # Get the current date
            today = datetime.date.today()
            # Format the date nicely
            current_date = today.strftime("%A, %B %d, %Y") # e.g., Friday, April 25, 2025
            return f"Today's date is {current_date}."

        # If none of the time/date phrases were found, return None
        return None
