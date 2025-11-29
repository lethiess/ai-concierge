"""Voice call data models."""

from pydantic import BaseModel, Field


class VoiceCallResult(BaseModel):
    """Structured output for voice call reservation result."""

    status: str  # "confirmed", "pending", "rejected", "error"
    restaurant_name: str
    confirmation_number: str | None = None
    confirmed_time: str | None = None  # Actual confirmed time from transcript analysis
    confirmed_date: str | None = None  # Actual confirmed date if changed
    message: str
    call_duration: float | None = None
    call_id: str | None = None


class ConfirmedReservationDetails(BaseModel):
    """Extracted details from a completed reservation call."""

    confirmed_time: str | None = Field(
        None, description="The ACTUAL confirmed time (e.g., '20:00', '8:00 PM')"
    )
    confirmed_date: str | None = Field(
        None, description="The confirmed date if different from requested"
    )
    confirmation_number: str | None = Field(
        None, description="The confirmation number provided by restaurant"
    )
    party_size: int | None = Field(None, description="Number of people")
    customer_name: str | None = Field(None, description="Name for the reservation")
    restaurant_notes: str | None = Field(
        None, description="Any special notes or instructions from restaurant"
    )
    was_modified: bool = Field(
        False,
        description="True if the reservation details were changed from original request",
    )
