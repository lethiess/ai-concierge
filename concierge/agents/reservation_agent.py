"""Reservation agent for handling restaurant reservation requests using OpenAI Agents SDK."""

import logging
from collections.abc import Callable

from agents import Agent, function_tool
from pydantic import BaseModel

from concierge.config import get_config
from concierge.models import Restaurant
from concierge.prompts import load_prompt
from datetime import datetime

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


class ReservationAgent:
    """Reservation agent that handles the reservation workflow.

    This agent:
    - Parses and validates reservation requests
    - Looks up restaurant information
    - Prepares details for the voice agent
    - Initiates the real-time voice call

    Attributes:
        restaurant_lookup_tool: The restaurant lookup function tool
        config: Application configuration
        _agent: The underlying Agent instance (created lazily)
    """

    def __init__(self, restaurant_lookup_tool: Callable) -> None:
        """Initialize the reservation agent.

        Args:
            restaurant_lookup_tool: The restaurant lookup function tool
        """
        self.restaurant_lookup_tool = restaurant_lookup_tool
        self.config = get_config()
        self._agent: Agent | None = None

        logger.info("ReservationAgent initialized")

    def create(self) -> Agent:
        """Create and return the configured reservation agent.

        Returns:
            Configured reservation agent

        Note:
            The agent is created lazily on first call and cached.
        """
        if self._agent is None:
            # Create the call initiation tool with config defaults
            config = self.config

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

                # Use concierge name from config if not provided
                if not customer_name:
                    customer_name = config.concierge_name
                    logger.info(f"Using concierge name from config: {customer_name}")

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
                result = await make_reservation_call_via_twilio(
                    reservation_details, restaurant
                )

                return {
                    "success": result.status == "confirmed",
                    "status": result.status,
                    "confirmation_number": result.confirmation_number,
                    "message": result.message,
                    "call_duration": result.call_duration,
                    "call_id": result.call_id,
                }

            # Load instructions from template with current date/time context
            current_datetime = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
            instructions = load_prompt(
                "reservation_agent", current_datetime=current_datetime
            )

            self._agent = Agent(
                name="Reservation Agent",
                model=self.config.agent_model,
                instructions=instructions,
                tools=[self.restaurant_lookup_tool, initiate_reservation_call],
                # Note: output_type removed to allow tool calls before completion
                # The agent will call tools first, then return text describing the result
            )
            logger.info("Reservation agent created successfully")

        return self._agent

    @property
    def agent(self) -> Agent:
        """Get the agent instance (creates it if needed).

        Returns:
            The reservation agent
        """
        return self.create()
