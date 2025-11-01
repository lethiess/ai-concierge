"""Tests for call state management."""

import pytest

from concierge.services.call_manager import CallManager, CallState, get_call_manager


class TestCallState:
    """Test CallState model."""

    def test_create_call_state(self):
        """Test creating a CallState."""
        call_state = CallState(
            call_id="test-123",
            reservation_details={"restaurant_name": "Test Restaurant"},
        )

        assert call_state.call_id == "test-123"
        assert call_state.status == "initiated"
        assert call_state.transcript == []
        assert call_state.confirmation_number is None
        assert call_state.start_time is not None
        assert call_state.end_time is None


class TestCallManager:
    """Test CallManager functionality."""

    @pytest.fixture
    def call_manager(self):
        """Create a fresh CallManager for each test."""
        # Clear any existing calls
        manager = CallManager()
        manager._active_calls.clear()
        return manager

    def test_generate_call_id(self, call_manager):
        """Test call ID generation."""
        call_id = call_manager.generate_call_id()

        assert isinstance(call_id, str)
        assert len(call_id) > 0

        # Should be unique
        call_id2 = call_manager.generate_call_id()
        assert call_id != call_id2

    def test_create_call(self, call_manager):
        """Test creating a new call."""
        reservation_details = {
            "restaurant_name": "Test Restaurant",
            "party_size": 4,
            "date": "tomorrow",
            "time": "7pm",
        }

        call_state = call_manager.create_call(reservation_details)

        assert call_state.call_id is not None
        assert call_state.status == "initiated"
        assert call_state.reservation_details == reservation_details

        # Should be retrievable
        retrieved = call_manager.get_call(call_state.call_id)
        assert retrieved is not None
        assert retrieved.call_id == call_state.call_id

    def test_create_call_with_id(self, call_manager):
        """Test creating a call with specific ID."""
        call_id = "custom-123"
        call_state = call_manager.create_call({"test": "data"}, call_id=call_id)

        assert call_state.call_id == call_id

    def test_get_call_not_found(self, call_manager):
        """Test getting non-existent call."""
        result = call_manager.get_call("nonexistent")
        assert result is None

    def test_update_status(self, call_manager):
        """Test updating call status."""
        call_state = call_manager.create_call({"test": "data"})

        call_manager.update_status(call_state.call_id, "in_progress")
        assert call_state.status == "in_progress"

        call_manager.update_status(call_state.call_id, "completed")
        assert call_state.status == "completed"
        assert call_state.end_time is not None

    def test_set_call_sid(self, call_manager):
        """Test setting Twilio call SID."""
        call_state = call_manager.create_call({"test": "data"})

        call_manager.set_call_sid(call_state.call_id, "CA123456")
        assert call_state.call_sid == "CA123456"

    def test_append_transcript(self, call_manager):
        """Test appending to transcript."""
        call_state = call_manager.create_call({"test": "data"})

        call_manager.append_transcript(call_state.call_id, "Hello")
        call_manager.append_transcript(call_state.call_id, "World")

        assert len(call_state.transcript) == 2
        assert call_state.transcript[0] == "Hello"
        assert call_state.transcript[1] == "World"

    def test_set_error(self, call_manager):
        """Test setting error message."""
        call_state = call_manager.create_call({"test": "data"})

        call_manager.set_error(call_state.call_id, "Test error")

        assert call_state.status == "failed"
        assert call_state.error_message == "Test error"
        assert call_state.end_time is not None

    def test_extract_confirmation_pattern1(self, call_manager):
        """Test extracting confirmation number - pattern 1."""
        call_state = call_manager.create_call({"test": "data"})

        call_manager.append_transcript(
            call_state.call_id, "Your confirmation number is ABC123"
        )

        confirmation = call_manager.extract_confirmation(call_state.call_id)
        assert confirmation == "ABC123"

    def test_extract_confirmation_pattern2(self, call_manager):
        """Test extracting confirmation number - pattern 2."""
        call_state = call_manager.create_call({"test": "data"})

        call_manager.append_transcript(call_state.call_id, "Your reservation is XYZ789")

        confirmation = call_manager.extract_confirmation(call_state.call_id)
        assert confirmation == "XYZ789"

    def test_extract_confirmation_pattern3(self, call_manager):
        """Test extracting confirmation number - pattern 3."""
        call_state = call_manager.create_call({"test": "data"})

        call_manager.append_transcript(call_state.call_id, "Reference number: DEF456")

        confirmation = call_manager.extract_confirmation(call_state.call_id)
        assert confirmation == "DEF456"

    def test_extract_confirmation_pattern4(self, call_manager):
        """Test extracting confirmation number - pattern 4 (standalone)."""
        call_state = call_manager.create_call({"test": "data"})

        call_manager.append_transcript(
            call_state.call_id, "Please write this down: ABC1234"
        )

        confirmation = call_manager.extract_confirmation(call_state.call_id)
        assert confirmation == "ABC1234"

    def test_extract_confirmation_not_found(self, call_manager):
        """Test when no confirmation number present."""
        call_state = call_manager.create_call({"test": "data"})

        call_manager.append_transcript(call_state.call_id, "Sorry, we're fully booked")

        confirmation = call_manager.extract_confirmation(call_state.call_id)
        assert confirmation is None

    def test_extract_confirmation_auto_update(self, call_manager):
        """Test that confirmation is auto-extracted on transcript append."""
        call_state = call_manager.create_call({"test": "data"})

        # Should auto-extract
        call_manager.append_transcript(
            call_state.call_id, "Confirmation number is AUTO123"
        )

        assert call_state.confirmation_number == "AUTO123"

    def test_get_all_calls(self, call_manager):
        """Test getting all calls."""
        call_manager.create_call({"test": "data1"})
        call_manager.create_call({"test": "data2"})
        call_manager.create_call({"test": "data3"})

        all_calls = call_manager.get_all_calls()

        assert len(all_calls) == 3

    def test_cleanup_old_calls(self, call_manager):
        """Test cleanup of old calls."""
        # Create calls
        call1 = call_manager.create_call({"test": "data1"})
        call2 = call_manager.create_call({"test": "data2"})

        # Mark as completed
        call_manager.update_status(call1.call_id, "completed")
        call_manager.update_status(call2.call_id, "failed")

        # Manually set end_time to the past (older than 60 minutes)
        from datetime import datetime, timedelta

        call1.end_time = datetime.now() - timedelta(minutes=120)
        call2.end_time = datetime.now() - timedelta(minutes=30)

        # Cleanup calls older than 60 minutes
        removed = call_manager.cleanup_old_calls(max_age_minutes=60)

        assert removed == 1  # Only call1 should be removed
        assert call_manager.get_call(call1.call_id) is None
        assert call_manager.get_call(call2.call_id) is not None


class TestCallManagerSingleton:
    """Test CallManager singleton behavior."""

    def test_singleton(self):
        """Test that get_call_manager returns same instance."""
        manager1 = get_call_manager()
        manager2 = get_call_manager()

        assert manager1 is manager2

    def test_shared_state(self):
        """Test that instances share state."""
        manager1 = get_call_manager()
        manager2 = get_call_manager()

        # Clear for test
        manager1._active_calls.clear()

        # Create call in manager1
        call1 = manager1.create_call({"test": "shared"})

        # Should be visible in manager2
        call2 = manager2.get_call(call1.call_id)
        assert call2 is not None
        assert call2.call_id == call1.call_id
