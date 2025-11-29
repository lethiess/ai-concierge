"""Cancellation agent for handling reservation cancellations."""

import logging

from agents import Agent

from concierge.config import get_config
from concierge.agents.prompts import load_prompt

logger = logging.getLogger(__name__)


class CancellationAgent:
    """Cancellation agent for handling reservation cancellations.

    This agent helps users cancel their reservations by searching conversation
    history and making voice calls to restaurants.

    Attributes:
        lookup_tool: The lookup_reservation_from_history tool function
        cancel_tool: The initiate_cancellation_call tool function
        config: Application configuration
        _agent: The underlying Agent instance (created lazily)
    """

    def __init__(self, lookup_tool, cancel_tool) -> None:
        """Initialize the cancellation agent.

        Args:
            lookup_tool: The lookup_reservation_from_history tool function
            cancel_tool: The initiate_cancellation_call tool function
        """
        self.lookup_tool = lookup_tool
        self.cancel_tool = cancel_tool
        self.config = get_config()
        self._agent: Agent | None = None

        logger.info("CancellationAgent initialized")

    def create(self) -> Agent:
        """Create and return the configured cancellation agent.

        Returns:
            Configured cancellation agent with lookup and cancellation tools

        Note:
            The agent is created lazily on first call and cached.
        """
        if self._agent is None:
            # Load instructions from template
            instructions = load_prompt("cancellation_agent")

            self._agent = Agent(
                name="Cancellation Agent",
                model=self.config.agent_model,
                instructions=instructions,
                tools=[self.lookup_tool, self.cancel_tool],
            )
            logger.info("Cancellation agent created successfully")

        return self._agent

    @property
    def agent(self) -> Agent:
        """Get the agent instance (creates it if needed).

        Returns:
            The cancellation agent
        """
        return self.create()
