from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from app.models.notification import NotificationCreate, Notification, NotificationStatus
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/api/v1")

def get_notification_service() -> NotificationService:
    """Get notification service instance."""
    return NotificationService()

@router.post(
    "/notifications",
    response_model=Notification,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Notification created successfully"},
        400: {"description": "Invalid input data"},
        500: {"description": "Internal server error"}
    }
)
async def create_notification(
    notification: NotificationCreate,
    notification_service: NotificationService = Depends(get_notification_service)
) -> Notification:
    """
    Create a new notification.
    
    Args:
        notification: Notification data to create
        
    Returns:
        Created notification
        
    Raises:
        HTTPException: If creation fails
    """
    try:
        return await notification_service.create_notification(notification)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get(
    "/notifications/{notification_id}",
    response_model=Notification,
    responses={
        200: {"description": "Notification retrieved successfully"},
        404: {"description": "Notification not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_notification(
    notification_id: str,
    notification_service: NotificationService = Depends(get_notification_service)
) -> Notification:
    """
    Get a specific notification by ID.
    
    Args:
        notification_id: ID of the notification to retrieve
        
    Returns:
        Notification object
        
    Raises:
        HTTPException: If notification not found or retrieval fails
    """
    try:
        notification = await notification_service.get_notification(notification_id)
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification {notification_id} not found"
            )
        return notification
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get(
    "/users/{user_id}/notifications",
    response_model=List[Notification],
    responses={
        200: {"description": "Notifications retrieved successfully"},
        500: {"description": "Internal server error"}
    }
)
async def get_user_notifications(
    user_id: str,
    limit: int = Query(default=10, ge=1, le=100, description="Number of notifications to return"),
    skip: int = Query(default=0, ge=0, description="Number of notifications to skip"),
    status: Optional[NotificationStatus] = Query(
        default=None,
        description="Filter notifications by status"
    ),
    notification_service: NotificationService = Depends(get_notification_service)
) -> List[Notification]:
    """
    Get notifications for a specific user.
    
    Args:
        user_id: ID of the user
        limit: Maximum number of notifications to return (1-100)
        skip: Number of notifications to skip
        status: Optional status filter
        
    Returns:
        List of notifications
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        return await notification_service.get_user_notifications(
            user_id=user_id,
            limit=limit,
            skip=skip,
            status=status
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.patch(
    "/notifications/{notification_id}/status",
    response_model=Notification,
    responses={
        200: {"description": "Status updated successfully"},
        400: {"description": "Invalid status value"},
        404: {"description": "Notification not found"},
        500: {"description": "Internal server error"}
    }
)
async def update_notification_status(
    notification_id: str,
    status: NotificationStatus = Query(..., description="New notification status"),
    notification_service: NotificationService = Depends(get_notification_service)
) -> Notification:
    """
    Update notification status.
    
    Args:
        notification_id: ID of the notification
        status: New status value
        
    Returns:
        Updated notification
        
    Raises:
        HTTPException: If update fails
    """
    try:
        return await notification_service.update_status(notification_id, status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check(
    notification_service: NotificationService = Depends(get_notification_service)
):
    """Check the health of the notification service."""
    return await notification_service.health_check() 