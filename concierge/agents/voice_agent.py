"""Voice agent for making real-time restaurant reservation calls using OpenAI Realtime API."""

import asyncio
import logging
from datetime import datetime

from agents.realtime import RealtimeAgent
from pydantic import BaseModel

from concierge.config import get_config
from concierge.models import Restaurant
from concierge.prompts import load_prompt
from concierge.services.call_manager import get_call_manager
from concierge.services.twilio_service import TwilioService
import contextlib

logger = logging.getLogger(__name__)


class ReservationResult(BaseModel):
    """Structured output for reservation result."""

    status: str  # "confirmed", "pending", "rejected", "error"
    restaurant_name: str
    confirmation_number: str | None = None
    message: str
    call_duration: float | None = None
    call_id: str | None = None


class VoiceAgent:
    """Voice agent for making real-time restaurant reservation calls.

    This agent uses OpenAI's Realtime API for full-duplex audio conversations,
    enabling natural phone calls to restaurants via Twilio Media Streams.

    Attributes:
        reservation_details: Dictionary containing reservation information
        _agent: The underlying RealtimeAgent instance (created lazily)
    """

    def __init__(self, reservation_details: dict) -> None:
        """Initialize the voice agent.

        Args:
            reservation_details: Dictionary containing reservation information:
                - restaurant_name: Name of the restaurant
                - restaurant_phone: Phone number to call
                - party_size: Number of people
                - date: Reservation date
                - time: Reservation time
                - customer_name: Optional customer name
                - special_requests: Optional special requests
        """
        self.reservation_details = reservation_details
        self._agent: RealtimeAgent | None = None

        logger.info(
            "VoiceAgent initialized for %s",
            reservation_details.get("restaurant_name", "unknown restaurant"),
        )

    def create(self) -> RealtimeAgent:
        """Create and return the configured RealtimeAgent.

        Returns:
            Configured RealtimeAgent for conducting the reservation call

        Note:
            The agent is created lazily on first call and cached.
            Full configuration (voice, temperature, etc.) is done via RealtimeRunner.
        """
        if self._agent is None:
            # Extract reservation details
            restaurant_name = self.reservation_details.get("restaurant_name")
            party_size = self.reservation_details.get("party_size")
            date = self.reservation_details.get("date")
            time = self.reservation_details.get("time")
            customer_name = self.reservation_details.get(
                "customer_name", "the customer"
            )
            special_requests = self.reservation_details.get("special_requests", "")

            # Format special requests for prompt
            special_requests_text = ""
            if special_requests:
                special_requests_text = f"**Special requests:** {special_requests}"

            # Get current date for context
            current_date = datetime.now().strftime("%A, %B %d, %Y")

            # Load and format prompt from template
            instructions = load_prompt(
                "voice_agent",
                restaurant_name=restaurant_name,
                party_size=party_size,
                date=date,
                time=time,
                customer_name=customer_name,
                special_requests=special_requests_text,
                current_date=current_date,
            )

            # Create the RealtimeAgent with minimal configuration
            # Full configuration (voice, temperature, etc.) is done via RealtimeRunner
            self._agent = RealtimeAgent(
                name="Restaurant Reservation Voice Agent",
                instructions=instructions,
            )

            logger.info("Realtime voice agent created for calling %s", restaurant_name)

        return self._agent

    @property
    def agent(self) -> RealtimeAgent:
        """Get the agent instance (creates it if needed).

        Returns:
            The voice agent
        """
        return self.create()


async def make_reservation_call_via_twilio(
    reservation_details: dict, restaurant: Restaurant
) -> ReservationResult:
    """Make a real-time reservation call using Twilio and OpenAI Realtime API.

    This function:
    1. Creates a call in CallManager with reservation details
    2. Initiates a Twilio call with TwiML pointing to WebSocket server
    3. The server handles the RealtimeAgent and audio streaming
    4. Polls for call completion
    5. Returns the result

    Args:
        reservation_details: Reservation information
        restaurant: Restaurant to call

    Returns:
        ReservationResult with the outcome of the call

    Note:
        This requires:
        - Twilio account with Media Streams capability
        - WebSocket server running (concierge.server)
        - PUBLIC_DOMAIN configured for Twilio webhooks
    """
    logger.info(f"Initiating real-time reservation call to {restaurant.name}")

    config = get_config()
    twilio_service = TwilioService()
    call_manager = get_call_manager()

    # Check if Twilio is configured
    if not twilio_service.is_configured():
        logger.error("Twilio not configured - returning simulated result")
        return ReservationResult(
            status="error",
            restaurant_name=restaurant.name,
            message="Twilio not configured - returning simulated result",
            call_duration=0.0,
            call_id=None,
        )

    # Check if server is configured
    if not config.public_domain:
        logger.error(
            "PUBLIC_DOMAIN not configured - cannot make call. "
            "Please set PUBLIC_DOMAIN in .env (e.g., your ngrok URL)"
        )
        return ReservationResult(
            status="error",
            restaurant_name=restaurant.name,
            message="Server not configured: PUBLIC_DOMAIN must be set for Twilio webhooks",
            call_duration=0.0,
            call_id=None,
        )

    start_time = datetime.now()

    try:
        # Step 1: Create call in CallManager (direct call since we're in same process)
        call_id = call_manager.generate_call_id()
        call_manager.create_call(reservation_details, call_id)
        logger.info(f"✓ Created call {call_id} in CallManager")

        # Step 2: Build TwiML URL
        twiml_url = f"https://{config.public_domain}/twiml?call_id={call_id}"
        status_callback_url = f"https://{config.public_domain}/twilio-status"
        logger.info(f"TwiML URL: {twiml_url}")

        # Step 3: Initiate Twilio call
        call_sid = twilio_service.initiate_call(
            to_number=restaurant.phone_number,
            twiml_url=twiml_url,
            status_callback=status_callback_url,
        )
        logger.info(f"Initiated Twilio call {call_sid} for reservation call {call_id}")

        # Step 4: Wait for call to complete (poll with timeout)
        result = await wait_for_call_completion(call_id, timeout=180)

        duration = (datetime.now() - start_time).total_seconds()
        result.call_duration = duration

    except Exception as e:
        logger.exception("Error making realtime reservation call")
        duration = (datetime.now() - start_time).total_seconds()

        # Try to get call_id if it was created before the error
        error_call_id = None
        with contextlib.suppress(NameError):
            error_call_id = call_id

        result = ReservationResult(
            status="error",
            restaurant_name=restaurant.name,
            message=f"Error making call: {e}",
            call_duration=duration,
            call_id=error_call_id,
        )

    return result


async def wait_for_call_completion(
    call_id: str, timeout: int = 180, poll_interval: int = 2
) -> ReservationResult:
    """Wait for a call to complete by polling CallManager.

    Args:
        call_id: Call identifier
        timeout: Maximum wait time in seconds
        poll_interval: Seconds between status checks

    Returns:
        ReservationResult

    Raises:
        TimeoutError: If call doesn't complete within timeout
    """
    call_manager = get_call_manager()
    elapsed = 0

    logger.info(f"Waiting for call {call_id} to complete (timeout: {timeout}s)")

    while elapsed < timeout:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        call_state = call_manager.get_call(call_id)
        if not call_state:
            msg = f"Call {call_id} not found in CallManager"
            raise ValueError(msg)

        if call_state.status == "completed":
            logger.info(f"Call {call_id} completed successfully")

            # Wait a bit for LLM transcript analysis to complete
            # The analysis runs async in update_status(), so we need to give it time
            max_analysis_wait = 10  # seconds
            analysis_elapsed = 0

            while analysis_elapsed < max_analysis_wait:
                # Check if transcript analysis has completed by looking for the confirmed_time field
                # which is only set by the LLM analysis
                if "confirmed_time" in call_state.reservation_details:
                    logger.info(
                        "✓ Transcript analysis completed, proceeding with result"
                    )
                    break

                # Also break if we have a confirmation number (analysis might be done)
                if call_state.confirmation_number:
                    logger.info("✓ Confirmation number present, proceeding with result")
                    break

                await asyncio.sleep(0.5)  # Check every 500ms
                analysis_elapsed += 0.5

                # Refresh call state
                call_state = call_manager.get_call(call_id)

            if analysis_elapsed >= max_analysis_wait:
                logger.warning(
                    f"⚠ Transcript analysis did not complete within {max_analysis_wait}s, proceeding anyway"
                )

            # Determine status based on confirmation number
            if call_state.confirmation_number:
                status = "confirmed"
                message = f"Reservation confirmed at {call_state.reservation_details.get('restaurant_name', 'restaurant')}"
            else:
                status = "pending"
                message = "Call completed but no confirmation number received. Please check with restaurant."

            return ReservationResult(
                status=status,
                restaurant_name=call_state.reservation_details.get(
                    "restaurant_name", "Unknown"
                ),
                confirmation_number=call_state.confirmation_number,
                message=message,
                call_id=call_id,
            )

        if call_state.status == "failed":
            logger.error(f"Call {call_id} failed: {call_state.error_message}")
            return ReservationResult(
                status="error",
                restaurant_name=call_state.reservation_details.get(
                    "restaurant_name", "Unknown"
                ),
                message=f"Call failed: {call_state.error_message}",
                call_id=call_id,
            )

    # Timeout
    logger.warning(f"Call {call_id} timed out after {timeout}s")
    await call_manager.update_status(call_id, "failed")
    call_manager.set_error(call_id, f"Call timed out after {timeout}s")

    return ReservationResult(
        status="error",
        restaurant_name=call_manager.get_call(call_id).reservation_details.get(
            "restaurant_name", "Unknown"
        ),
        message=f"Call timed out after {timeout} seconds",
        call_id=call_id,
    )
