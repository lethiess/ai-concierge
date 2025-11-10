"""Twilio service for voice call integration."""

import logging
from typing import Any

from twilio.rest import Client

from concierge.config import get_config

logger = logging.getLogger(__name__)


class TwilioService:
    """Service for managing Twilio voice calls and audio streaming.

    This service handles:
    - Initiating outbound calls
    - Managing call state
    - Streaming audio between Twilio and OpenAI Realtime API
    """

    def __init__(self) -> None:
        """Initialize the Twilio service."""
        self.config = get_config()
        if not self.config.has_twilio_config():
            logger.warning("Twilio not configured - service will not be functional")
            self.client = None
        else:
            self.client = Client(
                self.config.twilio_account_sid, self.config.twilio_auth_token
            )
            logger.info("Twilio service initialized")

    def is_configured(self) -> bool:
        """Check if Twilio is properly configured.

        Returns:
            True if Twilio credentials are set, False otherwise
        """
        return self.client is not None

    def _validate_phone_number(self, phone_number: str) -> None:
        """Validate that only the demo restaurant number can be called.

        This prevents expensive calls to unauthorized numbers.

        Args:
            phone_number: The phone number to validate

        Raises:
            ValueError: If the number is not the demo restaurant number
        """
        demo_number = self.config.demo_restaurant_phone

        # Normalize phone numbers for comparison (remove spaces, dashes, etc.)
        normalized_demo = (
            demo_number.replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )
        normalized_input = (
            phone_number.replace(" ", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
        )

        # Only allow demo restaurant number
        if normalized_input != normalized_demo:
            raise ValueError(
                f"Only the demo restaurant number can be called. "
                f"Attempted: {phone_number}, Allowed: {demo_number}. "
                f"This is a safety feature to prevent unauthorized calls."
            )

        logger.info(f"Phone number validated: {phone_number} matches demo number")

    def initiate_call(
        self,
        to_number: str,
        twiml_url: str | None = None,
        status_callback: str | None = None,
    ) -> str:
        """Initiate an outbound call.

        Only the demo restaurant number from config can be called.
        This is a safety feature to prevent unauthorized calls.

        Args:
            to_number: The phone number to call (must match demo_restaurant_phone)
            twiml_url: URL that returns TwiML instructions (optional)
            status_callback: URL for call status callbacks (optional)

        Returns:
            Call SID

        Raises:
            ValueError: If Twilio is not configured or number is not allowed
            Exception: If call initiation fails
        """
        if not self.client:
            msg = "Twilio is not configured"
            raise ValueError(msg)

        # Validate phone number - only allow demo restaurant number
        self._validate_phone_number(to_number)

        try:
            logger.info(f"Initiating call to {to_number}")

            call_params = {
                "to": to_number,
                "from_": self.config.twilio_phone_number,
            }

            if twiml_url:
                call_params["url"] = twiml_url
            else:
                # Default TwiML for testing
                call_params["twiml"] = (
                    "<Response><Say>Hello, this is a test call from AI Concierge.</Say></Response>"
                )

            if status_callback:
                call_params["status_callback"] = status_callback
                call_params["status_callback_event"] = [
                    "initiated",
                    "ringing",
                    "answered",
                    "completed",
                ]

            call = self.client.calls.create(**call_params)

        except Exception:
            logger.exception("Failed to initiate call")
            raise
        else:
            logger.info(f"Call initiated with SID: {call.sid}")
            return call.sid

    def get_call_status(self, call_sid: str) -> dict[str, Any]:
        """Get the status of a call.

        Args:
            call_sid: The call SID

        Returns:
            Dictionary with call status information

        Raises:
            ValueError: If Twilio is not configured
        """
        if not self.client:
            msg = "Twilio is not configured"
            raise ValueError(msg)

        try:
            call = self.client.calls(call_sid).fetch()

        except Exception:
            logger.exception("Failed to get call status")
            raise
        else:
            return {
                "sid": call.sid,
                "status": call.status,
                "duration": call.duration,
                "to": call.to,
                "from": call.from_,
                "start_time": call.start_time,
                "end_time": call.end_time,
            }

    def end_call(self, call_sid: str) -> None:
        """End an active call.

        Args:
            call_sid: The call SID

        Raises:
            ValueError: If Twilio is not configured
        """
        if not self.client:
            msg = "Twilio is not configured"
            raise ValueError(msg)

        try:
            logger.info(f"Ending call {call_sid}")
            self.client.calls(call_sid).update(status="completed")

        except Exception:
            logger.exception("Failed to end call")
            raise
