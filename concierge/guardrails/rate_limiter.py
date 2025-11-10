"""Rate limiting guardrail using OpenAI Agents SDK."""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from agents import GuardrailFunctionOutput, input_guardrail

logger = logging.getLogger(__name__)

# Rate limits
HOURLY_LIMIT = 5
DAILY_LIMIT = 20


def get_rate_limit_db_path() -> Path:
    """Get the path to the rate limit database.

    Returns:
        Path to rate_limits.db in the project root
    """
    return Path("rate_limits.db")


def init_rate_limit_db():
    """Initialize the rate limit database with required tables."""
    db_path = get_rate_limit_db_path()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            session_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            PRIMARY KEY (session_id, timestamp)
        )
    """)

    conn.commit()
    conn.close()
    logger.info(f"Rate limit database initialized at {db_path}")


def get_request_count(session_id: str, hours: int) -> int:
    """Get the number of requests for a session in the last N hours.

    Args:
        session_id: The session identifier
        hours: Number of hours to look back

    Returns:
        Number of requests in the time window
    """
    db_path = get_rate_limit_db_path()

    # Ensure database exists
    if not db_path.exists():
        init_rate_limit_db()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Calculate cutoff time
    cutoff = datetime.now() - timedelta(hours=hours)
    cutoff_str = cutoff.isoformat()

    # Count requests since cutoff
    cursor.execute(
        """
        SELECT COUNT(*) FROM rate_limits
        WHERE session_id = ? AND timestamp > ?
    """,
        (session_id, cutoff_str),
    )

    count = cursor.fetchone()[0]
    conn.close()

    return count


def record_request(session_id: str):
    """Record a request for rate limiting.

    Args:
        session_id: The session identifier
    """
    db_path = get_rate_limit_db_path()

    # Ensure database exists
    if not db_path.exists():
        init_rate_limit_db()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Record this request
    timestamp = datetime.now().isoformat()
    cursor.execute(
        """
        INSERT INTO rate_limits (session_id, timestamp)
        VALUES (?, ?)
    """,
        (session_id, timestamp),
    )

    conn.commit()
    conn.close()

    logger.debug(f"Recorded request for session {session_id} at {timestamp}")


def cleanup_old_records():
    """Clean up rate limit records older than 24 hours."""
    db_path = get_rate_limit_db_path()

    if not db_path.exists():
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Delete records older than 24 hours
    cutoff = datetime.now() - timedelta(hours=24)
    cutoff_str = cutoff.isoformat()

    cursor.execute(
        """
        DELETE FROM rate_limits WHERE timestamp < ?
    """,
        (cutoff_str,),
    )

    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted > 0:
        logger.info(f"Cleaned up {deleted} old rate limit records")


@input_guardrail(name="rate_limit_guardrail")
def rate_limit_guardrail(_context, _agent, user_input) -> GuardrailFunctionOutput:
    """Rate limiting guardrail to prevent abuse.

    Limits:
    - 5 requests per hour per session
    - 20 requests per day per session

    Args:
        _context: The guardrail context (contains session info)
        _agent: The agent being run
        user_input: Raw user input string

    Returns:
        GuardrailFunctionOutput indicating if rate limit was exceeded
    """
    # Extract session_id from context
    # The session_id should be available in the context when the runner is called with a session
    session_id = None

    # Try to get session_id from context
    if hasattr(_context, "session") and _context.session:
        session_id = _context.session.session_id

    # If no session_id, we can't enforce rate limiting (fail open)
    if not session_id:
        logger.warning("No session_id available for rate limiting - allowing request")
        return GuardrailFunctionOutput(
            output_info=None,
            tripwire_triggered=False,
        )

    # Clean up old records periodically
    cleanup_old_records()

    # Check hourly limit
    hourly_count = get_request_count(session_id, hours=1)
    if hourly_count >= HOURLY_LIMIT:
        logger.warning(
            f"Guardrail triggered: Hourly rate limit exceeded ({hourly_count}/{HOURLY_LIMIT})"
        )
        return GuardrailFunctionOutput(
            output_info=f"Rate limit exceeded. You have made {hourly_count} requests in the last hour. "
            f"Please wait before making more requests (limit: {HOURLY_LIMIT} per hour).",
            tripwire_triggered=True,
        )

    # Check daily limit
    daily_count = get_request_count(session_id, hours=24)
    if daily_count >= DAILY_LIMIT:
        logger.warning(
            f"Guardrail triggered: Daily rate limit exceeded ({daily_count}/{DAILY_LIMIT})"
        )
        return GuardrailFunctionOutput(
            output_info=f"Daily rate limit exceeded. You have made {daily_count} requests in the last 24 hours. "
            f"Please try again tomorrow (limit: {DAILY_LIMIT} per day).",
            tripwire_triggered=True,
        )

    # Record this request
    record_request(session_id)

    logger.debug(
        f"Rate limit check passed for session {session_id}: "
        f"{hourly_count + 1}/hour, {daily_count + 1}/day"
    )

    # Allow request
    return GuardrailFunctionOutput(
        output_info=None,
        tripwire_triggered=False,
    )
