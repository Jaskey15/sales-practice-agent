"""
Sales Coach agent that analyzes call transcripts and provides feedback.
Uses OpenAI API to evaluate sales performance and provide structured coaching.
"""
from openai import OpenAI
from typing import Dict, List, Optional
from pathlib import Path
import re


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class SalesCoach:
    """Sales coach that analyzes transcripts and provides structured feedback."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        *,
        http_referer: Optional[str] = None,
        x_title: Optional[str] = None,
    ):
        """
        Initialize Sales Coach with OpenRouter API.

        Args:
            api_key: OpenRouter API key
            model: OpenRouter chat model to use
            http_referer: Optional HTTP-Referer header for attribution
            x_title: Optional X-Title header for attribution
        """
        headers: Dict[str, str] = {}
        if http_referer:
            headers["HTTP-Referer"] = http_referer
        if x_title:
            headers["X-Title"] = x_title

        self._extra_headers = headers if headers else None

        client_kwargs = {
            "api_key": api_key,
            "base_url": OPENROUTER_BASE_URL,
        }
        if self._extra_headers:
            client_kwargs["default_headers"] = self._extra_headers

        self.client = OpenAI(**client_kwargs)
        self.model = model
        self.system_prompt = self._load_coach_prompt()

    def _load_coach_prompt(self) -> str:
        """Load coach system prompt from file."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "coach_system.txt"
        with open(prompt_path, "r") as f:
            return f.read()

    def _format_transcript_for_analysis(self, conversation: List[Dict[str, str]]) -> str:
        """Format conversation history into readable transcript."""
        transcript_lines = []

        for message in conversation:
            role = message.get("role", "unknown")
            content = message.get("content", "")

            if role == "assistant":
                speaker = "PROSPECT (Sarah)"
            elif role == "user":
                speaker = "SALESPERSON"
            else:
                speaker = role.upper()

            transcript_lines.append(f"{speaker}: {content}")

        return "\n\n".join(transcript_lines)

    def analyze_call(self, conversation: List[Dict[str, str]], call_metadata: Dict = None) -> Dict[str, any]:
        """Analyze a sales call and provide structured feedback."""
        transcript = self._format_transcript_for_analysis(conversation)

        analysis_prompt = f"""
Analyze this sales call transcript and provide detailed coaching feedback.

TRANSCRIPT:
{transcript}

Provide your analysis following the structured format defined in your system prompt.
"""

        # Chat Completions API (gpt-4o-mini compatible)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": analysis_prompt}
            ],
            max_completion_tokens=4000,
            extra_headers=self._extra_headers,
        )

        feedback_text = response.choices[0].message.content

        scores = self._extract_scores(feedback_text)

        return {
            "overall_score": scores.get("overall", 0),
            "detailed_scores": {
                "discovery": scores.get("discovery", 0),
                "objection_handling": scores.get("objection_handling", 0),
                "value_articulation": scores.get("value_articulation", 0),
                "relationship_building": scores.get("relationship_building", 0),
                "call_control": scores.get("call_control", 0),
                "closing": scores.get("closing", 0),
            },
            "feedback": feedback_text,
            "metadata": call_metadata or {}
        }

    def _extract_scores(self, feedback_text: str) -> Dict[str, float]:
        """Extract numerical scores from feedback text."""
        scores = {}

        # Extract overall score
        overall_match = re.search(r'OVERALL SCORE:\s*(\d+(?:\.\d+)?)/10', feedback_text)
        if overall_match:
            scores['overall'] = float(overall_match.group(1))

        # Extract detailed scores
        patterns = {
            'discovery': r'Discovery & Qualification:\*\*\s*(\d+(?:\.\d+)?)/10',
            'objection_handling': r'Objection Handling:\*\*\s*(\d+(?:\.\d+)?)/10',
            'value_articulation': r'Value Articulation:\*\*\s*(\d+(?:\.\d+)?)/10',
            'relationship_building': r'Relationship Building:\*\*\s*(\d+(?:\.\d+)?)/10',
            'call_control': r'Call Control & Structure:\*\*\s*(\d+(?:\.\d+)?)/10',
            'closing': r'Closing & Next Steps:\*\*\s*(\d+(?:\.\d+)?)/10',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, feedback_text)
            if match:
                scores[key] = float(match.group(1))

        return scores

    def quick_summary(self, conversation: List[Dict[str, str]]) -> str:
        """Generate a brief 2–3 sentence summary of the call."""
        transcript = self._format_transcript_for_analysis(conversation)

        summary_prompt = f"""
Provide a concise 2–3 sentence summary of this sales call.
What happened, and what was the outcome?

TRANSCRIPT:
{transcript}
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a summarization assistant."},
                {"role": "user", "content": summary_prompt},
            ],
            max_completion_tokens=200,
            extra_headers=self._extra_headers,
        )

        return response.choices[0].message.content