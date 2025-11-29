"""Restaurant data model."""

from pydantic import BaseModel, ConfigDict, Field


class Restaurant(BaseModel):
    """Restaurant information."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Restaurant name")
    phone_number: str = Field(..., description="Restaurant phone number")
    address: str | None = Field(None, description="Restaurant address")
    cuisine_type: str | None = Field(None, description="Type of cuisine")
