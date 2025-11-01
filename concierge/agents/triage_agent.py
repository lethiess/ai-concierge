"""Triage/Orchestrator agent using OpenAI Agents SDK."""

import logging
from typing import Any

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


def create_triage_agent(voice_agent: Agent, restaurant_lookup_tool) -> Agent:
    """Create the triage agent with handoff to voice agent.

    Args:
        voice_agent: The voice agent to hand off to
        restaurant_lookup_tool: The restaurant lookup function tool

    Returns:
        Configured triage agent
    """
    config = get_config()

    triage_agent = Agent(
        name="Reservation Triage Agent",
        model=config.agent_model,
        instructions="""You are a restaurant reservation assistant. Your role is to:

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

3. Look up the restaurant using the find_restaurant tool

4. Once you have validated the reservation details and found the restaurant,
   hand off to the Voice Agent to make the actual reservation call.

Be polite, concise, and ask for missing information if needed.
""",
        tools=[restaurant_lookup_tool],
        handoffs=[voice_agent],
        output_type=ReservationDetails,
    )

    logger.info("Triage agent created")
    return triage_agent


def format_reservation_result(result: Any) -> str:
    """Format a reservation result for display to the user.

    Args:
        result: The reservation result from the agent run

    Returns:
        Formatted string for display
    """
    output = []

    output.append("=" * 60)
    output.append("RESERVATION RESULT")
    output.append("=" * 60)

    # Extract information from the result
    if hasattr(result, "final_output"):
        output.append(f"\n{result.final_output}")

    output.append("\n" + "=" * 60)

    return "\n".join(output)
