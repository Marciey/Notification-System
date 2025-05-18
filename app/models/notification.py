from datetime import datetime
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, validator
from enum import Enum
import uuid

class NotificationType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    IN_APP = "in_app"

class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"

class NotificationBase(BaseModel):
    """Base notification model."""
    user_id: str = Field(..., min_length=1, description="User identifier")
    type: NotificationType = NotificationType.IN_APP
    title: str = Field(..., min_length=1, max_length=200, description="Notification title")
    message: str = Field(..., min_length=1, max_length=1000, description="Notification message")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")

    @validator('message')
    def validate_message(cls, v):
        """Validate message length and content."""
        if len(v.strip()) == 0:
            raise ValueError("Message cannot be empty")
        return v

class NotificationCreate(NotificationBase):
    """Model for creating a new notification."""
    id: Optional[str] = Field(default=None, description="Unique notification identifier")
    priority: Optional[str] = Field(default="normal", description="Notification priority")

class Notification(NotificationBase):
    """Complete notification model with status and timestamps."""
    id: str = Field(..., description="Unique notification identifier")
    status: NotificationStatus = Field(..., description="Notification status")
    created_at: datetime = Field(..., description="Creation timestamp")
    sent_at: Optional[datetime] = Field(default=None, description="Sent timestamp")
    failed_at: Optional[datetime] = Field(default=None, description="Failed timestamp")
    error: Optional[str] = Field(default=None, description="Error message")
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, ge=0, description="Maximum number of retries")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "1234567890",
                "user_id": "user_123",
                "type": "email",
                "title": "Welcome!",
                "message": "Welcome to our platform",
                "status": "pending",
                "created_at": "2024-03-17T12:00:00Z",
                "retry_count": 0,
                "max_retries": 3,
                "metadata": {"priority": "high"}
            }
        } 