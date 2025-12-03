"""
Sarah persona agent that responds to sales pitches.
Uses OpenAI API to maintain conversation as Sarah Martinez, Operations Manager.
"""
import logging

from openai import OpenAI  # type: ignore[import]
from typing import List, Dict
from pathlib import Path


logger = logging.getLogger(__name__)


class SarahPersona:
    """Sarah Martinez persona for sales training."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        """
        Initialize Sarah persona with OpenAI API.

        Args:
            api_key: OpenAI API key
            model: OpenAI chat model to use
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.system_prompt = self._load_persona_prompt()
        self.conversation_history: List[Dict[str, str]] = []

    def _load_persona_prompt(self) -> str:
        """Load Sarah's persona prompt from file."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "sarah_persona.txt"
        with open(prompt_path, "r") as f:
            return f.read()

    def respond(self, user_message: str) -> str:
        """
        Generate Sarah’s response to the user’s message.

        Args:
            user_message: The salesperson’s message

        Returns:
            Sarah’s response as text
        """

        # Add incoming message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Build messages array for the chat completion call
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.conversation_history)

        # Call Chat Completions API (correct Python usage — NOT responses API)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_completion_tokens=150
        )

        choice = response.choices[0]
        logger.debug(
            "OpenAI respond finish_reason=%s refusal=%s content=%r usage=%s",
            choice.finish_reason,
            choice.message.refusal,
            choice.message.content,
            response.usage,
        )

        assistant_message = choice.message.content

        # Add assistant response to conversation history
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })

        return assistant_message

    def get_conversation_history(self) -> List[Dict[str, str]]:
        """Get the full conversation history."""
        return self.conversation_history.copy()

    def reset_conversation(self):
        """Clear conversation history for a new call."""
        self.conversation_history = []

    def get_greeting(self) -> str:
        """
        Generate Sarah’s initial greeting for the phone call.

        Returns:
            Greeting string
        """

        greeting_prompt = (
            "You've just answered your office phone. "
            "Greet the caller professionally but briefly, like a real business call."
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": greeting_prompt},
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_completion_tokens=50
        )

        choice = response.choices[0]
        logger.debug(
            "OpenAI greeting finish_reason=%s refusal=%s content=%r usage=%s",
            choice.finish_reason,
            choice.message.refusal,
            choice.message.content,
            response.usage,
        )

        greeting = choice.message.content

        # Add greeting to conversation history
        self.conversation_history.append({
            "role": "assistant",
            "content": greeting
        })

        return greeting