"""Tests for SQLiteSession conversation memory functionality."""

import pytest
from agents import SQLiteSession


class TestSessionMemory:
    """Test suite for session memory functionality."""

    def test_create_session(self):
        """Test creating a session instance."""
        session = SQLiteSession("test_session_001", ":memory:")
        assert session is not None
        assert session.session_id == "test_session_001"

    @pytest.mark.asyncio
    async def test_session_persistence(self):
        """Test that session persists conversation history."""
        session = SQLiteSession("test_session_002", ":memory:")

        # Add some test items
        test_items = [
            {"role": "user", "content": "Book a table at Luigi's for 4 tomorrow"},
            {"role": "assistant", "content": "I'll help you book that table."},
        ]

        await session.add_items(test_items)

        # Retrieve items
        items = await session.get_items()

        assert len(items) >= len(test_items)
        # Check that our items are present
        assert any(
            item.get("role") == "user" and "Luigi's" in item.get("content", "")
            for item in items
        )

    @pytest.mark.asyncio
    async def test_session_isolation(self):
        """Test that different sessions are isolated."""
        session1 = SQLiteSession("test_session_003", ":memory:")
        session2 = SQLiteSession("test_session_004", ":memory:")

        # Add items to session 1
        await session1.add_items([{"role": "user", "content": "Session 1 message"}])

        # Add items to session 2
        await session2.add_items([{"role": "user", "content": "Session 2 message"}])

        # Check session 1 doesn't see session 2's messages
        items1 = await session1.get_items()
        items2 = await session2.get_items()

        session1_content = [item.get("content", "") for item in items1]
        session2_content = [item.get("content", "") for item in items2]

        assert "Session 1 message" in session1_content
        assert "Session 2 message" not in session1_content

        assert "Session 2 message" in session2_content
        assert "Session 1 message" not in session2_content
