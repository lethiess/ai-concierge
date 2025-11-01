"""Tests for data models."""

import pytest
from pydantic import ValidationError

from concierge.models import (
    ReservationRequest,
    ReservationResult,
    ReservationStatus,
    Restaurant,
)


class TestRestaurant:
    """Tests for the Restaurant model."""

    def test_create_restaurant(self):
        """Test creating a restaurant."""
        restaurant = Restaurant(
            name="Test Restaurant",
            phone_number="+1234567890",
            address="123 Test St",
            cuisine_type="Italian",
        )

        assert restaurant.name == "Test Restaurant"
        assert restaurant.phone_number == "+1234567890"
        assert restaurant.address == "123 Test St"
        assert restaurant.cuisine_type == "Italian"

    def test_restaurant_immutable(self):
        """Test that restaurant is frozen/immutable."""
        restaurant = Restaurant(
            name="Test Restaurant",
            phone_number="+1234567890",
        )

        with pytest.raises((ValidationError, AttributeError)):
            restaurant.name = "New Name"


class TestReservationRequest:
    """Tests for the ReservationRequest model."""

    def test_create_reservation_request(self):
        """Test creating a reservation request."""
        request = ReservationRequest(
            restaurant_name="Test Restaurant",
            party_size=4,
            date="2024-12-01",
            time="7:00 PM",
        )

        assert request.restaurant_name == "Test Restaurant"
        assert request.party_size == 4
        assert request.date == "2024-12-01"
        assert request.time == "7:00 PM"

    def test_reservation_request_with_optional_fields(self):
        """Test creating a request with optional fields."""
        request = ReservationRequest(
            restaurant_name="Test Restaurant",
            party_size=4,
            date="2024-12-01",
            time="7:00 PM",
            user_name="John Doe",
            user_phone="+1234567890",
            special_requests="Window seat please",
        )

        assert request.user_name == "John Doe"
        assert request.user_phone == "+1234567890"
        assert request.special_requests == "Window seat please"

    def test_invalid_party_size(self):
        """Test that invalid party size raises validation error."""
        with pytest.raises(ValidationError):
            ReservationRequest(
                restaurant_name="Test Restaurant",
                party_size=0,  # Invalid: must be > 0
                date="2024-12-01",
                time="7:00 PM",
            )


class TestReservationResult:
    """Tests for the ReservationResult model."""

    def test_create_reservation_result(self):
        """Test creating a reservation result."""
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
            message="Reservation confirmed",
            confirmation_number="ABC123",
            call_duration=45.5,
        )

        assert result.status == ReservationStatus.CONFIRMED
        assert result.confirmation_number == "ABC123"
        assert result.call_duration == 45.5
        assert result.timestamp is not None


class TestReservationStatus:
    """Tests for the ReservationStatus enum."""

    def test_status_values(self):
        """Test that all expected status values exist."""
        assert ReservationStatus.PENDING == "pending"
        assert ReservationStatus.CONFIRMED == "confirmed"
        assert ReservationStatus.REJECTED == "rejected"
        assert ReservationStatus.ERROR == "error"
