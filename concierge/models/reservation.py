"""Data models for restaurant reservations."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from concierge.models.restaurant import Restaurant


class ReservationStatus(str, Enum):
    """Status of a reservation request."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    ERROR = "error"


class ReservationRequest(BaseModel):
    """User's reservation request details."""

    model_config = ConfigDict(frozen=True)

    restaurant_name: str = Field(..., description="Name of the restaurant")
    party_size: int = Field(..., gt=0, description="Number of people")
    date: str = Field(..., description="Reservation date")
    time: str = Field(..., description="Reservation time")
    user_name: str | None = Field(None, description="Name for the reservation")
    user_phone: str | None = Field(None, description="Contact phone number")
    special_requests: str | None = Field(None, description="Special requests or notes")


class ReservationResult(BaseModel):
    """Result of a reservation attempt."""

    status: ReservationStatus = Field(..., description="Reservation status")
    restaurant: Restaurant = Field(..., description="Restaurant details")
    request: ReservationRequest = Field(..., description="Original request")
    confirmation_number: str | None = Field(
        None, description="Confirmation number if successful"
    )
    message: str = Field(..., description="Status message or explanation")
    call_duration: float | None = Field(
        None, description="Duration of the phone call in seconds"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now, description="When the result was created"
    )


class ReservationDetails(BaseModel):
    """Structured output for parsed reservation request."""

    restaurant_name: str
    party_size: int
    date: str
    time: str
    user_name: str | None = None
    user_phone: str | None = None
    special_requests: str | None = None
