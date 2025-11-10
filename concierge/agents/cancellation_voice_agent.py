"""Cancellation voice agent for making real-time cancellation calls using OpenAI Realtime API."""

import asyncio
import logging
from datetime import datetime

from agents.realtime import RealtimeAgent

from concierge.config import get_config
from concierge.prompts import load_prompt
from concierge.services.call_manager import get_call_manager
from concierge.services.twilio_service import TwilioService

logger = logging.getLogger(__name__)


class CancellationVoiceAgent:
    """Voice agent for making real-time cancellation calls.

    This agent uses OpenAI's Realtime API for full-duplex audio conversations,
    enabling natural phone calls to restaurants to cancel reservations.

    Attributes:
        cancellation_details: Dictionary containing cancellation information
        _agent: The underlying RealtimeAgent instance (created lazily)
    """

    def __init__(self, cancellation_details: dict) -> None:
        """Initialize the cancellation voice agent.

        Args:
            cancellation_details: Dictionary containing cancellation information:
                - restaurant_name: Name of the restaurant
                - restaurant_phone: Phone number to call
                - confirmation_number: Confirmation number to cancel
                - date: Original reservation date
                - time: Original reservation time
                - party_size: Number of people
                - customer_name: Optional customer name
        """
        self.cancellation_details = cancellation_details
        self._agent: RealtimeAgent | None = None

        logger.info(
            "CancellationVoiceAgent initialized for %s",
            cancellation_details.get("restaurant_name", "unknown restaurant"),
        )

    def create(self) -> RealtimeAgent:
        """Create and return the configured RealtimeAgent.

        Returns:
            Configured RealtimeAgent for conducting the cancellation call

        Note:
            The agent is created lazily on first call and cached.
        """
        if self._agent is None:
            # Extract cancellation details
            restaurant_name = self.cancellation_details.get("restaurant_name")
            confirmation_number = self.cancellation_details.get("confirmation_number")
            party_size = self.cancellation_details.get("party_size")
            date = self.cancellation_details.get("date")
            time = self.cancellation_details.get("time")
            customer_name = self.cancellation_details.get(
                "customer_name", "the customer"
            )

            # Get current date for context
            current_date = datetime.now().strftime("%A, %B %d, %Y")

            # Log details being used for prompt
            logger.info("=" * 70)
            logger.info("Creating CancellationVoiceAgent with these details:")
            logger.info(f"  Restaurant: {restaurant_name}")
            logger.info(f"  Confirmation: {confirmation_number}")
            logger.info(f"  Party size: {party_size}")
            logger.info(f"  Date: {date}")
            logger.info(f"  Time: {time}")
            logger.info(f"  Customer: {customer_name}")
            logger.info("=" * 70)

            # Load and format prompt from template
            instructions = load_prompt(
                "cancellation_voice_agent",
                restaurant_name=restaurant_name,
                confirmation_number=confirmation_number,
                party_size=party_size,
                date=date,
                time=time,
                customer_name=customer_name,
                current_date=current_date,
            )

            # Log first 500 chars of instructions to verify template substitution
            logger.info(
                f"Agent instructions (first 500 chars): {instructions[:500]}..."
            )

            # Create the RealtimeAgent
            self._agent = RealtimeAgent(
                name="Restaurant Cancellation Voice Agent",
                instructions=instructions,
            )

            logger.info(
                "✅ CancellationVoiceAgent created for %s (confirmation: %s)",
                restaurant_name,
                confirmation_number,
            )

        return self._agent

    @property
    def agent(self) -> RealtimeAgent:
        """Get the agent instance (creates it if needed).

        Returns:
            The cancellation voice agent
        """
        return self.create()

    async def make_cancellation_call(self) -> dict:
        """Make a real-time cancellation call using Twilio and OpenAI Realtime API.

        Returns:
            Dictionary with cancellation result:
            {
                "success": True,
                "status": "cancelled",
                "message": "...",
                "call_id": "...",
                "call_duration": 45.2
            }
        """
        restaurant_name = self.cancellation_details.get("restaurant_name")
        restaurant_phone = self.cancellation_details.get("restaurant_phone")
        confirmation_number = self.cancellation_details.get("confirmation_number")

        logger.info(
            f"Initiating real-time cancellation call to {restaurant_name} "
            f"for confirmation #{confirmation_number}"
        )

        config = get_config()
        twilio_service = TwilioService()
        call_manager = get_call_manager()

        # Check if Twilio is configured
        if not twilio_service.is_configured():
            logger.error("Twilio not configured - returning simulated result")
            return {
                "success": False,
                "status": "error",
                "message": "Twilio not configured. Cannot make actual phone calls.",
                "call_id": None,
                "call_duration": None,
            }

        try:
            # Create a unique call ID
            import uuid

            call_id = str(uuid.uuid4())

            # Register the call with CallManager
            call_manager.create_call(
                call_id=call_id,
                reservation_details={
                    "restaurant_name": restaurant_name,
                    "restaurant_phone": restaurant_phone,
                    "confirmation_number": confirmation_number,
                    "party_size": self.cancellation_details.get("party_size"),
                    "date": self.cancellation_details.get("date"),
                    "time": self.cancellation_details.get("time"),
                    "customer_name": self.cancellation_details.get("customer_name"),
                    "call_type": "cancellation",  # Mark as cancellation call
                },
            )

            # Create the voice agent
            self.create()

            # Build TwiML URL for cancellation call
            config = get_config()
            twiml_url = f"https://{config.public_domain}/twiml?call_id={call_id}"
            status_callback_url = f"https://{config.public_domain}/twilio-status"
            logger.info(f"TwiML URL: {twiml_url}")

            # Initiate the Twilio call with WebSocket TwiML
            twilio_call_sid = twilio_service.initiate_call(
                to_number=restaurant_phone,
                twiml_url=twiml_url,
                status_callback=status_callback_url,
            )

            logger.info(
                f"Initiated Twilio call {twilio_call_sid} for cancellation {call_id}"
            )

            # Wait for the call to complete (with timeout)
            max_wait = 120  # 2 minutes max
            wait_interval = 2  # Check every 2 seconds
            elapsed = 0

            while elapsed < max_wait:
                await asyncio.sleep(wait_interval)
                elapsed += wait_interval

                # Check call status
                call_state = call_manager.get_call(call_id)
                if call_state and call_state.status in ["completed", "failed"]:
                    break

            # Get final call state
            call_state = call_manager.get_call(call_id)

            if not call_state:
                logger.error(f"Call {call_id} not found in CallManager")
                return {
                    "success": False,
                    "status": "error",
                    "message": "Call state lost. Cancellation status unknown.",
                    "call_id": call_id,
                    "call_duration": None,
                }

            logger.info(
                f"Cancellation call {call_id} completed with status: {call_state.status}"
            )

            # Calculate duration
            call_duration = None
            if call_state.start_time and call_state.end_time:
                call_duration = (
                    call_state.end_time - call_state.start_time
                ).total_seconds()

            # Build result
            if call_state.status == "completed":
                # Get reservation details
                date = self.cancellation_details.get("date", "")
                time = self.cancellation_details.get("time", "")
                party_size = self.cancellation_details.get("party_size", "")

                # Build confirmation message with details
                confirmation_msg = (
                    f"Your reservation at {restaurant_name} for {party_size} people "
                    f"on {date} at {time} has been successfully cancelled. "
                    f"Original confirmation number: {confirmation_number}."
                )

                # Check if transcript analysis found a cancellation reference number
                # (optional - most restaurants don't provide one)
                if call_state.confirmation_number:
                    confirmation_msg += (
                        f" Restaurant noted: {call_state.confirmation_number}"
                    )

                return {
                    "success": True,
                    "status": "cancelled",
                    "message": confirmation_msg,
                    "call_id": call_id,
                    "call_duration": call_duration,
                    "restaurant_name": restaurant_name,
                    "original_confirmation": confirmation_number,
                    "date": date,
                    "time": time,
                    "party_size": party_size,
                }
            error_msg = call_state.error_message or "Call failed or timed out"
            return {
                "success": False,
                "status": "error",
                "message": f"Failed to cancel reservation: {error_msg}",
                "call_id": call_id,
                "call_duration": call_duration,
            }

        except Exception as e:
            logger.error(
                f"Error making cancellation call: {e}",
                exc_info=True,
            )
            return {
                "success": False,
                "status": "error",
                "message": f"Error making cancellation call: {e!s}",
                "call_id": None,
                "call_duration": None,
            }
