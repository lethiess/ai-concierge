"""Orchestrator agent that routes requests to specialized agents using OpenAI Agents SDK."""

import logging
from typing import TYPE_CHECKING

from agents import Agent

from concierge.config import get_config
from concierge.agents.prompts import load_prompt

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Orchestrator agent that routes requests to specialized agents.

    This is the main entry point for all user requests. It analyzes the intent
    and routes to the appropriate specialized agent.

    Attributes:
        specialized_agents: List of specialized agents to route to
        config: Application configuration
        _agent: The underlying Agent instance (created lazily)
    """

    def __init__(
        self,
        reservation_agent: Agent,
        cancellation_agent: Agent,
        search_agent: Agent,
        input_guardrails: list | None = None,
        output_guardrails: list | None = None,
    ) -> None:
        """Initialize the orchestrator agent.

        Args:
            reservation_agent: Agent for handling reservation requests (required)
            cancellation_agent: Agent for handling cancellations (required)
            search_agent: Agent for restaurant search (required)
            input_guardrails: List of input guardrails to apply (optional)
            output_guardrails: List of output guardrails to apply (optional)
        """
        # Build list of specialized agents
        self.specialized_agents: list[Agent] = [
            reservation_agent,
            cancellation_agent,
            search_agent,
        ]

        self.config = get_config()
        self.input_guardrails = input_guardrails or []
        self.output_guardrails = output_guardrails or []
        self._agent: Agent | None = None

        logger.info(
            "OrchestratorAgent initialized with %d specialized agents",
            len(self.specialized_agents),
        )

    def create(self) -> Agent:
        """Create and return the configured orchestrator agent.

        Returns:
            Configured orchestrator agent

        Note:
            The agent is created lazily on first call and cached.
        """
        if self._agent is None:
            # Load instructions from template
            instructions = load_prompt("orchestrator_agent")

            self._agent = Agent(
                name="AI Concierge Orchestrator",
                model=self.config.agent_model,
                instructions=instructions,
                handoffs=self.specialized_agents,
                input_guardrails=self.input_guardrails,
                output_guardrails=self.output_guardrails,
            )
            logger.info("Orchestrator agent created successfully")
            logger.info(
                f"  with {len(self.input_guardrails)} input guardrails and {len(self.output_guardrails)} output guardrails"
            )

        return self._agent

    @property
    def agent(self) -> Agent:
        """Get the agent instance (creates it if needed).

        Returns:
            The orchestrator agent
        """
        return self.create()
