"""Call state management for tracking reservation calls."""

import logging
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

    async def update_status(self, call_id: str, status: str) -> None:
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

                # On completion, use LLM to analyze the transcript and extract confirmed details
                if status == "completed":
                    await self.analyze_and_update_confirmation(call_id)

                    if not call_state.confirmation_number:
                        logger.warning(
                            f"⚠ Call {call_id} completed without confirmation number. Transcript length: {len(call_state.transcript)}"
                        )
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

            # Note: Confirmation extraction now happens once at the end via LLM
            # when update_status("completed") is called

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

    async def analyze_and_update_confirmation(self, call_id: str) -> None:
        """Analyze the call transcript using LLM and update confirmed details.

        This uses the Transcript Analysis Agent to understand the conversation
        and extract the actual confirmed details.

        Args:
            call_id: Call identifier
        """
        call_state = self._active_calls.get(call_id)
        if not call_state or not call_state.transcript:
            logger.warning(f"No transcript found for call {call_id}")
            return

        logger.info(f"🤖 Analyzing transcript with LLM for call {call_id}")
        logger.info(
            f"   Transcript has {len(call_state.transcript)} lines, {len(' '.join(call_state.transcript))} chars"
        )

        try:
            from concierge.agents.transcript_agent import get_transcript_agent

            agent = get_transcript_agent()
            confirmed_details = await agent.analyze_transcript(
                transcript_lines=call_state.transcript,
                original_details=call_state.reservation_details,
            )

            # Update call state with confirmed details
            if confirmed_details.confirmation_number:
                call_state.confirmation_number = confirmed_details.confirmation_number
                logger.info(
                    f"✓ LLM extracted confirmation number: {confirmed_details.confirmation_number}"
                )
            else:
                logger.warning("⚠ LLM did not extract a confirmation number")

            # Store the confirmed details in reservation_details for later retrieval
            if confirmed_details.confirmed_time:
                call_state.reservation_details["confirmed_time"] = (
                    confirmed_details.confirmed_time
                )
                logger.info(
                    f"✓ LLM extracted confirmed time: {confirmed_details.confirmed_time}"
                )

            if confirmed_details.confirmed_date:
                call_state.reservation_details["confirmed_date"] = (
                    confirmed_details.confirmed_date
                )
                logger.info(
                    f"✓ LLM extracted confirmed date: {confirmed_details.confirmed_date}"
                )

            if confirmed_details.restaurant_notes:
                call_state.reservation_details["restaurant_notes"] = (
                    confirmed_details.restaurant_notes
                )
                logger.info(
                    f"✓ LLM extracted notes: {confirmed_details.restaurant_notes}"
                )

            call_state.reservation_details["was_modified"] = (
                confirmed_details.was_modified
            )

            logger.info(f"✓ Transcript analysis complete for call {call_id}")

        except Exception as e:
            logger.error(f"Error analyzing transcript with LLM: {e}", exc_info=True)
            # Fallback: don't update anything, keep the call as-is

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
