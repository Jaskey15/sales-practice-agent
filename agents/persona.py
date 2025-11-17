"""
Sarah persona agent that responds to sales pitches.
Uses Claude API to maintain conversation as Sarah Chen, VP of Operations.
"""
import anthropic
from typing import List, Dict
from pathlib import Path


class SarahPersona:
    """Sarah Chen - VP of Operations persona for sales training."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize Sarah persona with Claude API.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
        """
        self.client = anthropic.Anthropic(api_key=api_key)
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
        Generate Sarah's response to the user's message.

        Args:
            user_message: The salesperson's message

        Returns:
            Sarah's response as text
        """
        # Add user message to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Call Claude API
        response = self.client.messages.create(
            model=self.model,
            max_tokens=300,  # Keep responses concise (2-4 sentences)
            temperature=0.7,  # Some variability for natural conversation
            system=self.system_prompt,
            messages=self.conversation_history
        )

        # Extract response text
        assistant_message = response.content[0].text

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
        Generate Sarah's initial greeting when answering the phone.

        Returns:
            Sarah's greeting message
        """
        greeting_prompt = "You've just answered your office phone. Greet the caller professionally but briefly, as you would in a real business call."

        response = self.client.messages.create(
            model=self.model,
            max_tokens=100,
            temperature=0.7,
            system=self.system_prompt,
            messages=[{"role": "user", "content": greeting_prompt}]
        )

        greeting = response.content[0].text

        # Add greeting to conversation history
        self.conversation_history.append({
            "role": "assistant",
            "content": greeting
        })

        return greeting
