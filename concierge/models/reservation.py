"""Data models for restaurant reservations."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ReservationStatus(str, Enum):
    """Status of a reservation request."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    ERROR = "error"


class Restaurant(BaseModel):
    """Restaurant information."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Restaurant name")
    phone_number: str = Field(..., description="Restaurant phone number")
    address: str | None = Field(None, description="Restaurant address")
    cuisine_type: str | None = Field(None, description="Type of cuisine")


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
