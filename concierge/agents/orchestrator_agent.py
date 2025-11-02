"""Orchestrator agent that routes requests to specialized agents using OpenAI Agents SDK."""

import logging
from typing import TYPE_CHECKING

from agents import Agent

from concierge.config import get_config

if TYPE_CHECKING:
    from collections.abc import Sequence

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

    def __init__(self, *specialized_agents: Agent) -> None:
        """Initialize the orchestrator agent.

        Args:
            *specialized_agents: Variable number of specialized agents to route to
        """
        self.specialized_agents: Sequence[Agent] = list(specialized_agents)
        self.config = get_config()
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
            self._agent = Agent(
                name="AI Concierge Orchestrator",
                model=self.config.agent_model,
                instructions="""You are the AI Concierge orchestrator. Your role is to understand user requests
and route them to the appropriate specialized agent.

Current capabilities:
- **Reservation Requests**: For booking/making restaurant reservations
  Examples: "Book a table", "Make a reservation", "Reserve a table"
  → Hand off to the Reservation Agent

Future capabilities (not yet implemented):
- Cancellation requests → Hand off to Cancellation Agent
- Modification requests → Hand off to Modification Agent
- Query requests → Hand off to Query Agent

**Important Instructions:**
1. Analyze the user's request to determine their intent
2. If it's a reservation request, hand off to the Reservation Agent
3. If the request type is not yet supported, politely inform the user
4. Be friendly, professional, and concise
5. Don't try to handle the request yourself - always delegate to specialized agents

When you identify a reservation request, immediately hand off to the Reservation Agent.
Don't ask for details yourself - let the specialized agent handle that.
""",
                handoffs=self.specialized_agents,
            )
            logger.info("Orchestrator agent created successfully")

        return self._agent

    @property
    def agent(self) -> Agent:
        """Get the agent instance (creates it if needed).

        Returns:
            The orchestrator agent
        """
        return self.create()


# Backward compatibility: Factory function that wraps the class
def create_orchestrator_agent(*specialized_agents: Agent) -> Agent:
    """Create the orchestrator agent that routes to specialized agents.

    This is a convenience function for backward compatibility.
    For new code, use OrchestratorAgent class directly.

    Args:
        *specialized_agents: Variable number of specialized agents to route to

    Returns:
        Configured orchestrator agent
    """
    orchestrator = OrchestratorAgent(*specialized_agents)
    return orchestrator.create()


def format_reservation_result(result) -> str:
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
