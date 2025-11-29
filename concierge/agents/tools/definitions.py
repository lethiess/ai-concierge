"""Function tools for the AI Concierge agents."""

import json
import logging

from agents import function_tool
from openai import OpenAI

from concierge.config import get_config
from concierge.services.restaurant_service import RestaurantService

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
async def initiate_reservation_call(
    restaurant_name: str,
    restaurant_phone: str,
    party_size: int,
    date: str,
    time: str,
    customer_name: str | None = None,
    special_requests: str | None = None,
) -> dict:
    """Initiate a real-time voice call to make the restaurant reservation.

    This triggers a Twilio call that uses OpenAI Realtime API for the conversation.

    Args:
        restaurant_name: Name of the restaurant
        restaurant_phone: Phone number to call
        party_size: Number of people
        date: Reservation date
        time: Reservation time
        customer_name: Customer name for the reservation
        special_requests: Any special requests

    Returns:
        Dictionary with call initiation result
    """
    config = get_config()
    logger.info(f"Initiating realtime voice call to {restaurant_name}")

    # Import here to avoid circular dependency
    from .voice import (
        make_reservation_call_via_twilio,
    )
    from concierge.models import Restaurant

    # Use concierge name from config if not provided
    if not customer_name:
        customer_name = config.concierge_name
        logger.info(f"Using concierge name from config: {customer_name}")

    # Prepare reservation details
    reservation_details = {
        "restaurant_name": restaurant_name,
        "restaurant_phone": restaurant_phone,
        "party_size": party_size,
        "date": date,
        "time": time,
        "customer_name": customer_name,
        "special_requests": special_requests,
        "call_type": "reservation",  # Mark as reservation call
    }

    # Create restaurant object (in real implementation, this would come from lookup)
    restaurant = Restaurant(
        name=restaurant_name,
        phone_number=restaurant_phone,
        address="",  # Not needed for call
        cuisine_type="",  # Not needed for call
    )

    # Make the realtime voice call
    result = await make_reservation_call_via_twilio(reservation_details, restaurant)

    return {
        "success": result.status == "confirmed",
        "status": result.status,
        "confirmation_number": result.confirmation_number,
        "confirmed_time": result.confirmed_time,  # Actual time from transcript
        "confirmed_date": result.confirmed_date,  # Actual date if changed
        "message": result.message,
        "call_duration": result.call_duration,
        "call_id": result.call_id,
        # Include full reservation details for session lookup
        "restaurant_name": restaurant_name,
        "restaurant_phone": restaurant_phone,
        "party_size": party_size,
        "date": date,
        "time": time,
        "customer_name": customer_name,
    }


@function_tool
def search_restaurants_llm(
    query: str,
    cuisine: str | None = None,
    location: str | None = None,
    rating_min: float = 4.0,
) -> dict:
    """Search for restaurants using LLM to generate realistic mock results.

    This is a demonstration tool that uses an LLM to generate plausible restaurant
    options based on user criteria. All generated restaurants connect to the demo
    phone line for actual reservations.

    Args:
        query: Natural language search query (e.g., "best Italian in Konstanz")
        cuisine: Optional cuisine type filter (Italian, Chinese, Mexican, etc.)
        location: Optional location/city filter
        rating_min: Minimum rating (1.0-5.0), defaults to 4.0

    Returns:
        Dictionary with search results:
        {
            "success": True,
            "restaurants": [
                {
                    "name": "Restaurant Name",
                    "cuisine": "Italian",
                    "address": "123 Main St, City",
                    "rating": 4.8,
                    "description": "Brief description",
                    "phone_number": "demo_phone"
                },
                ...
            ],
            "count": 3
        }
    """
    logger.info(
        f"Searching restaurants: query='{query}', cuisine={cuisine}, "
        f"location={location}, rating_min={rating_min}"
    )

    # Get demo restaurant phone for all results
    config = get_config()
    demo_phone = config.demo_restaurant_phone

    # Build LLM prompt to generate realistic restaurant options
    prompt = f"""Generate 3-5 realistic restaurant recommendations as JSON.

Search criteria:
- Query: {query}
- Cuisine: {cuisine or "any"}
- Location: {location or "not specified"}
- Minimum rating: {rating_min}/5.0

Generate restaurants that would match these criteria. Include:
- Realistic restaurant names (creative but believable)
- Accurate cuisine type
- Plausible addresses in the location (if specified)
- Ratings between {rating_min} and 5.0
- Brief, enticing descriptions (1-2 sentences)

Return ONLY valid JSON in this exact format:
{{
  "restaurants": [
    {{
      "name": "Restaurant Name",
      "cuisine": "Cuisine Type",
      "address": "Street Address, City",
      "rating": 4.8,
      "description": "Brief description of the restaurant"
    }}
  ]
}}"""

    try:
        # Use OpenAI API to generate mock results
        client = OpenAI(api_key=config.openai_api_key)

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use mini for cost efficiency
            messages=[
                {
                    "role": "system",
                    "content": "You are a restaurant recommendation system. Generate realistic restaurant data in JSON format.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,  # Higher temperature for creative variety
            response_format={"type": "json_object"},
        )

        # Parse the LLM response
        result_text = response.choices[0].message.content
        result_data = json.loads(result_text)

        restaurants = result_data.get("restaurants", [])

        # Add demo phone number to all restaurants (for actual calling)
        for restaurant in restaurants:
            restaurant["phone_number"] = demo_phone

        logger.info(f"Generated {len(restaurants)} restaurant options")

        return {
            "success": True,
            "restaurants": restaurants,
            "count": len(restaurants),
        }

    except Exception as e:
        logger.error(f"Error generating restaurant search results: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to search restaurants: {e!s}",
            "restaurants": [],
            "count": 0,
        }


@function_tool
def lookup_reservation_from_history(
    confirmation_number: str | None = None,
    restaurant_name: str | None = None,
) -> dict:
    """Look up a reservation from conversation history.

    This tool searches completed reservation calls for matching reservations.
    It can search by confirmation number or find the most recent reservation.

    Args:
        confirmation_number: Optional confirmation number to search for
        restaurant_name: Optional restaurant name to filter by

    Returns:
        Dictionary with reservation details if found:
        {
            "success": True,
            "reservation": {
                "restaurant_name": str,
                "restaurant_phone": str,
                "confirmation_number": str,
                "party_size": int,
                "date": str,
                "time": str,
                "customer_name": str | None
            }
        }
    """
    logger.debug(
        f"Looking up reservation: conf={confirmation_number}, restaurant={restaurant_name}"
    )

    try:
        from concierge.services.call_manager import get_call_manager

        call_manager = get_call_manager()

        # Get all completed calls
        all_calls = call_manager.get_all_calls()
        completed_calls = [
            c for c in all_calls if c.status == "completed" and c.confirmation_number
        ]

        if not completed_calls:
            logger.info("No completed reservations found")
            return {
                "success": False,
                "error": "No reservations found. Please provide the confirmation number or make a reservation first.",
            }

        # Sort by end_time (most recent first)
        completed_calls.sort(
            key=lambda c: c.end_time if c.end_time else c.start_time, reverse=True
        )

        logger.debug(f"Searching {len(completed_calls)} completed reservations")

        # Search for matching reservation
        for call_state in completed_calls:
            # Use confirmed time/date if available (from transcript analysis)
            # Otherwise fall back to originally requested time/date
            confirmed_time = call_state.reservation_details.get("confirmed_time")
            confirmed_date = call_state.reservation_details.get("confirmed_date")

            time = confirmed_time or call_state.reservation_details.get("time")
            date = confirmed_date or call_state.reservation_details.get("date")

            # Build reservation dict
            reservation = {
                "restaurant_name": call_state.reservation_details.get(
                    "restaurant_name"
                ),
                "restaurant_phone": call_state.reservation_details.get(
                    "restaurant_phone"
                ),
                "confirmation_number": call_state.confirmation_number,
                "party_size": call_state.reservation_details.get("party_size"),
                "date": date,
                "time": time,
                "customer_name": call_state.reservation_details.get("customer_name"),
            }

            # Filter by confirmation number if provided
            if confirmation_number:
                if (
                    call_state.confirmation_number
                    and str(call_state.confirmation_number).lower()
                    == str(confirmation_number).lower()
                ):
                    logger.info(f"Found reservation #{confirmation_number}")
                    return {"success": True, "reservation": reservation}
            # Filter by restaurant name if provided
            elif restaurant_name:
                res_name = call_state.reservation_details.get("restaurant_name", "")
                if restaurant_name.lower() in res_name.lower():
                    logger.info(f"Found reservation at {res_name}")
                    return {"success": True, "reservation": reservation}
            # No filters - return most recent
            else:
                logger.info(
                    f"Found most recent reservation at {reservation.get('restaurant_name')}"
                )
                return {"success": True, "reservation": reservation}

        # If we got here, nothing matched
        logger.info("No matching reservations found")
        return {
            "success": False,
            "error": "No matching reservations found. Please provide the confirmation number or more details about the reservation.",
        }

    except Exception as e:
        logger.error(f"Error looking up reservation: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Failed to look up reservation: {e!s}",
        }


@function_tool
async def initiate_cancellation_call(
    restaurant_phone: str,
    confirmation_number: str,
    restaurant_name: str,
    date: str,
    time: str,
    party_size: int,
    customer_name: str | None = None,
) -> dict:
    """Initiate a real-time voice call to cancel a restaurant reservation.

    This tool creates a voice agent and initiates an actual phone call to the
    restaurant to request cancellation. The call is made using the OpenAI Realtime
    API via Twilio.

    Args:
        restaurant_phone: Restaurant phone number to call
        confirmation_number: Reservation confirmation number
        restaurant_name: Name of the restaurant
        date: Reservation date
        time: Reservation time
        party_size: Number of people
        customer_name: Optional customer name

    Returns:
        Dictionary with cancellation result:
        {
            "success": True,
            "status": "cancelled",
            "message": "Cancellation confirmed...",
            "call_id": "...",
            "call_duration": 45.2
        }
    """
    logger.info(
        f"Initiating cancellation call to {restaurant_name} "
        f"for confirmation #{confirmation_number}"
    )

    try:
        # Import here to avoid circular imports
        from .voice import make_cancellation_call_via_twilio

        # Create cancellation details dict
        cancellation_details = {
            "restaurant_name": restaurant_name,
            "restaurant_phone": restaurant_phone,
            "confirmation_number": confirmation_number,
            "date": date,
            "time": time,
            "party_size": party_size,
            "customer_name": customer_name or "the customer",
        }

        # Make the cancellation call
        result = await make_cancellation_call_via_twilio(cancellation_details)

        logger.info(f"Cancellation call completed: status={result.get('status')}")
        return result

    except Exception as e:
        logger.error(f"Error initiating cancellation call: {e}", exc_info=True)
        return {
            "success": False,
            "status": "error",
            "message": f"Failed to initiate cancellation call: {e!s}",
        }
