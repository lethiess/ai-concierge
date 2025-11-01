"""Call state management for tracking reservation calls."""

import logging
import re
import uuid
from datetime import datetime
from typing import ClassVar

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CallState(BaseModel):
    """State for an active or completed reservation call."""

    call_id: str = Field(description="Unique call identifier")
    call_sid: str | None = Field(None, description="Twilio call SID")
    status: str = Field(
        default="initiated",
        description="Call status: initiated, ringing, in_progress, completed, failed",
    )
    reservation_details: dict = Field(description="Reservation information")
    transcript: list[str] = Field(
        default_factory=list, description="Conversation transcript"
    )
    confirmation_number: str | None = Field(
        None, description="Extracted confirmation number"
    )
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: datetime | None = Field(None, description="Call end time")
    error_message: str | None = Field(None, description="Error message if failed")


class CallManager:
    """Manages state for active and completed reservation calls.

    This is a singleton that stores call state in memory.
    For production, consider using Redis or a database.
    """

    _instance: ClassVar["CallManager | None"] = None
    _active_calls: ClassVar[dict[str, CallState]] = {}

    def __new__(cls) -> "CallManager":
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def generate_call_id() -> str:
        """Generate a unique call identifier.

        Returns:
            UUID-based call ID
        """
        return str(uuid.uuid4())

    def create_call(
        self, reservation_details: dict, call_id: str | None = None
    ) -> CallState:
        """Register a new call.

        Args:
            reservation_details: Reservation information
            call_id: Optional call ID (generated if not provided)

        Returns:
            CallState object
        """
        if call_id is None:
            call_id = self.generate_call_id()

        call_state = CallState(
            call_id=call_id,
            reservation_details=reservation_details,
            status="initiated",
        )

        self._active_calls[call_id] = call_state
        logger.info(f"Created call {call_id}")

        return call_state

    def get_call(self, call_id: str) -> CallState | None:
        """Get call state by ID.

        Args:
            call_id: Call identifier

        Returns:
            CallState or None if not found
        """
        return self._active_calls.get(call_id)

    def update_status(self, call_id: str, status: str) -> None:
        """Update call status.

        Args:
            call_id: Call identifier
            status: New status (initiated, ringing, in_progress, completed, failed)
        """
        call_state = self._active_calls.get(call_id)
        if call_state:
            call_state.status = status
            logger.info(f"Call {call_id} status updated to {status}")

            if status in ("completed", "failed"):
                call_state.end_time = datetime.now()
        else:
            logger.warning(f"Attempted to update non-existent call {call_id}")

    def set_call_sid(self, call_id: str, call_sid: str) -> None:
        """Set Twilio call SID.

        Args:
            call_id: Call identifier
            call_sid: Twilio call SID
        """
        call_state = self._active_calls.get(call_id)
        if call_state:
            call_state.call_sid = call_sid
            logger.info(f"Call {call_id} linked to Twilio SID {call_sid}")

    def append_transcript(self, call_id: str, text: str) -> None:
        """Add to conversation transcript.

        Args:
            call_id: Call identifier
            text: Transcript text to append
        """
        call_state = self._active_calls.get(call_id)
        if call_state:
            call_state.transcript.append(text)
            logger.debug(f"Call {call_id} transcript: {text}")

            # Try to extract confirmation number after each update
            if not call_state.confirmation_number:
                confirmation = self.extract_confirmation(call_id)
                if confirmation:
                    call_state.confirmation_number = confirmation
                    logger.info(f"Call {call_id} confirmation number: {confirmation}")

    def set_error(self, call_id: str, error_message: str) -> None:
        """Set error message and mark call as failed.

        Args:
            call_id: Call identifier
            error_message: Error description
        """
        call_state = self._active_calls.get(call_id)
        if call_state:
            call_state.error_message = error_message
            call_state.status = "failed"
            call_state.end_time = datetime.now()
            logger.error(f"Call {call_id} failed: {error_message}")

    def extract_confirmation(self, call_id: str) -> str | None:
        """Parse transcript for confirmation number.

        Looks for common patterns like:
        - "confirmation number ABC123"
        - "your reservation is ABC123"
        - "reference XYZ456"

        Args:
            call_id: Call identifier

        Returns:
            Extracted confirmation number or None
        """
        call_state = self._active_calls.get(call_id)
        if not call_state or not call_state.transcript:
            return None

        # Join all transcript lines
        full_transcript = " ".join(call_state.transcript).lower()

        # Pattern 1: "confirmation number is ABC123"
        pattern1 = r"confirmation\s+(?:number|code|#)?\s*(?:is|:)?\s*([A-Z0-9]{4,})"
        match = re.search(pattern1, full_transcript, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        # Pattern 2: "your reservation is ABC123"
        pattern2 = r"reservation\s+(?:number|code|#)?\s*(?:is|:)?\s*([A-Z0-9]{4,})"
        match = re.search(pattern2, full_transcript, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        # Pattern 3: "reference number XYZ456"
        pattern3 = r"reference\s+(?:number|code|#)?\s*(?:is|:)?\s*([A-Z0-9]{4,})"
        match = re.search(pattern3, full_transcript, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        # Pattern 4: Any standalone alphanumeric code (6+ chars)
        pattern4 = r"\b([A-Z]{2,}[0-9]{4,}|[0-9]{4,}[A-Z]{2,})\b"
        match = re.search(pattern4, full_transcript, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        return None

    def get_all_calls(self) -> list[CallState]:
        """Get all active calls.

        Returns:
            List of CallState objects
        """
        return list(self._active_calls.values())

    def cleanup_old_calls(self, max_age_minutes: int = 60) -> int:
        """Remove completed calls older than max_age_minutes.

        Args:
            max_age_minutes: Maximum age in minutes

        Returns:
            Number of calls removed
        """
        now = datetime.now()
        to_remove = []

        for call_id, call_state in self._active_calls.items():
            if call_state.status in ("completed", "failed") and call_state.end_time:
                age_minutes = (now - call_state.end_time).total_seconds() / 60
                if age_minutes > max_age_minutes:
                    to_remove.append(call_id)

        for call_id in to_remove:
            del self._active_calls[call_id]
            logger.info(f"Cleaned up old call {call_id}")

        return len(to_remove)


# Global singleton instance
_call_manager: CallManager | None = None


def get_call_manager() -> CallManager:
    """Get the global CallManager instance.

    Returns:
        CallManager singleton
    """
    global _call_manager
    if _call_manager is None:
        _call_manager = CallManager()
    return _call_manager
