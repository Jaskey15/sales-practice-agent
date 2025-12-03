"""
Sales Coach agent that analyzes call transcripts and provides feedback.
Uses OpenAI API to evaluate sales performance and provide structured coaching.
"""
from openai import OpenAI
from typing import Dict, List
from pathlib import Path


class SalesCoach:
    """Sales coach that analyzes transcripts and provides structured feedback."""

    def __init__(self, api_key: str, model: str = "gpt-5.1-chat-latest"):
        """
        Initialize Sales Coach with OpenAI API.

        Args:
            api_key: OpenAI API key
            model: OpenAI chat model to use
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.system_prompt = self._load_coach_prompt()

    def _load_coach_prompt(self) -> str:
        """Load coach system prompt from file."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "coach_system.txt"
        with open(prompt_path, "r") as f:
            return f.read()

    def _format_transcript_for_analysis(self, conversation: List[Dict[str, str]]) -> str:
        """
        Format conversation history into readable transcript.

        Args:
            conversation: List of message dictionaries with 'role' and 'content'

        Returns:
            Formatted transcript string
        """
        transcript_lines = []

        for i, message in enumerate(conversation):
            role = message.get("role", "unknown")
            content = message.get("content", "")

            # Format based on role
            if role == "assistant":
                speaker = "PROSPECT (Sarah)"
            elif role == "user":
                speaker = "SALESPERSON"
            else:
                speaker = role.upper()

            transcript_lines.append(f"{speaker}: {content}")

        return "\n\n".join(transcript_lines)

    def analyze_call(
        self,
        conversation: List[Dict[str, str]],
        call_metadata: Dict = None
    ) -> Dict[str, any]:
        """
        Analyze a sales call and provide structured feedback.

        Args:
            conversation: List of message dictionaries from the call
            call_metadata: Optional metadata about the call

        Returns:
            Dictionary containing:
                - overall_score: Overall performance score (0-10)
                - detailed_scores: Dict of category scores
                - feedback: Full structured feedback text
                - top_strengths: List of strengths
                - areas_for_improvement: List of improvements
        """
        # Format the transcript
        transcript = self._format_transcript_for_analysis(conversation)

        # Create analysis prompt
        analysis_prompt = f"""Analyze this sales call transcript and provide detailed coaching feedback.

TRANSCRIPT:
{transcript}

Provide your analysis following the structured format defined in your system prompt."""

        # Call OpenAI chat completions API for analysis
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=4000,  # Longer response for detailed analysis
            temperature=0.3,  # Lower temperature for more consistent analysis
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": analysis_prompt}
            ]
        )

        # Extract feedback
        feedback_text = response.choices[0].message.content

        # Parse scores from feedback (basic extraction)
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
        """
        Extract numerical scores from feedback text.

        Args:
            feedback_text: Full feedback text with scores

        Returns:
            Dictionary of extracted scores
        """
        import re

        scores = {}

        # Extract overall score
        overall_match = re.search(r'OVERALL SCORE:\s*(\d+(?:\.\d+)?)/10', feedback_text)
        if overall_match:
            scores['overall'] = float(overall_match.group(1))

        # Extract detailed scores
        score_patterns = {
            'discovery': r'Discovery & Qualification:\*\*\s*(\d+(?:\.\d+)?)/10',
            'objection_handling': r'Objection Handling:\*\*\s*(\d+(?:\.\d+)?)/10',
            'value_articulation': r'Value Articulation:\*\*\s*(\d+(?:\.\d+)?)/10',
            'relationship_building': r'Relationship Building:\*\*\s*(\d+(?:\.\d+)?)/10',
            'call_control': r'Call Control & Structure:\*\*\s*(\d+(?:\.\d+)?)/10',
            'closing': r'Closing & Next Steps:\*\*\s*(\d+(?:\.\d+)?)/10',
        }

        for key, pattern in score_patterns.items():
            match = re.search(pattern, feedback_text)
            if match:
                scores[key] = float(match.group(1))

        return scores

    def quick_summary(
        self,
        conversation: List[Dict[str, str]]
    ) -> str:
        """
        Generate a quick 2-3 sentence summary of the call.

        Args:
            conversation: List of message dictionaries from the call

        Returns:
            Brief summary string
        """
        transcript = self._format_transcript_for_analysis(conversation)

        summary_prompt = f"""Provide a brief 2-3 sentence summary of this sales call. What happened and what was the outcome?

TRANSCRIPT:
{transcript}"""

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=200,
            temperature=0.5,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": summary_prompt}
            ]
        )

        return response.choices[0].message.content
