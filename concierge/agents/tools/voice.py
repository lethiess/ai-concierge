"""Voice tools for making real-time calls using OpenAI Realtime API and Twilio."""

import asyncio
import logging
import contextlib
from datetime import datetime
import uuid

from concierge.config import get_config
from concierge.models import Restaurant, VoiceCallResult
from concierge.services.call_manager import get_call_manager
from concierge.services.twilio_service import TwilioService

logger = logging.getLogger(__name__)


async def _make_voice_call(
    call_details: dict,
    to_number: str,
    call_type: str,
    timeout: int = 180,
) -> VoiceCallResult:
    """Generic function to make a real-time voice call.

    Args:
        call_details: Dictionary containing call information
        to_number: Phone number to call
        call_type: Type of call ("reservation" or "cancellation")
        timeout: Maximum wait time in seconds

    Returns:
        VoiceCallResult with the outcome of the call
    """
    restaurant_name = call_details.get("restaurant_name", "Unknown")
    logger.info(f"Initiating real-time {call_type} call to {restaurant_name}")

    config = get_config()
    twilio_service = TwilioService()
    call_manager = get_call_manager()

    # Check if Twilio is configured
    if not twilio_service.is_configured():
        logger.error("Twilio not configured - returning simulated result")
        return VoiceCallResult(
            status="error",
            restaurant_name=restaurant_name,
            message="Twilio not configured - returning simulated result",
            call_duration=0.0,
            call_id=None,
        )

    # Check if server is configured
    if not config.public_domain:
        logger.error(
            "PUBLIC_DOMAIN not configured - cannot make call. "
            "Please set PUBLIC_DOMAIN in .env (e.g., your ngrok URL)"
        )
        return VoiceCallResult(
            status="error",
            restaurant_name=restaurant_name,
            message="Server not configured: PUBLIC_DOMAIN must be set for Twilio webhooks",
            call_duration=0.0,
            call_id=None,
        )

    start_time = datetime.now()
    call_id = None

    try:
        # Step 1: Create call in CallManager
        if "call_type" not in call_details:
            call_details["call_type"] = call_type

        # Use provided call_id or generate one
        call_id = call_details.get("call_id") or call_manager.generate_call_id()

        call_manager.create_call(call_details, call_id)
        logger.info(f"✓ Created call {call_id} in CallManager (call_type: {call_type})")

        # Step 2: Build TwiML URL
        twiml_url = f"https://{config.public_domain}/twiml?call_id={call_id}"
        status_callback_url = f"https://{config.public_domain}/twilio-status"
        logger.info(f"TwiML URL: {twiml_url}")

        # Step 3: Initiate Twilio call
        call_sid = twilio_service.initiate_call(
            to_number=to_number,
            twiml_url=twiml_url,
            status_callback=status_callback_url,
        )
        logger.info(f"Initiated Twilio call {call_sid} for {call_type} call {call_id}")

        # Step 4: Wait for call to complete
        result = await wait_for_call_completion(call_id, timeout=timeout)

        duration = (datetime.now() - start_time).total_seconds()
        result.call_duration = duration

    except Exception as e:
        logger.exception(f"Error making realtime {call_type} call")
        duration = (datetime.now() - start_time).total_seconds()

        # Try to get call_id if it was created before the error
        error_call_id = None
        with contextlib.suppress(NameError):
            error_call_id = call_id

        result = VoiceCallResult(
            status="error",
            restaurant_name=restaurant_name,
            message=f"Error making call: {e}",
            call_duration=duration,
            call_id=error_call_id,
        )

    return result


async def make_reservation_call_via_twilio(
    reservation_details: dict, restaurant: Restaurant
) -> VoiceCallResult:
    """Make a real-time reservation call using Twilio and OpenAI Realtime API.

    Args:
        reservation_details: Reservation information
        restaurant: Restaurant to call

    Returns:
        VoiceCallResult with the outcome of the call
    """
    return await _make_voice_call(
        call_details=reservation_details,
        to_number=restaurant.phone_number,
        call_type="reservation",
    )


async def make_cancellation_call_via_twilio(cancellation_details: dict) -> dict:
    """Make a real-time cancellation call using Twilio and OpenAI Realtime API.

    Args:
        cancellation_details: Dictionary containing cancellation information

    Returns:
        Dictionary with cancellation result
    """
    # Generate a UUID for cancellation calls if not present (to match previous behavior)
    if "call_id" not in cancellation_details:
        cancellation_details["call_id"] = str(uuid.uuid4())

    restaurant_phone = cancellation_details.get("restaurant_phone")

    result = await _make_voice_call(
        call_details=cancellation_details,
        to_number=restaurant_phone,
        call_type="cancellation",
        timeout=120,  # Cancellation calls might be shorter
    )

    # Convert VoiceCallResult to dict format expected by cancellation tool
    if result.status == "error":
        return {
            "success": False,
            "status": "error",
            "message": result.message,
            "call_id": result.call_id,
            "call_duration": result.call_duration,
        }

    # Build success message
    restaurant_name = cancellation_details.get("restaurant_name")
    confirmation_number = cancellation_details.get("confirmation_number")
    date = cancellation_details.get("date", "")
    time = cancellation_details.get("time", "")
    party_size = cancellation_details.get("party_size", "")

    confirmation_msg = (
        f"Your reservation at {restaurant_name} for {party_size} people "
        f"on {date} at {time} has been successfully cancelled. "
        f"Original confirmation number: {confirmation_number}."
    )

    if result.confirmation_number:
        confirmation_msg += f" Restaurant noted: {result.confirmation_number}"

    return {
        "success": True,
        "status": "cancelled",
        "message": confirmation_msg,
        "call_id": result.call_id,
        "call_duration": result.call_duration,
        "restaurant_name": restaurant_name,
        "original_confirmation": confirmation_number,
        "date": date,
        "time": time,
        "party_size": party_size,
    }


async def wait_for_call_completion(
    call_id: str, timeout: int = 180, poll_interval: int = 2
) -> VoiceCallResult:
    """Wait for a call to complete by polling CallManager.

    Args:
        call_id: Call identifier
        timeout: Maximum wait time in seconds
        poll_interval: Seconds between status checks

    Returns:
        VoiceCallResult

    Raises:
        TimeoutError: If call doesn't complete within timeout
    """
    call_manager = get_call_manager()
    elapsed = 0

    logger.info(f"Waiting for call {call_id} to complete (timeout: {timeout}s)")

    while elapsed < timeout:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

        call_state = call_manager.get_call(call_id)
        if not call_state:
            msg = f"Call {call_id} not found in CallManager"
            raise ValueError(msg)

        if call_state.status == "completed":
            logger.info(f"Call {call_id} completed successfully")

            # Wait a bit for LLM transcript analysis to complete
            # The analysis runs async in update_status(), so we need to give it time
            max_analysis_wait = 10  # seconds
            analysis_elapsed = 0

            while analysis_elapsed < max_analysis_wait:
                # Check if transcript analysis has completed by looking for the confirmed_time field
                # which is only set by the LLM analysis
                if "confirmed_time" in call_state.reservation_details:
                    logger.info(
                        "✓ Transcript analysis completed, proceeding with result"
                    )
                    break

                # Also break if we have a confirmation number (analysis might be done)
                if call_state.confirmation_number:
                    logger.info("✓ Confirmation number present, proceeding with result")
                    break

                await asyncio.sleep(0.5)  # Check every 500ms
                analysis_elapsed += 0.5

                # Refresh call state
                call_state = call_manager.get_call(call_id)

            if analysis_elapsed >= max_analysis_wait:
                logger.warning(
                    f"⚠ Transcript analysis did not complete within {max_analysis_wait}s, proceeding anyway"
                )

            # Determine status based on confirmation number
            if call_state.confirmation_number:
                status = "confirmed"
                message = f"Reservation confirmed at {call_state.reservation_details.get('restaurant_name', 'restaurant')}"
            else:
                status = "pending"
                message = "Call completed but no confirmation number received. Please check with restaurant."

            # Extract confirmed time and date from transcript analysis
            confirmed_time = call_state.reservation_details.get("confirmed_time")
            confirmed_date = call_state.reservation_details.get("confirmed_date")

            return VoiceCallResult(
                status=status,
                restaurant_name=call_state.reservation_details.get(
                    "restaurant_name", "Unknown"
                ),
                confirmation_number=call_state.confirmation_number,
                confirmed_time=confirmed_time,
                confirmed_date=confirmed_date,
                message=message,
                call_id=call_id,
            )

        if call_state.status == "failed":
            logger.error(f"Call {call_id} failed: {call_state.error_message}")
            return VoiceCallResult(
                status="error",
                restaurant_name=call_state.reservation_details.get(
                    "restaurant_name", "Unknown"
                ),
                message=f"Call failed: {call_state.error_message}",
                call_id=call_id,
            )

    # Timeout
    logger.warning(f"Call {call_id} timed out after {timeout}s")
    await call_manager.update_status(call_id, "failed")
    call_manager.set_error(call_id, f"Call timed out after {timeout}s")

    return VoiceCallResult(
        status="error",
        restaurant_name=call_manager.get_call(call_id).reservation_details.get(
            "restaurant_name", "Unknown"
        ),
        message=f"Call timed out after {timeout} seconds",
        call_id=call_id,
    )
