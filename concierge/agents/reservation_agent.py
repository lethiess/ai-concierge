"""Reservation agent for handling restaurant reservation requests using OpenAI Agents SDK."""

import logging
from collections.abc import Callable
from datetime import datetime

from agents import Agent

from concierge.config import get_config
from concierge.prompts import load_prompt

logger = logging.getLogger(__name__)


class ReservationAgent:
    """Reservation agent that handles the reservation workflow.

    This agent:
    - Parses and validates reservation requests
    - Looks up restaurant information
    - Prepares details for the voice agent
    - Initiates the real-time voice call

    Attributes:
        restaurant_lookup_tool: The restaurant lookup function tool
        reservation_call_tool: The reservation call initiation tool
        config: Application configuration
        _agent: The underlying Agent instance (created lazily)
    """

    def __init__(
        self, restaurant_lookup_tool: Callable, reservation_call_tool: Callable
    ) -> None:
        """Initialize the reservation agent.

        Args:
            restaurant_lookup_tool: The restaurant lookup function tool
            reservation_call_tool: The reservation call initiation tool
        """
        self.restaurant_lookup_tool = restaurant_lookup_tool
        self.reservation_call_tool = reservation_call_tool
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
            # Load instructions from template with current date/time context
            current_datetime = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
            instructions = load_prompt(
                "reservation_agent", current_datetime=current_datetime
            )

            self._agent = Agent(
                name="Reservation Agent",
                model=self.config.agent_model,
                instructions=instructions,
                tools=[self.restaurant_lookup_tool, self.reservation_call_tool],
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
