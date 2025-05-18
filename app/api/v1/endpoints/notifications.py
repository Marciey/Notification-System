from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.models.notification import NotificationCreate, Notification
from app.services.notification_service import NotificationService

router = APIRouter()

@router.post(
    "/notifications",
    response_model=Dict[str, Any],
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Notification created successfully"},
        400: {"description": "Invalid input data"},
        503: {"description": "Message queue service unavailable"},
        500: {"description": "Internal server error"}
    }
)
async def send_notification(
    notification: NotificationCreate,
    service: NotificationService = Depends()
) -> Dict[str, Any]:
    """Send a new notification.
    
    Args:
        notification: The notification data to send
        
    Returns:
        Dict containing the notification ID and status
        
    Raises:
        HTTPException: If the notification cannot be sent
    """
    return await service.send_notification(notification)

@router.get(
    "/users/{user_id}/notifications",
    response_model=Dict[str, Any],
    responses={
        200: {"description": "Successfully retrieved notifications"},
        400: {"description": "Invalid input parameters"},
        500: {"description": "Internal server error"}
    }
)
async def get_user_notifications(
    user_id: str,
    limit: int = Query(default=50, ge=1, le=100, description="Number of notifications to return"),
    skip: int = Query(default=0, ge=0, description="Number of notifications to skip"),
    service: NotificationService = Depends()
) -> Dict[str, Any]:
    """Get notifications for a user.
    
    Args:
        user_id: The ID of the user
        limit: Maximum number of notifications to return (1-100)
        skip: Number of notifications to skip
        
    Returns:
        Dict containing notifications and pagination info
        
    Raises:
        HTTPException: If the notifications cannot be retrieved
    """
    return await service.get_user_notifications(user_id, limit, skip)

@router.patch(
    "/notifications/{notification_id}/status",
    response_model=Dict[str, Any],
    responses={
        200: {"description": "Status updated successfully"},
        400: {"description": "Invalid status value"},
        404: {"description": "Notification not found"},
        500: {"description": "Internal server error"}
    }
)
async def update_notification_status(
    notification_id: str,
    status: str = Query(..., pattern="^(pending|sent|failed)$"),
    service: NotificationService = Depends()
) -> Dict[str, Any]:
    """Update notification status.
    
    Args:
        notification_id: The ID of the notification
        status: New status value (pending, sent, or failed)
        
    Returns:
        Dict containing the updated notification status
        
    Raises:
        HTTPException: If the status cannot be updated
    """
    return await service.update_notification_status(notification_id, status) 