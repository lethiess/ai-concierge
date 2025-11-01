"""Reservation agent for handling restaurant reservation requests using OpenAI Agents SDK."""

import logging

from agents import Agent, function_tool
from pydantic import BaseModel

from concierge.config import get_config
from concierge.models import Restaurant

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


def create_reservation_agent(restaurant_lookup_tool) -> Agent:
    """Create the reservation agent that handles the reservation workflow.

    This agent:
    - Parses and validates reservation requests
    - Looks up restaurant information
    - Prepares details for the voice agent
    - Initiates the real-time voice call

    Note: This agent does NOT hand off to a voice agent in the traditional sense.
    Instead, it prepares the reservation details and triggers a real-time voice call
    using the Realtime API, which is handled outside the agent loop.

    Args:
        restaurant_lookup_tool: The restaurant lookup function tool

    Returns:
        Configured reservation agent
    """
    config = get_config()

    # Create the call initiation tool
    @function_tool
    async def initiate_reservation_call(
        restaurant_name: str,
        restaurant_phone: str,
        party_size: int,
        date: str,
        time: str,
        customer_name: str | None = None,
        special_requests: str | None = None,
    ) -> dict:
        """Initiate a real-time voice call to make the restaurant reservation.

        This triggers a Twilio call that uses OpenAI Realtime API for the conversation.

        Args:
            restaurant_name: Name of the restaurant
            restaurant_phone: Phone number to call
            party_size: Number of people
            date: Reservation date
            time: Reservation time
            customer_name: Customer name for the reservation
            special_requests: Any special requests

        Returns:
            Dictionary with call initiation result
        """
        # Import here to avoid circular dependency
        from concierge.agents.voice_agent import (
            make_reservation_call_via_twilio,
        )

        logger.info(f"Initiating realtime voice call to {restaurant_name}")

        # Prepare reservation details
        reservation_details = {
            "restaurant_name": restaurant_name,
            "restaurant_phone": restaurant_phone,
            "party_size": party_size,
            "date": date,
            "time": time,
            "customer_name": customer_name,
            "special_requests": special_requests,
        }

        # Create restaurant object (in real implementation, this would come from lookup)
        restaurant = Restaurant(
            name=restaurant_name,
            phone_number=restaurant_phone,
            address="",  # Not needed for call
            cuisine_type="",  # Not needed for call
        )

        # Make the realtime voice call
        result = await make_reservation_call_via_twilio(reservation_details, restaurant)

        return {
            "success": result.status == "confirmed",
            "status": result.status,
            "confirmation_number": result.confirmation_number,
            "message": result.message,
            "call_duration": result.call_duration,
        }

    reservation_agent = Agent(
        name="Reservation Agent",
        model=config.agent_model,
        instructions="""You are a specialized restaurant reservation agent. Your role is to:

1. Parse the user's reservation request and extract:
   - Restaurant name
   - Party size (number of people, must be 1-50)
   - Date of reservation
   - Time of reservation
   - Customer name (if provided)
   - Customer phone (if provided)
   - Any special requests

2. Use the find_restaurant tool to look up the restaurant details (especially the phone number)

3. Validate the information:
   - Party size must be between 1 and 50 people
   - All required fields must be present (restaurant, party size, date, time)

4. Once you have all the information and found the restaurant, use the initiate_reservation_call
   tool to make the actual phone call to the restaurant.

5. The initiate_reservation_call tool will:
   - Use OpenAI Realtime API for natural voice conversation
   - Connect via Twilio to make the actual phone call
   - Conduct the reservation conversation in real-time
   - Return the result (confirmed, pending, or rejected)

Be polite, concise, and ask for missing information if needed.
If the restaurant is not found, inform the user and ask for clarification.

After initiating the call, report the result to the user clearly.
""",
        tools=[restaurant_lookup_tool, initiate_reservation_call],
        output_type=ReservationDetails,
    )

    logger.info("Reservation agent created")
    return reservation_agent
