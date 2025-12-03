"""
Twilio handler for generating TwiML responses.
Handles voice call flow, speech recognition, and text-to-speech.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse
from xml.sax.saxutils import escape

from twilio.twiml.voice_response import VoiceResponse


@dataclass
class ConversationRelayConfig:
    """Configuration for Twilio ConversationRelay."""

    voice_id: str
    welcome_greeting: str
    tts_provider: str = "ElevenLabs"
    text_normalization: str | None = "on"
    language: str = "en-US"


class TwilioVoiceHandler:
    """Handles Twilio voice interactions and TwiML generation."""

    def __init__(self, base_url: str, voice_id: str):
        """
        Initialize Twilio handler.

        Args:
            base_url: Base URL for webhook callbacks (e.g., ngrok URL)
            voice_id: ElevenLabs voice identifier for ConversationRelay
        """
        self.base_url = base_url.rstrip("/")
        self.voice_id = voice_id.strip()

    def create_conversationrelay_response(
        self,
        config: ConversationRelayConfig,
        relay_path: str = "/voice/relay"
    ) -> str:
        """
        Create TwiML response that connects the caller to ConversationRelay.

        Args:
            config: ConversationRelay settings for this call.
            relay_path: Relative websocket path for ConversationRelay handler.

        Returns:
            TwiML XML string
        """
        ws_url = self._build_ws_url(relay_path)

        attributes = [
            f'url="{ws_url}"',
            f'ttsProvider="{self._escape_attr(config.tts_provider)}"',
            f'voice="{self._escape_attr(config.voice_id)}"',
            f'ttsLanguage="{self._escape_attr(config.language)}"',
            f'welcomeGreeting="{self._escape_attr(config.welcome_greeting)}"',
        ]

        if config.text_normalization:
            attributes.append(
                f'elevenlabsTextNormalization="{self._escape_attr(config.text_normalization)}"'
            )

        attributes_str = " ".join(attributes)

        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response>"
            "<Connect>"
            f"<ConversationRelay {attributes_str} />"
            "</Connect>"
            "</Response>"
        )

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
            voice="Google.en-US-Neural2-F",
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

    def _build_ws_url(self, relay_path: str) -> str:
        """Construct websocket URL for ConversationRelay."""
        relay_path = "/" + relay_path.lstrip("/")
        parsed = urlparse(self.base_url if "://" in self.base_url else f"https://{self.base_url}")

        scheme = "wss" if parsed.scheme == "https" else "ws"
        netloc = parsed.netloc or parsed.path
        base_path = parsed.path if parsed.netloc else ""

        full_path = "/".join(filter(None, [base_path.strip("/"), relay_path.strip("/")]))
        full_path = "/" + full_path if not full_path.startswith("/") else full_path

        return urlunparse((scheme, netloc, full_path, "", "", ""))

    @staticmethod
    def _escape_attr(value: str) -> str:
        """Escape attribute values for inclusion in TwiML."""
        return escape(value, {'"': "&quot;"})
