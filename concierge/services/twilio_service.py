"""Twilio service for voice call integration."""

import base64
import json
import logging
from typing import Any
from collections.abc import Callable

import websockets
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

    def initiate_call(
        self,
        to_number: str,
        twiml_url: str | None = None,
        status_callback: str | None = None,
    ) -> str:
        """Initiate an outbound call.

        Args:
            to_number: The phone number to call
            twiml_url: URL that returns TwiML instructions (optional)
            status_callback: URL for call status callbacks (optional)

        Returns:
            Call SID

        Raises:
            ValueError: If Twilio is not configured
            Exception: If call initiation fails
        """
        if not self.client:
            msg = "Twilio is not configured"
            raise ValueError(msg)

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


class TwilioRealtimeMediaStream:
    """Handler for Twilio Media Streams with OpenAI Realtime API.

    This class manages the bidirectional audio streaming between
    Twilio and OpenAI's Realtime API.
    """

    def __init__(
        self,
        openai_ws_handler: Callable,
        sample_rate: int = 8000,
    ) -> None:
        """Initialize the media stream handler.

        Args:
            openai_ws_handler: Async handler for OpenAI WebSocket messages
            sample_rate: Audio sample rate (Twilio uses 8000 Hz mulaw)
        """
        self.openai_ws_handler = openai_ws_handler
        self.sample_rate = sample_rate
        self.stream_sid: str | None = None
        logger.info("Twilio Realtime Media Stream handler initialized")

    async def handle_twilio_stream(self, websocket: Any) -> None:
        """Handle incoming Twilio Media Stream WebSocket.

        Args:
            websocket: The Twilio Media Stream WebSocket connection
        """
        logger.info("Handling Twilio Media Stream connection")

        try:
            async for message in websocket:
                data = json.loads(message)
                event_type = data.get("event")

                if event_type == "start":
                    self.stream_sid = data["start"]["streamSid"]
                    logger.info(f"Media stream started: {self.stream_sid}")

                elif event_type == "media":
                    # Audio data from Twilio (base64 encoded mulaw)
                    payload = data["media"]["payload"]
                    # Decode and send to OpenAI handler
                    await self._process_audio_from_twilio(payload)

                elif event_type == "stop":
                    logger.info(f"Media stream stopped: {self.stream_sid}")
                    break

        except websockets.exceptions.ConnectionClosed:
            logger.info("Twilio Media Stream connection closed")

        except Exception:
            logger.exception("Error in Twilio Media Stream")

    async def _process_audio_from_twilio(self, payload: str) -> None:
        """Process audio received from Twilio.

        Args:
            payload: Base64 encoded mulaw audio from Twilio
        """
        # Decode the audio
        audio_bytes = base64.b64decode(payload)

        # Send to OpenAI handler
        # This would be implemented based on the specific OpenAI Realtime API pattern
        await self.openai_ws_handler(
            {
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(audio_bytes).decode("utf-8"),
            }
        )

    async def send_audio_to_twilio(self, websocket: Any, audio_data: bytes) -> None:
        """Send audio from OpenAI back to Twilio.

        Args:
            websocket: The Twilio WebSocket connection
            audio_data: Raw audio bytes to send
        """
        if not self.stream_sid:
            logger.warning("Cannot send audio - stream not started")
            return

        # Encode audio to base64
        payload = base64.b64encode(audio_data).decode("utf-8")

        # Send as Twilio media event
        message = json.dumps(
            {
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {
                    "payload": payload,
                },
            }
        )

        await websocket.send(message)
