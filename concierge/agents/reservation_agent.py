"""Reservation agent for handling restaurant reservation requests using OpenAI Agents SDK."""

import logging

from agents import Agent
from pydantic import BaseModel

from concierge.config import get_config

logger = logging.getLogger(__name__)


class ReservationDetails(BaseModel):
    """Structured output for parsed reservation request."""

    restaurant_name: str
    party_size: int
    date: str
    time: str
    user_name: str | None = None
    user_phone: str | None = None
    special_requests: str | None = None


def create_reservation_agent(voice_agent: Agent, restaurant_lookup_tool) -> Agent:
    """Create the reservation agent with handoff to voice agent.

    This agent handles the full reservation workflow:
    - Parse reservation details
    - Look up restaurant
    - Hand off to voice agent for the call

    Args:
        voice_agent: The voice agent to hand off to
        restaurant_lookup_tool: The restaurant lookup function tool

    Returns:
        Configured reservation agent
    """
    config = get_config()

    reservation_agent = Agent(
        name="Reservation Agent",
        model=config.agent_model,
        instructions="""You are a specialized restaurant reservation agent. Your role is to:

1. Parse the user's reservation request and extract:
   - Restaurant name
   - Party size (number of people)
   - Date of reservation
   - Time of reservation
   - Customer name (if provided)
   - Customer phone (if provided)
   - Any special requests

2. Validate the information:
   - Party size must be between 1 and 50 people
   - All required fields must be present (restaurant, party size, date, time)

3. Use the find_restaurant tool to look up the restaurant details

4. Once you have validated the reservation details and found the restaurant,
   hand off to the Voice Agent to make the actual reservation call.

Be polite, concise, and ask for missing information if needed.
If the restaurant is not found, inform the user and ask for clarification.
""",
        tools=[restaurant_lookup_tool],
        handoffs=[voice_agent],
        output_type=ReservationDetails,
    )

    logger.info("Reservation agent created")
    return reservation_agent
