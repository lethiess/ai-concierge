"""Tests for AI Concierge agents using OpenAI Agents SDK."""

from agents import Agent

from concierge.agents import (
    create_orchestrator_agent,
    create_reservation_agent,
    create_voice_agent,
    end_call,
    find_restaurant,
    get_call_status,
    make_call,
)


class TestAgentCreation:
    """Tests for agent creation using the SDK."""

    def test_create_voice_agent(self):
        """Test voice agent creation."""
        voice_agent = create_voice_agent(make_call, get_call_status, end_call)

        assert isinstance(voice_agent, Agent)
        assert voice_agent.name == "Voice Reservation Agent"
        assert len(voice_agent.tools) == 3

    def test_create_reservation_agent(self):
        """Test reservation agent creation with handoff to voice agent."""
        voice_agent = create_voice_agent(make_call, get_call_status, end_call)
        reservation_agent = create_reservation_agent(voice_agent, find_restaurant)

        assert isinstance(reservation_agent, Agent)
        assert reservation_agent.name == "Reservation Agent"
        assert len(reservation_agent.handoffs) == 1
        assert len(reservation_agent.tools) == 1

    def test_create_orchestrator_agent(self):
        """Test orchestrator agent creation with specialized agents."""
        voice_agent = create_voice_agent(make_call, get_call_status, end_call)
        reservation_agent = create_reservation_agent(voice_agent, find_restaurant)
        orchestrator = create_orchestrator_agent(reservation_agent)

        assert isinstance(orchestrator, Agent)
        assert orchestrator.name == "AI Concierge Orchestrator"
        assert len(orchestrator.handoffs) == 1

    def test_agent_handoff_chain(self):
        """Test the full agent handoff chain: Orchestrator → Reservation → Voice."""
        voice_agent = create_voice_agent(make_call, get_call_status, end_call)
        reservation_agent = create_reservation_agent(voice_agent, find_restaurant)
        orchestrator = create_orchestrator_agent(reservation_agent)

        # Verify the handoff chain
        assert reservation_agent in orchestrator.handoffs
        assert voice_agent in reservation_agent.handoffs

    def test_multiple_specialized_agents(self):
        """Test orchestrator with multiple specialized agents."""
        voice_agent = create_voice_agent(make_call, get_call_status, end_call)
        reservation_agent = create_reservation_agent(voice_agent, find_restaurant)
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

    def test_make_call_simulated(self):
        """Test making a call when Twilio is not configured."""
        result = make_call(
            phone_number="+1234567890",
            restaurant_name="Test Restaurant",
            party_size=4,
            date="tomorrow",
            time="7pm",
        )

        assert result["success"] is True
        assert "call_sid" in result

    def test_get_call_status_simulated(self):
        """Test getting call status for simulated call."""
        result = get_call_status("SIMULATED")

        assert result["success"] is True
        assert result["status"] == "completed"

    def test_end_call_simulated(self):
        """Test ending a simulated call."""
        result = end_call("SIMULATED")

        assert result["success"] is True
