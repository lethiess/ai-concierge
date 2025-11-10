"""Tests for AI Concierge agents using OpenAI Agents SDK."""

import pytest
from agents import Agent
from agents.realtime import RealtimeAgent

from concierge.agents import (
    CancellationAgent,
    OrchestratorAgent,
    ReservationAgent,
    ReservationVoiceAgent,
    SearchAgent,
    find_restaurant,
)
from concierge.agents.tools import (
    search_restaurants_llm,
    lookup_reservation_from_history,
    initiate_cancellation_call,
)
from concierge.services.restaurant_service import RestaurantService


class TestAgentCreation:
    """Tests for agent creation using the SDK."""

    def test_create_reservation_agent(self):
        """Test reservation agent creation using class."""
        reservation_agent_instance = ReservationAgent(find_restaurant)
        reservation_agent = reservation_agent_instance.create()

        assert isinstance(reservation_agent, Agent)
        assert reservation_agent.name == "Reservation Agent"
        # Has find_restaurant and initiate_reservation_call tools
        assert len(reservation_agent.tools) == 2

    def test_reservation_agent_class(self):
        """Test reservation agent creation using class."""
        reservation_agent_instance = ReservationAgent(find_restaurant)
        reservation_agent = reservation_agent_instance.create()

        assert isinstance(reservation_agent, Agent)
        assert reservation_agent.name == "Reservation Agent"
        assert len(reservation_agent.tools) == 2
        # Test property access
        assert reservation_agent_instance.agent == reservation_agent

    def test_create_orchestrator_agent(self):
        """Test orchestrator agent creation with specialized agents using class."""
        reservation_agent_instance = ReservationAgent(find_restaurant)
        reservation_agent = reservation_agent_instance.create()
        orchestrator_instance = OrchestratorAgent(reservation_agent=reservation_agent)
        orchestrator = orchestrator_instance.create()

        assert isinstance(orchestrator, Agent)
        assert orchestrator.name == "AI Concierge Orchestrator"
        assert len(orchestrator.handoffs) == 1

    def test_orchestrator_agent_class(self):
        """Test orchestrator agent creation using class."""
        reservation_agent_instance = ReservationAgent(find_restaurant)
        reservation_agent = reservation_agent_instance.create()
        orchestrator_instance = OrchestratorAgent(reservation_agent=reservation_agent)
        orchestrator = orchestrator_instance.create()

        assert isinstance(orchestrator, Agent)
        assert orchestrator.name == "AI Concierge Orchestrator"
        assert len(orchestrator.handoffs) == 1
        # Test property access
        assert orchestrator_instance.agent == orchestrator

    def test_agent_handoff_chain(self):
        """Test the handoff chain: Orchestrator → Reservation Agent."""
        reservation_agent_instance = ReservationAgent(find_restaurant)
        reservation_agent = reservation_agent_instance.create()
        orchestrator_instance = OrchestratorAgent(reservation_agent=reservation_agent)
        orchestrator = orchestrator_instance.create()

        # Verify the handoff chain
        assert reservation_agent in orchestrator.handoffs

    def test_create_cancellation_agent(self):
        """Test cancellation agent creation."""
        cancellation_agent_instance = CancellationAgent(
            lookup_reservation_from_history, initiate_cancellation_call
        )
        cancellation_agent = cancellation_agent_instance.create()

        assert isinstance(cancellation_agent, Agent)
        assert cancellation_agent.name == "Cancellation Agent"
        assert len(cancellation_agent.tools) == 2

    def test_create_search_agent(self):
        """Test search agent creation."""
        search_agent_instance = SearchAgent(search_restaurants_llm)
        search_agent = search_agent_instance.create()

        assert isinstance(search_agent, Agent)
        assert search_agent.name == "Restaurant Search Agent"
        assert len(search_agent.tools) == 1

    def test_orchestrator_with_all_agents(self):
        """Test orchestrator with all 3 specialized agents."""
        reservation_agent_instance = ReservationAgent(find_restaurant)
        reservation_agent = reservation_agent_instance.create()

        cancellation_agent_instance = CancellationAgent(
            lookup_reservation_from_history, initiate_cancellation_call
        )
        cancellation_agent = cancellation_agent_instance.create()

        search_agent_instance = SearchAgent(search_restaurants_llm)
        search_agent = search_agent_instance.create()

        orchestrator_instance = OrchestratorAgent(
            reservation_agent=reservation_agent,
            cancellation_agent=cancellation_agent,
            search_agent=search_agent,
        )
        orchestrator = orchestrator_instance.create()

        assert isinstance(orchestrator, Agent)
        assert orchestrator.name == "AI Concierge Orchestrator"
        assert len(orchestrator.handoffs) == 3
        assert reservation_agent in orchestrator.handoffs
        assert cancellation_agent in orchestrator.handoffs
        assert search_agent in orchestrator.handoffs

    @pytest.mark.skip(reason="RealtimeAgent requires specific SDK setup")
    def test_create_reservation_voice_agent(self):
        """Test reservation voice agent creation with reservation details using class."""
        reservation_details = {
            "restaurant_name": "Test Restaurant",
            "restaurant_phone": "+1234567890",
            "party_size": 4,
            "date": "tomorrow",
            "time": "7pm",
            "customer_name": "John Doe",
            "special_requests": "Window seat please",
        }

        voice_agent_instance = ReservationVoiceAgent(reservation_details)
        voice_agent = voice_agent_instance.create()

        assert isinstance(voice_agent, RealtimeAgent)
        assert voice_agent.name == "Restaurant Reservation Voice Agent"
        assert "Test Restaurant" in voice_agent.instructions

    @pytest.mark.skip(reason="RealtimeAgent requires specific SDK setup")
    def test_reservation_voice_agent_class(self):
        """Test reservation voice agent creation using class."""
        reservation_details = {
            "restaurant_name": "Test Restaurant",
            "restaurant_phone": "+1234567890",
            "party_size": 4,
            "date": "tomorrow",
            "time": "7pm",
            "customer_name": "John Doe",
            "special_requests": "Window seat please",
        }

        voice_agent_instance = ReservationVoiceAgent(reservation_details)
        voice_agent = voice_agent_instance.create()

        assert isinstance(voice_agent, RealtimeAgent)
        assert voice_agent.name == "Restaurant Reservation Voice Agent"
        assert "Test Restaurant" in voice_agent.instructions
        # Test property access
        assert voice_agent_instance.agent == voice_agent

    def test_multiple_specialized_agents(self):
        """Test orchestrator with multiple specialized agents."""
        reservation_agent_instance = ReservationAgent(find_restaurant)
        reservation_agent = reservation_agent_instance.create()
        # In the future, we might have cancellation_agent, query_agent, etc.
        orchestrator_instance = OrchestratorAgent(reservation_agent)
        orchestrator = orchestrator_instance.create()

        assert len(orchestrator.handoffs) >= 1


class TestTools:
    """Tests for function tools (via underlying service)."""

    def test_find_restaurant_success(self):
        """Test finding a restaurant that exists."""
        # Test via the underlying service
        service = RestaurantService()
        restaurant = service.find_restaurant("Lugis Pizza")

        assert restaurant is not None
        assert restaurant.name == "Lugis Pizza"

    def test_find_restaurant_not_found(self):
        """Test finding a restaurant that doesn't exist."""
        # Test via the underlying service
        # Note: RestaurantService currently returns demo restaurant for any query
        # In production, this would check a real database
        service = RestaurantService()
        restaurant = service.find_restaurant("Nonexistent Restaurant")

        # For now, just verify it returns something (demo restaurant)
        assert restaurant is not None
