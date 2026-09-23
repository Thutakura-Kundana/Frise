"""Database models for Frise application."""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum, ForeignKey
from sqlalchemy.sql import func
import enum
from backend.database import Base


class StatusEnum(str, enum.Enum):
    """Status enum for food items."""
    FRESH = "fresh"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"


class NotificationTypeEnum(str, enum.Enum):
    """Notification type enum."""
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    INFO = "info"


class User(Base):
    """Application user and personal fridge settings."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    fridge_capacity = Column(Integer, nullable=False, default=40)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FoodItem(Base):
    """Food inventory item model."""
    __tablename__ = "food_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    item_name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    barcode = Column(String(100), nullable=True, unique=True)
    image_path = Column(String(500), nullable=True)
    expiry_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(Enum(StatusEnum), default=StatusEnum.FRESH)
    quantity = Column(Integer, default=1)
    description = Column(String(500), nullable=True)
    unit = Column(String(50), nullable=True)
    shelf_location = Column(String(100), nullable=True)
    storage_state = Column(String(100), nullable=True)
    space_units = Column(Integer, default=1)


class Notification(Base):
    """Notification model."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    item_id = Column(Integer, nullable=False)
    message = Column(String(500), nullable=False)
    notification_type = Column(Enum(NotificationTypeEnum), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_read = Column(Boolean, default=False)
    triggered_at = Column(DateTime, nullable=True)


class ActivityLog(Base):
    """Activity log model for tracking user actions."""
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    item_id = Column(Integer, nullable=True)
    details = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
