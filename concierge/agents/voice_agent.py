"""Voice agent for making real-time restaurant reservation calls using OpenAI Realtime API."""

import logging
from datetime import datetime

from agents.realtime import RealtimeAgent
from pydantic import BaseModel

from concierge.models import Restaurant
from concierge.services.twilio_service import TwilioService

logger = logging.getLogger(__name__)


class ReservationResult(BaseModel):
    """Structured output for reservation result."""

    status: str  # "confirmed", "pending", "rejected", "error"
    restaurant_name: str
    confirmation_number: str | None = None
    message: str
    call_duration: float | None = None


def create_voice_agent(reservation_details: dict) -> RealtimeAgent:
    """Create a realtime voice agent for making restaurant reservation calls.

    This agent uses OpenAI's Realtime API for full-duplex audio conversations,
    enabling natural phone calls to restaurants via Twilio Media Streams.

    Args:
        reservation_details: Dictionary containing reservation information:
            - restaurant_name: Name of the restaurant
            - restaurant_phone: Phone number to call
            - party_size: Number of people
            - date: Reservation date
            - time: Reservation time
            - customer_name: Optional customer name
            - special_requests: Optional special requests

    Returns:
        Configured RealtimeAgent for conducting the reservation call
    """
    # Extract reservation details
    restaurant_name = reservation_details.get("restaurant_name")
    party_size = reservation_details.get("party_size")
    date = reservation_details.get("date")
    time = reservation_details.get("time")
    customer_name = reservation_details.get("customer_name", "the customer")
    special_requests = reservation_details.get("special_requests", "")

    # Build instructions for the voice agent
    instructions = f"""You are calling {restaurant_name} to make a restaurant reservation.

**Your Task:**
Make a reservation for {party_size} people on {date} at {time}.
Customer name: {customer_name}
{f"Special requests: {special_requests}" if special_requests else ""}

**Instructions:**
1. Greet the person who answers politely
2. State that you're calling to make a reservation
3. Provide the date, time, and party size
4. Give the customer's name when asked
5. Mention any special requests if applicable
6. Try to get a confirmation number
7. If the requested time is unavailable, ask about nearby time slots
8. Thank them and end the call politely

**Important:**
- Be natural and conversational
- Listen carefully to their responses
- Be flexible if they suggest alternative times
- If you reach voicemail, leave a brief message with a callback number
- Keep the call professional and concise

Your goal is to successfully book the reservation or gather information about alternatives.
"""

    # Create the RealtimeAgent with minimal configuration
    # Full configuration (voice, temperature, etc.) is done via RealtimeRunner
    voice_agent = RealtimeAgent(
        name="Restaurant Reservation Voice Agent",
        instructions=instructions,
    )

    logger.info(f"Realtime voice agent created for calling {restaurant_name}")
    return voice_agent


async def make_reservation_call_via_twilio(
    reservation_details: dict, restaurant: Restaurant
) -> ReservationResult:
    """Make a real-time reservation call using Twilio and OpenAI Realtime API.

    This function:
    1. Creates a RealtimeAgent configured for the reservation
    2. Initiates a Twilio call to the restaurant
    3. Connects Twilio Media Streams to the RealtimeAgent
    4. Conducts the voice conversation in real-time
    5. Returns the result

    Args:
        reservation_details: Reservation information
        restaurant: Restaurant to call

    Returns:
        ReservationResult with the outcome of the call

    Note:
        This requires:
        - Twilio account with Media Streams capability
        - WebSocket server to connect Twilio ↔ RealtimeAgent
        - Proper audio format handling (PCM16, mulaw, etc.)
    """
    logger.info(f"Initiating real-time reservation call to {restaurant.name}")

    twilio_service = TwilioService()

    if not twilio_service.is_configured():
        logger.warning("Twilio not configured - returning simulated result")
        return simulate_reservation_call(
            restaurant,
            reservation_details["party_size"],
            reservation_details["date"],
            reservation_details["time"],
        )

    start_time = datetime.now()

    try:
        # Create the realtime voice agent with reservation context
        _voice_agent = create_voice_agent(reservation_details)

        # TODO: Implement the full Twilio Media Streams integration
        # This requires:
        # 1. Start a WebSocket server to handle Twilio Media Streams
        # 2. Initiate Twilio call with TwiML that connects to the WebSocket
        # 3. Use RealtimeRunner to manage the agent session
        # 4. Stream audio bidirectionally: Twilio ↔ WebSocket ↔ RealtimeAgent
        # 5. Handle call events (answered, completed, failed, etc.)
        # 6. Extract confirmation number from conversation
        # 7. Return structured result

        # For MVP, we simulate the call
        logger.warning(
            "Full Twilio Media Streams integration not yet implemented - simulating"
        )
        duration = (datetime.now() - start_time).total_seconds()

        return ReservationResult(
            status="confirmed",
            restaurant_name=restaurant.name,
            confirmation_number=f"REALTIME-SIM-{int(datetime.now().timestamp())}",
            message=f"[SIMULATED REALTIME CALL] Reservation confirmed at {restaurant.name} for {reservation_details['party_size']} people on {reservation_details['date']} at {reservation_details['time']}. "
            "Note: Full Twilio Media Streams integration pending.",
            call_duration=duration,
        )

    except Exception as e:
        logger.exception("Error making realtime reservation call")
        duration = (datetime.now() - start_time).total_seconds()

        return ReservationResult(
            status="error",
            restaurant_name=restaurant.name,
            message=f"Error making call - see logs for details: {e}",
            call_duration=duration,
        )


def simulate_reservation_call(
    restaurant: Restaurant, party_size: int, date: str, time: str
) -> ReservationResult:
    """Simulate a reservation call when Twilio is not configured.

    Args:
        restaurant: The restaurant information
        party_size: Number of people
        date: Reservation date
        time: Reservation time

    Returns:
        Simulated ReservationResult
    """
    logger.info("Simulating reservation call (Twilio not configured)")

    return ReservationResult(
        status="confirmed",
        restaurant_name=restaurant.name,
        confirmation_number=f"DEMO-SIM-{int(datetime.now().timestamp())}",
        message=f"[SIMULATED] Reservation confirmed at {restaurant.name} for {party_size} people on {date} at {time}. "
        "Note: Twilio is not configured, so no actual call was made. "
        "In production, this would use OpenAI Realtime API + Twilio Media Streams for real-time voice conversation.",
        call_duration=2.0,
    )
