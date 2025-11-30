"""Generic voice agent for making real-time calls using OpenAI Realtime API."""

import logging
from datetime import datetime
from typing import Any

from agents.realtime import RealtimeAgent

from concierge.agents.prompts import load_prompt

logger = logging.getLogger(__name__)


class VoiceAgent:
    """Generic voice agent for making real-time calls.

    This agent uses OpenAI's Realtime API for full-duplex audio conversations,
    enabling natural phone calls via Twilio Media Streams.

    Attributes:
        template_name: Name of the prompt template to use
        context: Dictionary containing context for the prompt
        _agent: The underlying RealtimeAgent instance (created lazily)
    """

    def __init__(self, template_name: str, context: dict[str, Any]) -> None:
        """Initialize the voice agent.

        Args:
            template_name: Name of the prompt template to use
            context: Dictionary containing context for the prompt
        """
        self.template_name = template_name
        self.context = context
        self._agent: RealtimeAgent | None = None

        logger.info(
            "VoiceAgent initialized with template '%s' for %s",
            template_name,
            context.get("restaurant_name", "unknown restaurant"),
        )

    def create(self) -> RealtimeAgent:
        """Create and return the configured RealtimeAgent.

        Returns:
            Configured RealtimeAgent for conducting the call
        """
        if self._agent is None:
            # Add current date to context if not present
            if "current_date" not in self.context:
                self.context["current_date"] = datetime.now().strftime("%A, %B %d, %Y")

            # Load and format prompt from template
            instructions = load_prompt(self.template_name, **self.context)

            # Determine agent name based on template
            agent_name = "Voice Agent"
            if "reservation" in self.template_name:
                agent_name = "Restaurant Reservation Voice Agent"
            elif "cancellation" in self.template_name:
                agent_name = "Restaurant Cancellation Voice Agent"

            # Create the RealtimeAgent
            self._agent = RealtimeAgent(
                name=agent_name,
                instructions=instructions,
            )

            logger.info("✅ VoiceAgent created: %s", agent_name)

        return self._agent

    @property
    def agent(self) -> RealtimeAgent:
        """Get the agent instance (creates it if needed).

        Returns:
            The voice agent
        """
        return self.create()
