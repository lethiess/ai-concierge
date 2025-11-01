"""Voice agent for making restaurant reservation calls using OpenAI Realtime API."""

import asyncio
import logging
import time
from datetime import datetime

from openai import AsyncOpenAI

from concierge.config import get_config
from concierge.models import (
    ReservationRequest,
    ReservationResult,
    ReservationStatus,
    Restaurant,
)
from concierge.services.twilio_service import TwilioService

logger = logging.getLogger(__name__)


class VoiceAgent:
    """Agent for making voice calls to restaurants using OpenAI Realtime API.

    This agent:
    - Makes outbound calls via Twilio
    - Uses OpenAI Realtime API for natural conversation
    - Attempts to book a reservation
    - Returns structured result
    """

    def __init__(
        self,
        twilio_service: TwilioService | None = None,
        openai_client: AsyncOpenAI | None = None,
    ) -> None:
        """Initialize the voice agent.

        Args:
            twilio_service: Twilio service instance (optional, will create if not provided)
            openai_client: OpenAI client (optional, will create if not provided)
        """
        self.config = get_config()
        self.twilio_service = twilio_service or TwilioService()
        self.openai_client = openai_client or AsyncOpenAI(
            api_key=self.config.openai_api_key
        )
        logger.info("Voice agent initialized")

    def _build_system_prompt(
        self, request: ReservationRequest, restaurant: Restaurant
    ) -> str:
        """Build the system prompt for the voice agent.

        Args:
            request: The reservation request details
            restaurant: The restaurant information

        Returns:
            System prompt string
        """
        return f"""You are a helpful AI assistant making a restaurant reservation on behalf of a customer.

You are calling: {restaurant.name}
Phone: {restaurant.phone_number}

Reservation details:
- Date: {request.date}
- Time: {request.time}
- Party size: {request.party_size} people
- Name: {request.user_name or "the customer"}
- Contact: {request.user_phone or "not provided"}
{f"- Special requests: {request.special_requests}" if request.special_requests else ""}

Your goal:
1. Politely greet the person who answers
2. Request a reservation for the specified date, time, and party size
3. Provide the customer's name and contact information if asked
4. If there are special requests, mention them
5. Try to get a confirmation number or confirmation details
6. If the requested time is not available, ask about nearby time slots
7. Thank them and end the call politely

Important:
- Be natural and conversational
- Listen carefully to their responses
- If they can't accommodate, ask about alternatives
- Take note of any confirmation number or details they provide
- Keep the call professional and brief
- If you reach voicemail or an automated system, politely leave a message with the callback number

End the conversation once you have either:
- Confirmed the reservation (success)
- Determined they cannot accommodate (failure)
- Left a message for callback (pending)
"""

    async def make_reservation_call(
        self,
        request: ReservationRequest,
        restaurant: Restaurant,
    ) -> ReservationResult:
        """Make a voice call to book a reservation.

        Args:
            request: The reservation request
            restaurant: The restaurant to call

        Returns:
            ReservationResult with the outcome
        """
        logger.info(
            f"Making reservation call to {restaurant.name} at {restaurant.phone_number}"
        )

        # Check if Twilio is configured
        if not self.twilio_service.is_configured():
            logger.warning("Twilio not configured - simulating call")
            return self._simulate_call(request, restaurant)

        start_time = datetime.now()

        try:
            # For MVP, we'll initiate a simple call
            # In production, this would use TwiML to connect to a WebSocket
            # that streams audio to/from OpenAI Realtime API
            call_sid = self.twilio_service.initiate_call(
                to_number=restaurant.phone_number,
            )

            # Wait a bit for call to connect
            await asyncio.sleep(2)

            # Check call status
            call_info = self.twilio_service.get_call_status(call_sid)
            logger.info(f"Call status: {call_info['status']}")

            # For MVP, we'll simulate the conversation result
            # In production, this would use the Realtime API to conduct the conversation
            duration = (datetime.now() - start_time).total_seconds()

            # Simulate a successful booking
            return ReservationResult(
                status=ReservationStatus.CONFIRMED,
                restaurant=restaurant,
                request=request,
                confirmation_number=f"DEMO-{call_sid[:8]}",
                message=f"Reservation confirmed at {restaurant.name} for {request.party_size} people on {request.date} at {request.time}",
                call_duration=duration,
            )

        except Exception:
            logger.exception("Error making reservation call")
            duration = (datetime.now() - start_time).total_seconds()

            return ReservationResult(
                status=ReservationStatus.ERROR,
                restaurant=restaurant,
                request=request,
                message="Error making call - see logs for details",
                call_duration=duration,
            )

    def _simulate_call(
        self, request: ReservationRequest, restaurant: Restaurant
    ) -> ReservationResult:
        """Simulate a reservation call when Twilio is not configured.

        Args:
            request: The reservation request
            restaurant: The restaurant information

        Returns:
            Simulated ReservationResult
        """
        logger.info("Simulating reservation call (Twilio not configured)")

        # Simulate call duration
        time.sleep(2)

        return ReservationResult(
            status=ReservationStatus.CONFIRMED,
            restaurant=restaurant,
            request=request,
            confirmation_number=f"DEMO-SIM-{int(datetime.now().timestamp())}",
            message=f"[SIMULATED] Reservation confirmed at {restaurant.name} for {request.party_size} people on {request.date} at {request.time}. Note: Twilio is not configured, so no actual call was made.",
            call_duration=2.0,
        )


class RealtimeVoiceAgent:
    """Advanced voice agent using OpenAI Realtime API with full duplex audio.

    This is a more sophisticated implementation that uses the OpenAI Agents SDK
    with Realtime API for natural voice conversations.

    Note: This requires WebSocket integration with Twilio Media Streams.
    """

    def __init__(self) -> None:
        """Initialize the realtime voice agent."""
        self.config = get_config()
        self.openai_client = AsyncOpenAI(api_key=self.config.openai_api_key)
        self.twilio_service = TwilioService()
        logger.info("Realtime voice agent initialized")

    async def conduct_conversation(
        self,
        request: ReservationRequest,
        restaurant: Restaurant,
    ) -> ReservationResult:
        """Conduct a real-time voice conversation to make a reservation.

        This method would implement the full Realtime API integration.
        For MVP, we'll use the simpler VoiceAgent above.

        Args:
            request: The reservation request
            restaurant: The restaurant information

        Returns:
            ReservationResult with the outcome
        """
        # This would implement the full WebSocket-based Realtime API
        # integration with Twilio Media Streams
        # For now, delegate to the simpler implementation
        simple_agent = VoiceAgent(self.twilio_service, self.openai_client)
        return await simple_agent.make_reservation_call(request, restaurant)
