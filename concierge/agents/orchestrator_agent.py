"""Orchestrator agent that routes requests to specialized agents using OpenAI Agents SDK."""

import logging

from agents import Agent

from concierge.config import get_config

logger = logging.getLogger(__name__)


def create_orchestrator_agent(*specialized_agents: Agent) -> Agent:
    """Create the orchestrator agent that routes to specialized agents.

    This is the main entry point for all user requests. It analyzes the intent
    and routes to the appropriate specialized agent.

    Args:
        *specialized_agents: Variable number of specialized agents to route to

    Returns:
        Configured orchestrator agent
    """
    config = get_config()

    orchestrator_agent = Agent(
        name="AI Concierge Orchestrator",
        model=config.agent_model,
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
        handoffs=list(specialized_agents),
    )

    logger.info(
        "Orchestrator agent created with %d specialized agents", len(specialized_agents)
    )
    return orchestrator_agent


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
