"""Function tools for the AI Concierge agents."""

import logging

from agents import function_tool

from concierge.services.restaurant_service import RestaurantService
from concierge.services.twilio_service import TwilioService

logger = logging.getLogger(__name__)


@function_tool
def find_restaurant(restaurant_name: str) -> dict:
    """Find a restaurant by name.

    Args:
        restaurant_name: Name of the restaurant to find

    Returns:
        Dictionary with restaurant information or error
    """
    logger.info(f"Looking up restaurant: {restaurant_name}")

    service = RestaurantService()
    restaurant = service.find_restaurant(restaurant_name)

    if not restaurant:
        return {
            "success": False,
            "error": f"Restaurant '{restaurant_name}' not found",
        }

    return {
        "success": True,
        "restaurant": {
            "name": restaurant.name,
            "phone_number": restaurant.phone_number,
            "address": restaurant.address,
            "cuisine_type": restaurant.cuisine_type,
        },
    }


@function_tool
def make_call(
    phone_number: str,
    restaurant_name: str,
    party_size: int,  # noqa: ARG001 - Used in actual call conversation
    date: str,  # noqa: ARG001 - Used in actual call conversation
    time: str,  # noqa: ARG001 - Used in actual call conversation
    customer_name: str | None = None,  # noqa: ARG001 - Used in actual call conversation
    special_requests: str | None = None,  # noqa: ARG001 - Used in actual call conversation
) -> dict:
    """Initiate a phone call to make a reservation.

    Args:
        phone_number: Restaurant phone number
        restaurant_name: Name of the restaurant
        party_size: Number of people (used in call conversation)
        date: Reservation date (used in call conversation)
        time: Reservation time (used in call conversation)
        customer_name: Name for the reservation (used in call conversation)
        special_requests: Any special requests (used in call conversation)

    Returns:
        Dictionary with call initiation result
    """
    logger.info(f"Initiating call to {restaurant_name} at {phone_number}")

    service = TwilioService()

    if not service.is_configured():
        logger.warning("Twilio not configured - returning simulated result")
        return {
            "success": True,
            "call_sid": "SIMULATED",
            "status": "simulated",
            "message": "Twilio not configured. In a real scenario, the call would be initiated.",
        }

    try:
        call_sid = service.initiate_call(to_number=phone_number)
    except Exception as e:
        logger.exception("Failed to initiate call")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to initiate call: {e}",
        }
    else:
        return {
            "success": True,
            "call_sid": call_sid,
            "status": "initiated",
            "message": f"Call initiated to {restaurant_name}",
        }


@function_tool
def get_call_status(call_sid: str) -> dict:
    """Get the status of an ongoing call.

    Args:
        call_sid: The Twilio call SID

    Returns:
        Dictionary with call status information
    """
    logger.info(f"Checking status for call: {call_sid}")

    if call_sid == "SIMULATED":
        return {
            "success": True,
            "status": "completed",
            "duration": 45,
            "message": "Simulated call completed successfully",
        }

    service = TwilioService()

    if not service.is_configured():
        return {
            "success": False,
            "error": "Twilio not configured",
        }

    try:
        status = service.get_call_status(call_sid)
    except Exception as e:
        logger.exception("Failed to get call status")
        return {
            "success": False,
            "error": str(e),
        }
    else:
        return {
            "success": True,
            **status,
        }


@function_tool
def end_call(call_sid: str) -> dict:
    """End an active call.

    Args:
        call_sid: The Twilio call SID

    Returns:
        Dictionary with result
    """
    logger.info(f"Ending call: {call_sid}")

    if call_sid == "SIMULATED":
        return {
            "success": True,
            "message": "Simulated call ended",
        }

    service = TwilioService()

    if not service.is_configured():
        return {
            "success": False,
            "error": "Twilio not configured",
        }

    try:
        service.end_call(call_sid)
    except Exception as e:
        logger.exception("Failed to end call")
        return {
            "success": False,
            "error": str(e),
        }
    else:
        return {
            "success": True,
            "message": f"Call {call_sid} ended successfully",
        }
