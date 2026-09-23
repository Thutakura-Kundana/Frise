"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class AuthRegister(BaseModel):
    """Registration request."""
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    fridge_capacity: int = Field(40, ge=1, le=1000)


class AuthLogin(BaseModel):
    """Login request."""
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    """Safe user profile response."""
    id: int
    email: str
    fridge_capacity: int

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    """Token and user response."""
    access_token: str
    token_type: str
    user: UserResponse


class FridgeSettings(BaseModel):
    """Personal fridge capacity settings."""
    fridge_capacity: int = Field(..., ge=1, le=1000)


class StatusEnum(str, Enum):
    """Status enum for food items."""
    FRESH = "fresh"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"


class NotificationTypeEnum(str, Enum):
    """Notification type enum."""
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    INFO = "info"


class FoodItemBase(BaseModel):
    """Base schema for food items."""
    item_name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., min_length=1, max_length=100)
    barcode: Optional[str] = Field(None, max_length=100)
    expiry_date: datetime
    quantity: Optional[int] = Field(1, ge=1)
    description: Optional[str] = Field(None, max_length=500)
    unit: Optional[str] = Field(None, max_length=50)
    shelf_location: Optional[str] = Field(None, max_length=100)
    storage_state: Optional[str] = Field(None, max_length=100)
    space_units: Optional[int] = Field(1, ge=1)

    @field_validator("item_name", "category", mode="before")
    @classmethod
    def required_string_must_not_be_blank(cls, value):
        """Trim required text inputs and reject blank values."""
        if isinstance(value, str):
            value = value.strip()
        return value

    @field_validator(
        "barcode",
        "description",
        "unit",
        "shelf_location",
        "storage_state",
        mode="before"
    )
    @classmethod
    def blank_string_to_none(cls, value):
        """Treat blank optional text inputs as missing values."""
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class FoodItemCreate(FoodItemBase):
    """Schema for creating food items."""
    pass


class FoodItemUpdate(BaseModel):
    """Schema for updating food items."""
    item_name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    barcode: Optional[str] = Field(None, max_length=100)
    expiry_date: Optional[datetime] = None
    quantity: Optional[int] = Field(None, ge=1)
    description: Optional[str] = Field(None, max_length=500)
    unit: Optional[str] = Field(None, max_length=50)
    shelf_location: Optional[str] = Field(None, max_length=100)
    storage_state: Optional[str] = Field(None, max_length=100)
    space_units: Optional[int] = Field(None, ge=1)

    @field_validator("item_name", "category", mode="before")
    @classmethod
    def required_string_must_not_be_blank(cls, value):
        """Trim optional required text fields when they are provided."""
        if isinstance(value, str):
            value = value.strip()
        return value

    @field_validator(
        "barcode",
        "description",
        "unit",
        "shelf_location",
        "storage_state",
        mode="before"
    )
    @classmethod
    def blank_string_to_none(cls, value):
        """Treat blank optional text inputs as missing values."""
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class FoodItemResponse(FoodItemBase):
    """Schema for food item responses."""
    id: int
    image_path: Optional[str]
    status: StatusEnum
    created_at: datetime

    class Config:
        """Pydantic config."""
        from_attributes = True


class NotificationBase(BaseModel):
    """Base notification schema."""
    message: str
    notification_type: NotificationTypeEnum


class NotificationCreate(NotificationBase):
    """Schema for creating notifications."""
    item_id: int


class NotificationResponse(NotificationBase):
    """Schema for notification responses."""
    id: int
    item_id: int
    created_at: datetime
    is_read: bool
    triggered_at: Optional[datetime]

    class Config:
        """Pydantic config."""
        from_attributes = True


class DashboardStats(BaseModel):
    """Dashboard statistics schema."""
    total_items: int
    fresh_items: int
    expiring_soon_items: int
    expired_items: int
    total_notifications: int
    unread_notifications: int
    fridge_capacity: int
    used_space: int
    empty_space: int


class CategoryStats(BaseModel):
    """Category statistics schema."""
    category: str
    count: int
    fresh: int
    expiring_soon: int
    expired: int


class ActivityLogResponse(BaseModel):
    """Activity log response schema."""
    id: int
    action: str
    item_id: Optional[int]
    details: Optional[str]
    created_at: datetime

    class Config:
        """Pydantic config."""
        from_attributes = True
