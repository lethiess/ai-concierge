"""Voice agent for making restaurant reservation calls using OpenAI Agents SDK."""

import logging
from datetime import datetime

from agents import Agent
from pydantic import BaseModel

from concierge.config import get_config
from concierge.models import Restaurant

logger = logging.getLogger(__name__)


class ReservationResult(BaseModel):
    """Structured output for reservation result."""

    status: str  # "confirmed", "pending", "rejected", "error"
    restaurant_name: str
    confirmation_number: str | None = None
    message: str
    call_duration: float | None = None


def create_voice_agent(make_call_tool, get_call_status_tool, end_call_tool) -> Agent:
    """Create the voice agent for making reservation calls.

    Args:
        make_call_tool: Function tool to initiate a call
        get_call_status_tool: Function tool to check call status
        end_call_tool: Function tool to end a call

    Returns:
        Configured voice agent
    """
    config = get_config()

    voice_agent = Agent(
        name="Voice Reservation Agent",
        model=config.agent_model,
        instructions="""You are a voice reservation agent. Your role is to:

1. Make a phone call to the restaurant using the make_call tool
2. Conduct a natural conversation to book the reservation
3. Provide all reservation details:
   - Date and time
   - Party size
   - Customer name
   - Special requests (if any)

4. Try to get a confirmation number
5. If the requested time is not available, ask about alternatives
6. Return a structured result with the outcome

When calling:
- Be polite and professional
- Speak clearly and concisely
- Listen carefully to responses
- Handle voicemail gracefully
- Thank them at the end

For the MVP, since Twilio may not be configured, you may simulate the call.
""",
        tools=[make_call_tool, get_call_status_tool, end_call_tool],
        output_type=ReservationResult,
    )

    logger.info("Voice agent created")
    return voice_agent


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

    # Simulate call duration
    time.sleep(2)

    return ReservationResult(
        status="confirmed",
        restaurant_name=restaurant.name,
        confirmation_number=f"DEMO-SIM-{int(datetime.now().timestamp())}",
        message=f"[SIMULATED] Reservation confirmed at {restaurant.name} for {party_size} people on {date} at {time}. Note: Twilio is not configured, so no actual call was made.",
        call_duration=2.0,
    )
