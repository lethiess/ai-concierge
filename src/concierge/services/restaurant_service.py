"""Restaurant lookup service - Mock implementation for MVP."""

import logging

from concierge.config import get_config
from concierge.models import Restaurant

logger = logging.getLogger(__name__)


class RestaurantService:
    """Service for looking up restaurant information.

    This is a mock implementation that returns static demo data.
    In production, this would integrate with a real restaurant database or API.
    """

    def __init__(self) -> None:
        """Initialize the restaurant service."""
        self.config = get_config()
        self.demo_restaurant = Restaurant(
            name=self.config.demo_restaurant_name,
            phone_number=self.config.demo_restaurant_phone,
            address="123 Demo Street, San Francisco, CA 94102",
            cuisine_type="Italian",
        )
        logger.info(
            f"Initialized restaurant service with demo: {self.demo_restaurant.name}"
        )

    def find_restaurant(self, restaurant_name: str) -> Restaurant | None:
        """Find a restaurant by name.

        Args:
            restaurant_name: The name of the restaurant to find

        Returns:
            Restaurant object if found, None otherwise
        """
        logger.info(f"Looking up restaurant: {restaurant_name}")

        # For MVP, always return the demo restaurant regardless of the name
        # This allows testing with any restaurant name
        logger.info(
            f"Returning demo restaurant '{self.demo_restaurant.name}' "
            f"for search query '{restaurant_name}'"
        )
        return self.demo_restaurant

    def get_demo_restaurant(self) -> Restaurant:
        """Get the demo restaurant directly.

        Returns:
            The demo restaurant object
        """
        return self.demo_restaurant
