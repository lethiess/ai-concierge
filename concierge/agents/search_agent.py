"""Restaurant search agent for finding restaurants based on user preferences."""

import logging

from agents import Agent

from concierge.config import get_config
from concierge.prompts import load_prompt

logger = logging.getLogger(__name__)


class SearchAgent:
    """Restaurant search agent for finding restaurants.

    This agent helps users discover restaurants based on their preferences
    using LLM-powered mock search to generate realistic options.

    Attributes:
        search_tool: The search_restaurants_llm tool function
        config: Application configuration
        _agent: The underlying Agent instance (created lazily)
    """

    def __init__(self, search_tool) -> None:
        """Initialize the search agent.

        Args:
            search_tool: The search_restaurants_llm tool function
        """
        self.search_tool = search_tool
        self.config = get_config()
        self._agent: Agent | None = None

        logger.info("SearchAgent initialized")

    def create(self) -> Agent:
        """Create and return the configured search agent.

        Returns:
            Configured search agent with search tools

        Note:
            The agent is created lazily on first call and cached.
        """
        if self._agent is None:
            # Load instructions from template
            instructions = load_prompt("search_agent")

            self._agent = Agent(
                name="Restaurant Search Agent",
                model=self.config.agent_model,
                instructions=instructions,
                tools=[self.search_tool],
            )
            logger.info("Search agent created successfully")

        return self._agent

    @property
    def agent(self) -> Agent:
        """Get the agent instance (creates it if needed).

        Returns:
            The search agent
        """
        return self.create()
