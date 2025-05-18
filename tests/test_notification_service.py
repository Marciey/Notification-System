import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from app.services.notification_service import NotificationService
from app.models.notification import NotificationCreate, NotificationStatus

@pytest.fixture
def notification_service():
    return NotificationService()

@pytest.fixture
def mock_notification():
    return NotificationCreate(
        id="test-123",
        user_id="user-123",
        title="Test Notification",
        message="This is a test notification",
        priority="high"
    )

@pytest.mark.asyncio
async def test_create_notification(notification_service, mock_notification):
    # Mock database and RabbitMQ
    notification_service.db.notifications.insert_one = Mock()
    notification_service.rabbitmq.publish_message = Mock()
    
    # Create notification
    result = await notification_service.create_notification(mock_notification)
    
    # Verify database insert
    notification_service.db.notifications.insert_one.assert_called_once()
    
    # Verify RabbitMQ publish
    notification_service.rabbitmq.publish_message.assert_called_once()
    
    # Verify result
    assert result["id"] == mock_notification.id
    assert result["status"] == NotificationStatus.PENDING
    assert result["retry_count"] == 0

@pytest.mark.asyncio
async def test_process_notification_success(notification_service):
    # Mock notification
    notification = {
        "id": "test-123",
        "retry_count": 0
    }
    
    # Mock database
    notification_service.db.notifications.update_one = Mock()
    
    # Mock processing
    with patch.object(notification_service, '_process_notification', return_value=True):
        result = await notification_service.process_notification(notification)
        
        # Verify success
        assert result is True
        notification_service.db.notifications.update_one.assert_called_once()

@pytest.mark.asyncio
async def test_process_notification_retry(notification_service):
    # Mock notification
    notification = {
        "id": "test-123",
        "retry_count": 0
    }
    
    # Mock database and RabbitMQ
    notification_service.db.notifications.update_one = Mock()
    notification_service.rabbitmq.publish_message = Mock()
    
    # Mock processing failure
    with patch.object(notification_service, '_process_notification', return_value=False):
        result = await notification_service.process_notification(notification)
        
        # Verify retry
        assert result is False
        assert notification_service.db.notifications.update_one.call_count == 1
        assert notification_service.rabbitmq.publish_message.call_count == 1

@pytest.mark.asyncio
async def test_get_user_notifications(notification_service):
    # Mock notifications
    mock_notifications = [
        {"id": "1", "user_id": "user-123", "status": "sent"},
        {"id": "2", "user_id": "user-123", "status": "pending"}
    ]
    
    # Mock database cursor
    mock_cursor = Mock()
    mock_cursor.to_list = Mock(return_value=mock_notifications)
    notification_service.db.notifications.find = Mock(return_value=mock_cursor)
    
    # Get notifications
    result = await notification_service.get_user_notifications("user-123")
    
    # Verify result
    assert len(result) == 2
    assert result[0]["id"] == "1"
    assert result[1]["id"] == "2"

@pytest.mark.asyncio
async def test_get_notification_stats(notification_service):
    # Mock stats
    mock_stats = [
        {
            "_id": {"status": "sent", "priority": "high"},
            "count": 5,
            "avg_retries": 0.5
        },
        {
            "_id": {"status": "failed", "priority": "normal"},
            "count": 2,
            "avg_retries": 2.0
        }
    ]
    
    # Mock database aggregation
    mock_cursor = Mock()
    mock_cursor.to_list = Mock(return_value=mock_stats)
    notification_service.db.notifications.aggregate = Mock(return_value=mock_cursor)
    
    # Get stats
    result = await notification_service.get_notification_stats()
    
    # Verify result
    assert "by_status" in result
    assert "by_priority" in result
    assert result["by_status"]["sent"]["count"] == 5
    assert result["by_status"]["failed"]["count"] == 2 