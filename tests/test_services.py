"""Tests for service modules."""

import pytest

from concierge.services.restaurant_service import RestaurantService
from concierge.services.twilio_service import TwilioService


class TestRestaurantService:
    """Tests for the RestaurantService."""

    @pytest.fixture
    def restaurant_service(self):
        """Create a restaurant service for testing."""
        return RestaurantService()

    def test_find_restaurant_returns_demo(self, restaurant_service):
        """Test that find_restaurant returns the demo restaurant."""
        result = restaurant_service.find_restaurant("Any Restaurant")

        assert result is not None
        assert result.name == restaurant_service.demo_restaurant.name
        assert result.phone_number == restaurant_service.demo_restaurant.phone_number

    def test_get_demo_restaurant(self, restaurant_service):
        """Test get_demo_restaurant method."""
        result = restaurant_service.get_demo_restaurant()

        assert result is not None
        assert result.name is not None
        assert result.phone_number is not None


class TestTwilioService:
    """Tests for the TwilioService."""

    @pytest.fixture
    def twilio_service(self):
        """Create a Twilio service for testing."""
        return TwilioService()

    def test_is_configured(self, twilio_service):
        """Test configuration check."""
        # Will depend on environment variables
        result = twilio_service.is_configured()
        assert isinstance(result, bool)

    def test_initiate_call_not_configured(self, twilio_service):
        """Test call initiation when not configured."""
        # Force not configured
        twilio_service.client = None

        with pytest.raises(ValueError, match="not configured"):
            twilio_service.initiate_call("+1234567890")

    def test_get_call_status_not_configured(self, twilio_service):
        """Test get call status when not configured."""
        # Force not configured
        twilio_service.client = None

        with pytest.raises(ValueError, match="not configured"):
            twilio_service.get_call_status("test_sid")
