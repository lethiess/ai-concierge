"""Tests for agent modules."""

import pytest
from unittest.mock import patch

from concierge.agents.triage_agent import TriageAgent
from concierge.agents.voice_agent import VoiceAgent
from concierge.models import (
    ReservationRequest,
    ReservationResult,
    ReservationStatus,
    Restaurant,
)


class TestTriageAgent:
    """Tests for the TriageAgent."""

    @pytest.fixture
    def triage_agent(self):
        """Create a triage agent for testing."""
        return TriageAgent()

    def test_parse_request_valid_input(self, triage_agent):
        """Test parsing a valid reservation request."""
        user_input = "Book a table at Demo Restaurant for 4 people tomorrow at 7pm"

        with patch.object(triage_agent, "_parse_request") as mock_parse:
            mock_parse.return_value = {
                "restaurant_name": "Demo Restaurant",
                "party_size": 4,
                "date": "tomorrow",
                "time": "7pm",
            }

            result = triage_agent.process_user_request(user_input)

            assert result["success"] is True
            assert result["request"].restaurant_name == "Demo Restaurant"
            assert result["request"].party_size == 4

    def test_invalid_input_empty(self, triage_agent):
        """Test handling of empty input."""
        result = triage_agent.process_user_request("")
        assert result["success"] is False
        assert "empty" in result["error"].lower()

    def test_invalid_party_size(self, triage_agent):
        """Test handling of invalid party size."""
        user_input = "Book a table for 100 people"

        with patch.object(triage_agent, "_parse_request") as mock_parse:
            mock_parse.return_value = {
                "restaurant_name": "Demo Restaurant",
                "party_size": 100,  # Exceeds maximum
                "date": "tomorrow",
                "time": "7pm",
            }

            result = triage_agent.process_user_request(user_input)

            assert result["success"] is False
            assert "party size" in result["error"].lower()

    def test_format_result_confirmed(self, triage_agent):
        """Test formatting a confirmed reservation result."""
        restaurant = Restaurant(
            name="Test Restaurant",
            phone_number="+1234567890",
        )

        request = ReservationRequest(
            restaurant_name="Test Restaurant",
            party_size=4,
            date="2024-12-01",
            time="7:00 PM",
        )

        result = ReservationResult(
            status=ReservationStatus.CONFIRMED,
            restaurant=restaurant,
            request=request,
            confirmation_number="TEST123",
            message="Reservation confirmed",
        )

        formatted = triage_agent.format_result(result)

        assert "CONFIRMED" in formatted
        assert "Test Restaurant" in formatted
        assert "TEST123" in formatted


class TestVoiceAgent:
    """Tests for the VoiceAgent."""

    @pytest.fixture
    def voice_agent(self):
        """Create a voice agent for testing."""
        return VoiceAgent()

    @pytest.mark.asyncio
    async def test_simulate_call(self, voice_agent):
        """Test simulated call when Twilio is not configured."""
        restaurant = Restaurant(
            name="Test Restaurant",
            phone_number="+1234567890",
        )

        request = ReservationRequest(
            restaurant_name="Test Restaurant",
            party_size=4,
            date="2024-12-01",
            time="7:00 PM",
        )

        # Mock Twilio as not configured
        voice_agent.twilio_service.client = None

        result = await voice_agent.make_reservation_call(request, restaurant)

        assert result.status == ReservationStatus.CONFIRMED
        assert "SIMULATED" in result.message
        assert result.confirmation_number is not None

    def test_build_system_prompt(self, voice_agent):
        """Test system prompt generation."""
        restaurant = Restaurant(
            name="Test Restaurant",
            phone_number="+1234567890",
        )

        request = ReservationRequest(
            restaurant_name="Test Restaurant",
            party_size=4,
            date="2024-12-01",
            time="7:00 PM",
            user_name="John Doe",
        )

        prompt = voice_agent._build_system_prompt(request, restaurant)

        assert "Test Restaurant" in prompt
        assert "4 people" in prompt
        assert "2024-12-01" in prompt
        assert "7:00 PM" in prompt
        assert "John Doe" in prompt
