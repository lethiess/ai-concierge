"""Function tools for the AI Concierge agents."""

import logging

from agents import function_tool

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
