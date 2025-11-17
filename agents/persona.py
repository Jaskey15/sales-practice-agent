"""
Sarah persona agent that responds to sales pitches.
Uses Claude API to maintain conversation as Sarah Chen, VP of Operations.
"""
import anthropic
import requests
from typing import List, Dict, Optional
from pathlib import Path


class SarahPersona:
    """Sarah Chen - VP of Operations persona for sales training."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022", use_openrouter: bool = False):
        """
        Initialize Sarah persona with Claude API.

        Args:
            api_key: Anthropic API key or OpenRouter API key (depending on use_openrouter)
            model: Claude model to use
        """
        self.api_key = api_key
        self.use_openrouter = use_openrouter
        self.model = model
        # If using OpenRouter, we'll call the OpenRouter HTTP API directly.
        if self.use_openrouter:
            self.client = None
        else:
            self.client = anthropic.Anthropic(api_key=api_key)
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

        # Call API (OpenRouter or Anthropic)
        if self.use_openrouter:
            messages = [{"role": "system", "content": self.system_prompt}] + self.conversation_history
            assistant_message = self._call_openrouter_chat(messages=messages, model=self.model, max_tokens=300, temperature=0.7)
        else:
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

        if self.use_openrouter:
            messages = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": greeting_prompt}]
            greeting = self._call_openrouter_chat(messages=messages, model=self.model, max_tokens=100, temperature=0.7)
        else:
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

    def _call_openrouter_chat(self, messages: List[Dict[str, str]], model: str, max_tokens: int = 300, temperature: float = 0.7) -> str:
        """
        Call OpenRouter chat completions endpoint and return assistant text.
        This uses the OpenRouter API which is compatible with OpenAI-style chat completions.
        """
        if not self.api_key:
            raise ValueError("OpenRouter API key not set")

        url = "https://api.openrouter.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # Try common response shapes (OpenAI-compatible)
        try:
            return data["choices"][0]["message"]["content"]
        except Exception:
            # Fallback to other possible shapes
            # e.g., some OpenRouter responses may include 'output' or nested content
            if "output" in data:
                try:
                    # output can be a list of objects with 'content' arrays
                    return data["output"][0]["content"][0]["text"]
                except Exception:
                    pass
            # If nothing matched, raise for visibility
            raise ValueError(f"Unexpected OpenRouter response shape: {data}")
