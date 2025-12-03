"""
Simple JSON-based storage for call transcripts.
Can be upgraded to SQLite or PostgreSQL later.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class TranscriptStorage:
    """Manages storage of call transcripts within per-call directories."""

    TRANSCRIPT_FILENAME = "transcript.json"
    FEEDBACK_FILENAME = "feedback.json"

    def __init__(self, storage_dir: str = "data/calls"):
        """
        Initialize transcript storage.

        Args:
            storage_dir: Base directory to store call artifacts
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _slugify(value: str) -> str:
        """Basic slug implementation to keep directory names readable."""
        value = value.lower()
        value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
        return value or "call"

    def _find_call_dir(self, call_sid: str) -> Optional[Path]:
        """Locate existing directory for a call SID."""
        matches = sorted(self.storage_dir.glob(f"*_{call_sid}"), reverse=True)
        return matches[0] if matches else None

    def _build_dir_name(
        self,
        timestamp: datetime,
        call_sid: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Compose a directory name using timestamp, friendly label, and SID."""
        parts = [timestamp.strftime("%Y%m%d_%H%M%S")]

        if metadata:
            friendly_label = metadata.get("friendly_label") or metadata.get("caller_label")
            if friendly_label:
                parts.append(self._slugify(str(friendly_label)))
            else:
                # Fall back to caller number if available
                caller_number = metadata.get("from_number")
                if caller_number:
                    parts.append(self._slugify(str(caller_number)))

        parts.append(call_sid)
        return "_".join(filter(None, parts))

    def _get_call_dir(
        self,
        call_sid: str,
        *,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        create: bool = False,
    ) -> Optional[Path]:
        """
        Retrieve or create the directory for a call.

        Args:
            call_sid: Twilio call SID
            timestamp: Timestamp used when creating new directories
            metadata: Metadata used to build a friendly directory name
            create: Whether to create the directory if it doesn't exist
        """
        existing = self._find_call_dir(call_sid)
        if existing or not create:
            return existing

        timestamp = timestamp or datetime.now()
        dir_name = self._build_dir_name(timestamp, call_sid, metadata)
        call_dir = self.storage_dir / dir_name
        call_dir.mkdir(parents=True, exist_ok=True)
        return call_dir

    def _write_json(self, filepath: Path, payload: Dict[str, Any]) -> None:
        """Persist JSON payload to disk."""
        with open(filepath, "w") as f:
            json.dump(payload, f, indent=2)

    def _read_json(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Safely read JSON data if the file exists."""
        if not filepath.exists():
            return None
        with open(filepath, "r") as f:
            return json.load(f)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def save_transcript(
        self,
        call_sid: str,
        conversation_history: List[Dict[str, str]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Save a call transcript to the call's directory.

        Args:
            call_sid: Twilio call SID (unique identifier)
            conversation_history: List of message dictionaries
            metadata: Optional metadata about the call

        Returns:
            Path to the saved transcript file
        """
        timestamp = datetime.now()
        metadata = dict(metadata or {})
        metadata.setdefault("friendly_label", metadata.get("caller_label"))
        metadata.setdefault("created_at", timestamp.isoformat())

        call_dir = self._get_call_dir(
            call_sid,
            timestamp=timestamp,
            metadata=metadata,
            create=True,
        )
        if not call_dir:
            raise RuntimeError(f"Unable to allocate directory for call {call_sid}")

        transcript_path = call_dir / self.TRANSCRIPT_FILENAME
        transcript_data = {
            "call_sid": call_sid,
            "timestamp": timestamp.isoformat(),
            "metadata": metadata,
            "conversation": conversation_history,
        }
        self._write_json(transcript_path, transcript_data)

        return str(transcript_path)

    def load_transcript(self, call_sid: str) -> Optional[Dict[str, Any]]:
        """
        Load a transcript by call SID.

        Returns:
            Transcript data dictionary or None if not found
        """
        call_dir = self._find_call_dir(call_sid)
        if not call_dir:
            return None
        return self._read_json(call_dir / self.TRANSCRIPT_FILENAME)

    def list_transcripts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List recent transcripts (metadata only).

        Returns:
            List of transcript metadata dictionaries
        """
        transcripts: List[Dict[str, Any]] = []

        call_dirs = sorted(
            (p for p in self.storage_dir.iterdir() if p.is_dir()),
            key=lambda p: p.name,
            reverse=True,
        )

        for call_dir in call_dirs[:limit]:
            transcript_path = call_dir / self.TRANSCRIPT_FILENAME
            data = self._read_json(transcript_path)
            if not data:
                continue

            metadata = data.get("metadata", {})
            transcripts.append({
                "call_sid": data.get("call_sid"),
                "timestamp": data.get("timestamp"),
                "metadata": metadata,
                "message_count": len(data.get("conversation", [])),
                "has_feedback": (call_dir / self.FEEDBACK_FILENAME).exists(),
                "directory": str(call_dir),
            })

        return transcripts

    def get_transcript_stats(self, call_sid: str) -> Optional[Dict[str, Any]]:
        """Compute simple statistics for a transcript."""
        transcript = self.load_transcript(call_sid)
        if not transcript:
            return None

        conversation = transcript.get("conversation", [])
        user_messages = [msg for msg in conversation if msg.get("role") == "user"]
        assistant_messages = [msg for msg in conversation if msg.get("role") == "assistant"]

        return {
            "call_sid": call_sid,
            "timestamp": transcript.get("timestamp"),
            "friendly_label": transcript.get("metadata", {}).get("friendly_label"),
            "total_messages": len(conversation),
            "user_messages": len(user_messages),
            "assistant_messages": len(assistant_messages),
            "duration_estimate": len(conversation) * 15,  # Rough estimate: 15s per exchange
        }

    def save_feedback(self, call_sid: str, feedback_data: Dict[str, Any]) -> str:
        """
        Save coaching feedback for a call.

        Args:
            call_sid: Twilio call SID
            feedback_data: Dictionary containing feedback analysis

        Returns:
            Path to the saved feedback file
        """
        timestamp = datetime.now()
        call_dir = self._find_call_dir(call_sid)
        if not call_dir:
            # Create a directory if one does not yet exist (edge case).
            call_dir = self._get_call_dir(
                call_sid,
                timestamp=timestamp,
                metadata=feedback_data.get("metadata"),
                create=True,
            )
        if not call_dir:
            raise RuntimeError(f"Unable to locate directory for call {call_sid}")

        feedback_path = call_dir / self.FEEDBACK_FILENAME
        feedback_record = {
            "call_sid": call_sid,
            "timestamp": timestamp.isoformat(),
            "feedback": feedback_data,
        }
        self._write_json(feedback_path, feedback_record)
        return str(feedback_path)

    def load_feedback(self, call_sid: str) -> Optional[Dict[str, Any]]:
        """Load coaching feedback for a call."""
        call_dir = self._find_call_dir(call_sid)
        if not call_dir:
            return None
        return self._read_json(call_dir / self.FEEDBACK_FILENAME)
