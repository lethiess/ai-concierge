"""Cancellation voice agent for making real-time cancellation calls using OpenAI Realtime API."""

import logging
from datetime import datetime

from agents.realtime import RealtimeAgent

from concierge.agents.prompts import load_prompt

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
            cancellation_details: Dictionary containing cancellation information
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
