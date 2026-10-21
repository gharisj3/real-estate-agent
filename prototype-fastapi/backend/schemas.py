from typing import Optional
from pydantic import BaseModel, Field

ALLOWED_STATUSES = {"available", "booked", "off-market"}


class PropertyIn(BaseModel):
    title: str
    address: str
    property_type: str = "apartment"
    price: float = Field(ge=0)
    bedrooms: int = Field(ge=0, default=0)
    bathrooms: int = Field(ge=0, default=0)
    description: str = ""
    status: str = "available"
    image_url: str = ""


class PropertyUpdate(BaseModel):
    title: Optional[str] = None
    address: Optional[str] = None
    property_type: Optional[str] = None
    price: Optional[float] = Field(default=None, ge=0)
    bedrooms: Optional[int] = Field(default=None, ge=0)
    bathrooms: Optional[int] = Field(default=None, ge=0)
    description: Optional[str] = None
    status: Optional[str] = None
    image_url: Optional[str] = None


class PropertyOut(PropertyIn):
    id: int
    created_at: str
