"""
Twilio handler for generating TwiML responses.
Handles voice call flow, speech recognition, and text-to-speech.
"""
from twilio.twiml.voice_response import VoiceResponse, Gather


class TwilioVoiceHandler:
    """Handles Twilio voice interactions and TwiML generation."""

    def __init__(self, base_url: str):
        """
        Initialize Twilio handler.

        Args:
            base_url: Base URL for webhook callbacks (e.g., ngrok URL)
        """
        self.base_url = base_url.rstrip("/")

    def create_greeting_response(self, greeting_text: str) -> str:
        """
        Create initial greeting TwiML response.

        Args:
            greeting_text: Sarah's greeting message

        Returns:
            TwiML XML string
        """
        response = VoiceResponse()

        # Sarah says her greeting - using neural voice for more natural sound
        response.say(
            greeting_text,
            voice="Polly.Ruth-Neural",  # High-quality neural voice (more natural)
            language="en-US"
        )

        # Gather user's speech response
        gather = Gather(
            input="speech",
            action=f"{self.base_url}/voice/respond",
            method="POST",
            speech_timeout="auto",  # Auto-detect when user stops speaking
            speech_model="phone_call",  # Optimized for phone calls
            language="en-US"
        )

        response.append(gather)

        # If no input, prompt again
        response.say(
            "I didn't catch that. Are you still there?",
            voice="Polly.Ruth-Neural",
            language="en-US"
        )

        return str(response)

    def create_conversation_response(
        self,
        sarah_response: str,
        is_final: bool = False
    ) -> str:
        """
        Create conversation turn TwiML response.

        Args:
            sarah_response: Sarah's response text
            is_final: Whether this is the final response (end call)

        Returns:
            TwiML XML string
        """
        response = VoiceResponse()

        # Sarah speaks her response
        response.say(
            sarah_response,
            voice="Polly.Ruth-Neural",
            language="en-US"
        )

        if is_final:
            # End the call
            response.say(
                "Thanks for your time. Goodbye!",
                voice="Polly.Ruth-Neural",
                language="en-US"
            )
            response.hangup()
        else:
            # Continue conversation - gather next input
            gather = Gather(
                input="speech",
                action=f"{self.base_url}/voice/respond",
                method="POST",
                speech_timeout="auto",
                speech_model="phone_call",
                language="en-US"
            )

            response.append(gather)

            # If no input after waiting
            response.say(
                "I didn't hear anything. Are you still there?",
                voice="Polly.Ruth-Neural",
                language="en-US"
            )

            # Give one more chance to respond
            final_gather = Gather(
                input="speech",
                action=f"{self.base_url}/voice/respond",
                method="POST",
                speech_timeout="auto",
                speech_model="phone_call",
                language="en-US",
                timeout=5
            )

            response.append(final_gather)

            # If still no input, end call
            response.say(
                "I'll let you go. Feel free to call back anytime. Goodbye!",
                voice="Polly.Ruth-Neural",
                language="en-US"
            )
            response.hangup()

        return str(response)

    def create_error_response(self, error_message: str = None) -> str:
        """
        Create error handling TwiML response.

        Args:
            error_message: Optional custom error message

        Returns:
            TwiML XML string
        """
        response = VoiceResponse()

        message = error_message or "I'm sorry, I'm having technical difficulties. Please try calling back later."

        response.say(
            message,
            voice="Polly.Ruth-Neural",
            language="en-US"
        )

        response.hangup()

        return str(response)

    def should_end_call(self, user_message: str) -> bool:
        """
        Determine if the call should end based on user's message.

        Args:
            user_message: User's speech transcribed to text

        Returns:
            True if call should end, False otherwise
        """
        # Simple keyword detection for ending calls
        end_phrases = [
            "goodbye",
            "bye",
            "thank you for your time",
            "i'll let you go",
            "talk to you later",
            "have a good day",
            "i have to go",
            "gotta go"
        ]

        user_lower = user_message.lower().strip()

        return any(phrase in user_lower for phrase in end_phrases)
