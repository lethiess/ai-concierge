"""Orchestrator agent that routes requests to specialized agents using OpenAI Agents SDK."""

import logging
from typing import TYPE_CHECKING

from agents import Agent

from concierge.config import get_config
from concierge.prompts import load_prompt

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
            # Load instructions from template
            instructions = load_prompt("orchestrator_agent")

            self._agent = Agent(
                name="AI Concierge Orchestrator",
                model=self.config.agent_model,
                instructions=instructions,
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


def format_reservation_result(result) -> str:
    """Format a reservation result for display to the user.

    Args:
        result: The reservation result from the agent run

    Returns:
        Formatted string for display
    """
    import json
    from concierge.services.call_manager import get_call_manager

    output = []

    output.append("=" * 60)
    output.append("RESERVATION RESULT")
    output.append("=" * 60)

    # Extract structured call information from tool calls
    from logging import getLogger

    logger = getLogger(__name__)

    call_result = None
    call_id = None

    # Try method 1: Extract from result.messages (if available)
    if hasattr(result, "messages"):
        logger.info(f"📋 Checking {len(result.messages)} messages for tool results")
        for i, msg in enumerate(result.messages):
            logger.info(
                f"  Message {i}: role={getattr(msg, 'role', 'unknown')}, type={type(msg).__name__}"
            )
            # Check for tool results
            if hasattr(msg, "role") and msg.role == "tool":
                if hasattr(msg, "content") and msg.content:
                    logger.info(f"  ✓ Found tool result: {msg.content[:200]}")
                    try:
                        call_result = (
                            json.loads(msg.content)
                            if isinstance(msg.content, str)
                            else msg.content
                        )
                        logger.info(
                            f"  Parsed tool result keys: {call_result.keys() if isinstance(call_result, dict) else 'not a dict'}"
                        )
                        if isinstance(call_result, dict) and "call_id" in call_result:
                            call_id = call_result["call_id"]
                            logger.info(
                                f"✓ Extracted call_id from tool result: {call_id}"
                            )
                            break
                        logger.warning(
                            f"⚠ Tool result is dict but no call_id: {call_result}"
                        )
                    except (json.JSONDecodeError, AttributeError) as e:
                        logger.exception(f"  ✗ Error parsing tool result: {e}")
    else:
        logger.warning("⚠ Result has no messages attribute - trying alternative method")

        # Method 2: Get the most recent completed call from CallManager
        call_manager = get_call_manager()
        all_calls = call_manager.get_all_calls()

        # Find the most recently completed call
        completed_calls = [c for c in all_calls if c.status == "completed"]
        if completed_calls:
            # Sort by end_time (most recent first)
            completed_calls.sort(
                key=lambda c: c.end_time if c.end_time else c.start_time, reverse=True
            )
            most_recent_call = completed_calls[0]
            call_id = most_recent_call.call_id
            logger.info(f"✓ Using most recent completed call: {call_id}")

    # If we have a call_id, get the actual call state from CallManager
    restaurant_name = None
    party_size = None
    confirmed_date = None
    confirmed_time = None
    confirmation_number = None
    status = "pending"
    call_duration = None

    if call_id:
        call_manager = get_call_manager()
        call_state = call_manager.get_call(call_id)
        if call_state:
            # Get basic reservation details
            restaurant_name = call_state.reservation_details.get("restaurant_name")
            party_size = call_state.reservation_details.get("party_size")

            # Get the actual confirmation details
            confirmation_number = call_state.confirmation_number
            status = call_state.status

            if call_state.start_time and call_state.end_time:
                duration = (call_state.end_time - call_state.start_time).total_seconds()
                call_duration = duration

            # Get the confirmed time from LLM analysis (stored in reservation_details)
            # If different from original, use that; otherwise fall back to original
            confirmed_time = call_state.reservation_details.get("confirmed_time")
            if confirmed_time:
                from logging import getLogger

                logger = getLogger(__name__)
                logger.info(f"✓ Using LLM-extracted confirmed time: {confirmed_time}")
            else:
                # Fall back to original requested time
                confirmed_time = call_state.reservation_details.get("time", "")

            # Get the confirmed date from LLM analysis if available
            confirmed_date = call_state.reservation_details.get("confirmed_date")
            if not confirmed_date:
                confirmed_date = call_state.reservation_details.get("date", "")

    # Build the output message
    if restaurant_name:
        # Format the time nicely
        time_display = confirmed_time
        if confirmed_time:
            try:
                # Convert 24h to 12h format if needed
                if ":" in confirmed_time:
                    hour, minute = confirmed_time.split(":")
                    hour = int(hour)
                    minute = int(minute) if minute else 0
                    period = "PM" if hour >= 12 else "AM"
                    display_hour = hour if hour <= 12 else hour - 12
                    if display_hour == 0:
                        display_hour = 12
                    time_display = f"{display_hour}:{minute:02d} {period}"
            except:
                pass

        date_display = confirmed_date if confirmed_date else "tomorrow"

        output.append(f"\n✓ Restaurant: {restaurant_name}")
        output.append(f"✓ Party Size: {party_size} people")
        output.append(f"✓ Date: {date_display}")
        output.append(f"✓ Time: {time_display}")

        if confirmation_number:
            output.append(f"✓ Confirmation Number: {confirmation_number}")
        else:
            output.append("⚠ Confirmation Number: Not received")

        if status == "completed" and confirmation_number:
            output.append("\n✓ Reservation confirmed! Enjoy your meal!")
        elif status == "completed":
            output.append(
                "\n⚠ Call completed but no confirmation received. Please verify with restaurant."
            )
        else:
            output.append(f"\n⚠ Status: {status.title()}")

        if call_duration:
            output.append(f"\n⏱ Call Duration: {call_duration:.1f}s")
    # Fallback to the agent's final output if no structured data
    elif hasattr(result, "final_output"):
        output.append(f"\n{result.final_output}")

    output.append("\n" + "=" * 60)

    return "\n".join(output)
