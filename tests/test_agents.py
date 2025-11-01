"""Tests for AI Concierge agents using OpenAI Agents SDK."""

from agents import Agent
from agents.realtime import RealtimeAgent

from concierge.agents import (
    create_orchestrator_agent,
    create_reservation_agent,
    create_voice_agent,
    find_restaurant,
)


class TestAgentCreation:
    """Tests for agent creation using the SDK."""

    def test_create_reservation_agent(self):
        """Test reservation agent creation."""
        reservation_agent = create_reservation_agent(find_restaurant)

        assert isinstance(reservation_agent, Agent)
        assert reservation_agent.name == "Reservation Agent"
        # Has find_restaurant and initiate_reservation_call tools
        assert len(reservation_agent.tools) == 2

    def test_create_orchestrator_agent(self):
        """Test orchestrator agent creation with specialized agents."""
        reservation_agent = create_reservation_agent(find_restaurant)
        orchestrator = create_orchestrator_agent(reservation_agent)

        assert isinstance(orchestrator, Agent)
        assert orchestrator.name == "AI Concierge Orchestrator"
        assert len(orchestrator.handoffs) == 1

    def test_agent_handoff_chain(self):
        """Test the handoff chain: Orchestrator → Reservation Agent."""
        reservation_agent = create_reservation_agent(find_restaurant)
        orchestrator = create_orchestrator_agent(reservation_agent)

        # Verify the handoff chain
        assert reservation_agent in orchestrator.handoffs

    def test_create_voice_agent(self):
        """Test voice agent creation with reservation details."""
        reservation_details = {
            "restaurant_name": "Test Restaurant",
            "restaurant_phone": "+1234567890",
            "party_size": 4,
            "date": "tomorrow",
            "time": "7pm",
            "customer_name": "John Doe",
            "special_requests": "Window seat please",
        }

        voice_agent = create_voice_agent(reservation_details)

        assert isinstance(voice_agent, RealtimeAgent)
        assert voice_agent.name == "Restaurant Reservation Voice Agent"
        assert "Test Restaurant" in voice_agent.instructions

    def test_multiple_specialized_agents(self):
        """Test orchestrator with multiple specialized agents."""
        reservation_agent = create_reservation_agent(find_restaurant)
        # In the future, we might have cancellation_agent, query_agent, etc.
        orchestrator = create_orchestrator_agent(reservation_agent)

        assert len(orchestrator.handoffs) >= 1


class TestTools:
    """Tests for function tools."""

    def test_find_restaurant_success(self):
        """Test finding a restaurant that exists."""
        result = find_restaurant("Demo Restaurant")

        assert result["success"] is True
        assert "restaurant" in result
        assert result["restaurant"]["name"] == "Demo Restaurant"

    def test_find_restaurant_not_found(self):
        """Test finding a restaurant that doesn't exist."""
        result = find_restaurant("Nonexistent Restaurant")

        assert result["success"] is False
        assert "error" in result
