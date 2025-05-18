import logging
from datetime import datetime
from fastapi import HTTPException, status
from app.core.mongodb import MongoDB
from app.core.rabbitmq import RabbitMQ
from app.models.notification import NotificationCreate, Notification, NotificationStatus
import asyncio
from typing import Dict, Any, Optional, List
import uuid

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service class for handling all notification operations.
    
    This service manages the lifecycle of notifications including:
    - Creation and queuing of notifications
    - Processing and sending notifications
    - Retry mechanisms for failed notifications
    - Status updates and tracking
    - Health monitoring of dependencies
    """
    
    def __init__(self):
        """Initialize service with database and message queue connections."""
        self.db = MongoDB.db
        self.rabbitmq = RabbitMQ()
        self.max_retries = 3  # Maximum number of retry attempts for failed notifications
        self.retry_delay = 60  # Base delay in seconds between retries

    async def health_check(self) -> Dict[str, Any]:
        """
        Check the health of all service dependencies.
        
        Returns:
            Dict containing health status of MongoDB and RabbitMQ connections
        """
        try:
            # Check MongoDB connection
            mongo_status = await self._check_mongodb()
            # Check RabbitMQ connection
            rabbitmq_status = await self._check_rabbitmq()
            # Service is healthy only if all dependencies are healthy
            is_healthy = mongo_status["status"] == "healthy" and rabbitmq_status["status"] == "healthy"
            
            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "dependencies": {
                    "mongodb": mongo_status,
                    "rabbitmq": rabbitmq_status
                }
            }
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }

    async def _check_mongodb(self) -> Dict[str, Any]:
        """
        Check MongoDB connection and basic operations.
        
        Returns:
            Dict containing MongoDB connection status
        """
        try:
            # Test basic database operations
            await self.db.command("ping")
            await self.db.notifications.find_one({})
            return {
                "status": "healthy",
                "message": "MongoDB connection is working"
            }
        except Exception as e:
            logger.error(f"MongoDB health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "message": f"MongoDB connection failed: {str(e)}"
            }

    async def _check_rabbitmq(self) -> Dict[str, Any]:
        """
        Check RabbitMQ connection and channel.
        
        Returns:
            Dict containing RabbitMQ connection status
        """
        try:
            is_connected = await RabbitMQ.check_connection()
            if not is_connected:
                return {
                    "status": "unhealthy",
                    "message": "RabbitMQ connection is not working"
                }
            return {
                "status": "healthy",
                "message": "RabbitMQ connection is working"
            }
        except Exception as e:
            logger.error(f"RabbitMQ health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "message": f"RabbitMQ connection failed: {str(e)}"
            }

    async def create_notification(self, notification: NotificationCreate) -> Notification:
        """
        Create and queue a new notification.
        
        Args:
            notification: NotificationCreate object containing notification details
            
        Returns:
            Created Notification object
            
        Raises:
            HTTPException: If notification creation fails
        """
        try:
            # Generate unique ID and timestamp
            notification_id = str(uuid.uuid4())
            created_at = datetime.utcnow()
            
            # Create notification document
            notification_doc = {
                "id": notification_id,
                "user_id": notification.user_id,
                "title": notification.title,
                "message": notification.message,
                "type": notification.type,
                "status": NotificationStatus.PENDING,
                "created_at": created_at,
                "retry_count": 0,
                "max_retries": self.max_retries,
                "metadata": notification.metadata or {}
            }
            
            # Save to database and queue for processing
            await self.db.notifications.insert_one(notification_doc)
            await self.rabbitmq.publish_message(notification_doc)
            logger.info(f"Notification created and queued: {notification_id}")
            
            # Return created notification as Pydantic model
            return Notification(
                id=notification_id,
                user_id=notification.user_id,
                title=notification.title,
                message=notification.message,
                type=notification.type,
                status=NotificationStatus.PENDING,
                created_at=created_at,
                retry_count=0,
                max_retries=self.max_retries,
                metadata=notification.metadata or {}
            )
            
        except Exception as e:
            logger.error(f"Failed to create notification: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create notification: {str(e)}"
            )

    async def process_notification(self, notification: dict) -> bool:
        """
        Process a notification with retry logic.
        
        Args:
            notification: Dictionary containing notification details
            
        Returns:
            bool: True if notification was processed successfully
        """
        try:
            # Check if max retries exceeded
            if notification.get("retry_count", 0) >= self.max_retries:
                await self._mark_as_failed(notification["id"])
                return False

            # Attempt to send notification
            success = await self._send_notification(notification)
            
            if success:
                await self._mark_as_sent(notification["id"])
                return True
            
            # Schedule retry if sending failed
            await self._schedule_retry(notification)
            return False
                
        except Exception as e:
            await self._mark_as_failed(notification["id"])
            return False

    async def get_user_notifications(
        self,
        user_id: str,
        limit: int = 10,
        skip: int = 0,
        status: NotificationStatus = None
    ) -> List[Notification]:
        """
        Get notifications for a specific user with optional filtering.
        
        Args:
            user_id: ID of the user
            limit: Maximum number of notifications to return
            skip: Number of notifications to skip (for pagination)
            status: Optional status filter
            
        Returns:
            List of Notification objects
            
        Raises:
            HTTPException: If retrieval fails
        """
        try:
            # Build query with optional status filter
            query = {"user_id": user_id}
            if status:
                query["status"] = status
                
            # Execute query with sorting and pagination
            cursor = self.db.notifications.find(query).sort(
                "created_at", -1
            ).skip(skip).limit(limit)
            
            # Convert MongoDB documents to Pydantic models
            notifications = []
            async for doc in cursor:
                notifications.append(Notification(
                    id=doc["id"],
                    user_id=doc["user_id"],
                    title=doc["title"],
                    message=doc["message"],
                    type=doc["type"],
                    status=doc["status"],
                    created_at=doc["created_at"],
                    sent_at=doc.get("sent_at"),
                    failed_at=doc.get("failed_at"),
                    error=doc.get("error"),
                    retry_count=doc.get("retry_count", 0),
                    max_retries=doc.get("max_retries", self.max_retries),
                    metadata=doc.get("metadata", {})
                ))
            
            return notifications
        except Exception as e:
            logger.error(f"Error retrieving notifications: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve notifications"
            )

    async def _send_notification(self, notification: dict) -> bool:
        """
        Send notification based on its type.
        
        Args:
            notification: Dictionary containing notification details
            
        Returns:
            bool: True if notification was sent successfully
        """
        try:
            # Simulate sending delay
            await asyncio.sleep(1)
            notification_type = notification.get("type", "in_app")
            
            # TODO: Implement actual notification sending logic
            # This is a placeholder for future implementation
            logger.info(f"Sending {notification_type} notification to {notification.get('user_id')}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending {notification.get('type')} notification: {str(e)}")
            return False

    async def _schedule_retry(self, notification: dict) -> None:
        """
        Schedule a retry for failed notification with exponential backoff.
        
        Args:
            notification: Dictionary containing notification details
        """
        # Calculate retry count and delay
        retry_count = notification.get("retry_count", 0) + 1
        delay = self.retry_delay * (2 ** retry_count)  # Exponential backoff
        
        # Update notification status
        await self.db.notifications.update_one(
            {"id": notification["id"]},
            {
                "$set": {
                    "retry_count": retry_count,
                    "last_retry": datetime.utcnow(),
                    "status": NotificationStatus.PENDING
                }
            }
        )
        
        # Requeue for processing
        await self.rabbitmq.publish_message(notification)

    async def _mark_as_sent(self, notification_id: str) -> None:
        """
        Mark notification as successfully sent.
        
        Args:
            notification_id: ID of the notification
        """
        await self.db.notifications.update_one(
            {"id": notification_id},
            {
                "$set": {
                    "status": NotificationStatus.SENT,
                    "sent_at": datetime.utcnow()
                }
            }
        )

    async def _mark_as_failed(self, notification_id: str) -> None:
        """
        Mark notification as failed.
        
        Args:
            notification_id: ID of the notification
        """
        await self.db.notifications.update_one(
            {"id": notification_id},
            {
                "$set": {
                    "status": NotificationStatus.FAILED,
                    "failed_at": datetime.utcnow()
                }
            }
        )

    async def update_status(
        self,
        notification_id: str,
        status: NotificationStatus
    ) -> Notification:
        """
        Update notification status.
        
        Args:
            notification_id: ID of the notification
            status: New status value
            
        Returns:
            Updated Notification object
            
        Raises:
            HTTPException: If update fails
        """
        try:
            # Update notification status
            result = await self.db.notifications.update_one(
                {"id": notification_id},
                {
                    "$set": {
                        "status": status,
                        "sent_at": datetime.utcnow() if status == NotificationStatus.SENT else None,
                        "failed_at": datetime.utcnow() if status == NotificationStatus.FAILED else None
                    }
                }
            )
            
            if result.modified_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Notification {notification_id} not found"
                )
            
            # Get updated notification
            notification = await self.get_notification(notification_id)
            if not notification:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Notification {notification_id} not found"
                )
            
            return notification
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating notification {notification_id} status: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update notification status: {str(e)}"
            )

    async def get_notification_stats(self) -> dict:
        """Get detailed notification statistics."""
        pipeline = [
            {
                "$group": {
                    "_id": {
                        "status": "$status",
                        "priority": "$priority"
                    },
                    "count": {"$sum": 1},
                    "avg_retries": {"$avg": "$retry_count"}
                }
            }
        ]
        
        stats = await self.db.notifications.aggregate(pipeline).to_list(length=None)
        
        return {
            "by_status": {
                stat["_id"]["status"]: {
                    "count": stat["count"],
                    "avg_retries": stat["avg_retries"]
                }
                for stat in stats
            },
            "by_priority": {
                stat["_id"]["priority"]: {
                    "count": stat["count"],
                    "avg_retries": stat["avg_retries"]
                }
                for stat in stats
            }
        }

    def _get_priority_value(self, priority: str) -> int:
        """Convert priority string to numeric value."""
        priorities = {
            "high": 1,
            "normal": 2,
            "low": 3
        }
        return priorities.get(priority, 2)

    async def get_notification(self, notification_id: str) -> Optional[Notification]:
        """
        Get a notification by ID.
        
        Args:
            notification_id: ID of the notification
            
        Returns:
            Notification object if found, None otherwise
            
        Raises:
            HTTPException: If retrieval fails
        """
        try:
            notification_doc = await self.db.notifications.find_one({"id": notification_id})
            if not notification_doc:
                return None
                
            return Notification(
                id=notification_doc["id"],
                user_id=notification_doc["user_id"],
                title=notification_doc["title"],
                message=notification_doc["message"],
                type=notification_doc["type"],
                status=notification_doc["status"],
                created_at=notification_doc["created_at"],
                sent_at=notification_doc.get("sent_at"),
                failed_at=notification_doc.get("failed_at"),
                error=notification_doc.get("error"),
                retry_count=notification_doc.get("retry_count", 0),
                max_retries=notification_doc.get("max_retries", self.max_retries),
                metadata=notification_doc.get("metadata", {})
            )
        except Exception as e:
            logger.error(f"Error retrieving notification {notification_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve notification: {str(e)}"
            ) 