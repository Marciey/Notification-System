from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger
from app.core.config import settings
from typing import Optional
import asyncio

class MongoDB:
    """
    MongoDB connection and database operations manager.
    
    This class manages:
    - Connection to MongoDB server
    - Database operations with retry logic
    - Index creation for performance optimization
    - Connection health monitoring
    """
    
    # Class-level variables for database connection
    client: Optional[AsyncIOMotorClient] = None
    db = None

    @classmethod
    async def connect_to_database(cls, max_retries: int = 3):
        """
        Create database connection with retry logic.
        
        Args:
            max_retries: Maximum number of connection attempts
            
        Raises:
            Exception: If connection fails after all retries
        """
        for attempt in range(max_retries):
            try:
                # Initialize MongoDB client with connection settings
                cls.client = AsyncIOMotorClient(
                    settings.MONGODB_URL,
                    serverSelectionTimeoutMS=5000,  # Timeout for server selection
                    connectTimeoutMS=5000,          # Timeout for connection
                    socketTimeoutMS=5000            # Timeout for operations
                )
                cls.db = cls.client[settings.MONGODB_DB]
                
                # Test connection and create indexes
                await cls.client.admin.command('ping')
                await cls.create_indexes()
                logger.info("Connected to MongoDB")
                return
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(1)  # Wait before retry

    @classmethod
    async def close_database_connection(cls):
        """Close database connection and cleanup resources."""
        if cls.client:
            cls.client.close()
            logger.info("Closed MongoDB connection")

    @classmethod
    async def check_connection(cls) -> bool:
        """
        Check if database connection is alive.
        
        Returns:
            bool: True if connection is active and working
        """
        try:
            if not cls.client:
                return False
            await cls.client.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False

    @classmethod
    async def create_indexes(cls):
        """
        Create necessary indexes for better performance.
        
        Creates indexes for:
        - User notifications (user_id + created_at)
        - Notification status
        - Notification priority
        - Notification category
        - Notification type
        - User email (unique)
        - User phone
        
        Raises:
            Exception: If index creation fails
        """
        try:
            # Notification indexes for efficient querying
            await cls.db.notifications.create_index(
                [("user_id", 1), ("created_at", -1)],  # Compound index for user notifications
                background=True  # Create index in background
            )
            await cls.db.notifications.create_index(
                [("status", 1)],  # Index for status filtering
                background=True
            )
            await cls.db.notifications.create_index(
                [("metadata.priority", 1)],  # Index for priority-based queries
                background=True
            )
            await cls.db.notifications.create_index(
                [("metadata.category", 1)],  # Index for category filtering
                background=True
            )
            await cls.db.notifications.create_index(
                [("type", 1)],  # Index for notification type
                background=True
            )
            
            # User indexes
            try:
                await cls.db.users.create_index(
                    [("email", 1)],
                    unique=True,  # Ensure email uniqueness
                    background=True
                )
            except Exception as e:
                logger.warning(f"Could not create unique email index: {e}")
            
            await cls.db.users.create_index(
                [("phone", 1)],  # Index for phone number lookups
                background=True
            )
            logger.info("Created MongoDB indexes")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
            raise

def get_database():
    """
    Get database instance with proper error handling.
    
    Returns:
        Database: MongoDB database instance
        
    Raises:
        RuntimeError: If database is not initialized or connection is dead
    """
    if not MongoDB.db:
        raise RuntimeError("Database not initialized. Call connect_to_database first.")
    if not MongoDB.check_connection():
        raise RuntimeError("Database connection is not alive")
    return MongoDB.db

async def init_mongodb():
    """Initialize MongoDB connection."""
    await MongoDB.connect_to_database()

async def close_mongodb():
    """Close MongoDB connection."""
    await MongoDB.close_database_connection() 