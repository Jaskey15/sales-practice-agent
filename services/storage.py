"""
Simple JSON-based storage for call transcripts.
Can be upgraded to SQLite or PostgreSQL later.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class TranscriptStorage:
    """Manages storage of call transcripts as JSON files."""

    def __init__(self, storage_dir: str = "data/transcripts"):
        """
        Initialize transcript storage.

        Args:
            storage_dir: Directory to store transcript files
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def save_transcript(
        self,
        call_sid: str,
        conversation_history: List[Dict[str, str]],
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Save a call transcript to a JSON file.

        Args:
            call_sid: Twilio call SID (unique identifier)
            conversation_history: List of message dictionaries
            metadata: Optional metadata about the call

        Returns:
            Path to the saved transcript file
        """
        timestamp = datetime.now().isoformat()

        transcript_data = {
            "call_sid": call_sid,
            "timestamp": timestamp,
            "metadata": metadata or {},
            "conversation": conversation_history
        }

        # Create filename: YYYYMMDD_HHMMSS_callsid.json
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{call_sid}.json"
        filepath = self.storage_dir / filename

        with open(filepath, "w") as f:
            json.dump(transcript_data, f, indent=2)

        return str(filepath)

    def load_transcript(self, call_sid: str) -> Optional[Dict]:
        """
        Load a transcript by call SID.

        Args:
            call_sid: Twilio call SID

        Returns:
            Transcript data dictionary or None if not found
        """
        # Find file matching the call_sid
        for filepath in self.storage_dir.glob(f"*_{call_sid}.json"):
            with open(filepath, "r") as f:
                return json.load(f)
        return None

    def list_transcripts(self, limit: int = 10) -> List[Dict]:
        """
        List recent transcripts.

        Args:
            limit: Maximum number of transcripts to return

        Returns:
            List of transcript metadata (without full conversation)
        """
        transcripts = []

        # Get all transcript files, sorted by modification time (newest first)
        files = sorted(
            self.storage_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        for filepath in files[:limit]:
            with open(filepath, "r") as f:
                data = json.load(f)
                # Return metadata only, not full conversation
                transcripts.append({
                    "call_sid": data["call_sid"],
                    "timestamp": data["timestamp"],
                    "metadata": data.get("metadata", {}),
                    "message_count": len(data.get("conversation", []))
                })

        return transcripts

    def get_transcript_stats(self, call_sid: str) -> Optional[Dict]:
        """
        Get statistics about a transcript.

        Args:
            call_sid: Twilio call SID

        Returns:
            Dictionary with transcript statistics
        """
        transcript = self.load_transcript(call_sid)
        if not transcript:
            return None

        conversation = transcript.get("conversation", [])

        user_messages = [msg for msg in conversation if msg["role"] == "user"]
        assistant_messages = [msg for msg in conversation if msg["role"] == "assistant"]

        return {
            "call_sid": call_sid,
            "timestamp": transcript["timestamp"],
            "total_messages": len(conversation),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "duration_estimate": len(conversation) * 15  # Rough estimate: 15s per exchange
        }
