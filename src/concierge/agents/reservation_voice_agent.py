"""Reservation voice agent for making real-time restaurant reservation calls using OpenAI Realtime API."""

import logging
from datetime import datetime

from agents.realtime import RealtimeAgent

from concierge.agents.prompts import load_prompt

logger = logging.getLogger(__name__)


class ReservationVoiceAgent:
    """Reservation voice agent for making real-time restaurant reservation calls.

    This agent uses OpenAI's Realtime API for full-duplex audio conversations,
    enabling natural phone calls to restaurants via Twilio Media Streams.

    Attributes:
        reservation_details: Dictionary containing reservation information
        _agent: The underlying RealtimeAgent instance (created lazily)
    """

    def __init__(self, reservation_details: dict) -> None:
        """Initialize the reservation voice agent.

        Args:
            reservation_details: Dictionary containing reservation information
        """
        self.reservation_details = reservation_details
        self._agent: RealtimeAgent | None = None

        logger.info(
            "ReservationVoiceAgent initialized for %s",
            reservation_details.get("restaurant_name", "unknown restaurant"),
        )

    def create(self) -> RealtimeAgent:
        """Create and return the configured RealtimeAgent.

        Returns:
            Configured RealtimeAgent for conducting the reservation call
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
                "reservation_voice_agent",
                restaurant_name=restaurant_name,
                party_size=party_size,
                date=date,
                time=time,
                customer_name=customer_name,
                special_requests=special_requests_text,
                current_date=current_date,
            )

            # Create the RealtimeAgent with minimal configuration
            self._agent = RealtimeAgent(
                name="Restaurant Reservation Voice Agent",
                instructions=instructions,
            )

            logger.info(
                "✅ ReservationVoiceAgent created for calling %s", restaurant_name
            )

        return self._agent

    @property
    def agent(self) -> RealtimeAgent:
        """Get the agent instance (creates it if needed).

        Returns:
            The reservation voice agent
        """
        return self.create()
