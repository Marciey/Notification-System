from aio_pika import connect_robust, Connection, Channel, Queue, Message
from aio_pika.pool import Pool
from loguru import logger
from app.core.config import settings
from typing import Optional, List
import json
import asyncio
from datetime import datetime

class RabbitMQ:
    """
    RabbitMQ connection and message handling manager.
    
    This class manages:
    - Connection to RabbitMQ server
    - Channel pooling for efficient message handling
    - Message batching for better performance
    - Automatic reconnection on connection loss
    - Health monitoring
    """
    
    # Class-level variables for connection and message handling
    connection: Optional[Connection] = None
    channel_pool: Optional[Pool] = None
    queue: Optional[Queue] = None
    _message_batch: List[Message] = []  # Buffer for batched messages
    _batch_lock = asyncio.Lock()  # Lock for thread-safe batch operations
    _batch_task: Optional[asyncio.Task] = None  # Task for processing batches
    _connection_task: Optional[asyncio.Task] = None  # Task for monitoring connection

    @classmethod
    async def connect(cls, max_retries: int = 5, initial_delay: float = 1.0):
        """
        Create RabbitMQ connection and channel pool with retry mechanism.
        
        Args:
            max_retries: Maximum number of connection attempts
            initial_delay: Initial delay between retries in seconds
        """
        retry_count = 0
        delay = initial_delay

        while retry_count < max_retries:
            try:
                # Establish connection with automatic reconnection
                cls.connection = await connect_robust(
                    settings.RABBITMQ_URL,
                    timeout=30,
                    reconnect_interval=5
                )
                
                # Create channel pool for efficient message handling
                cls.channel_pool = Pool(cls.get_channel, max_size=10)
                
                # Set up queue and channel settings
                async with cls.channel_pool.acquire() as channel:
                    cls.queue = await channel.declare_queue(
                        settings.RABBITMQ_QUEUE_NAME,
                        durable=True  # Queue survives broker restart
                    )
                    await channel.set_qos(prefetch_count=settings.RABBITMQ_PREFETCH_COUNT)
                
                # Start background tasks
                cls._batch_task = asyncio.create_task(cls._process_batch())
                cls._connection_task = asyncio.create_task(cls._monitor_connection())
                logger.info("Connected to RabbitMQ")
                return
            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    logger.error(f"Could not connect to RabbitMQ after {max_retries} attempts: {e}")
                    raise
                
                logger.warning(f"Failed to connect to RabbitMQ (attempt {retry_count}/{max_retries}): {e}")
                logger.info(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)  # Exponential backoff with max delay

    @classmethod
    async def _monitor_connection(cls):
        """
        Monitor RabbitMQ connection and reconnect if needed.
        
        This method runs in the background and ensures the connection stays alive.
        """
        while True:
            try:
                if not cls.connection or cls.connection.is_closed:
                    logger.warning("RabbitMQ connection lost, attempting to reconnect...")
                    await cls.connect()
                await asyncio.sleep(5)  # Check connection every 5 seconds
            except Exception as e:
                logger.error(f"Error in connection monitor: {e}")
                await asyncio.sleep(5)

    @classmethod
    async def get_channel(cls) -> Channel:
        """
        Get a channel from the connection.
        
        Returns:
            Channel: RabbitMQ channel for message operations
            
        Raises:
            RuntimeError: If RabbitMQ is not initialized
        """
        if not cls.connection:
            raise RuntimeError("RabbitMQ not initialized")
        return await cls.connection.channel()

    @classmethod
    async def publish_message(cls, message: dict):
        """
        Publish a message to RabbitMQ with batching.
        
        Args:
            message: Dictionary containing message data
        """
        async with cls._batch_lock:
            # Create message with metadata
            cls._message_batch.append(
                Message(
                    body=json.dumps(message, default=str).encode(),
                    content_type="application/json",
                    timestamp=datetime.utcnow().timestamp()
                )
            )
            # Publish batch if size threshold reached
            if len(cls._message_batch) >= settings.RABBITMQ_BATCH_SIZE:
                await cls._publish_batch()

    @classmethod
    async def _process_batch(cls):
        """
        Process message batch periodically.
        
        This method runs in the background and ensures messages are published
        even if the batch size threshold is not reached.
        """
        while True:
            await asyncio.sleep(settings.RABBITMQ_BATCH_TIMEOUT)
            async with cls._batch_lock:
                if cls._message_batch:
                    await cls._publish_batch()

    @classmethod
    async def _publish_batch(cls):
        """
        Publish a batch of messages with retry logic.
        
        This method handles the actual publishing of messages to RabbitMQ
        with automatic retries on failure.
        """
        if not cls._message_batch:
            return
        max_retries = 3
        retry_delay = 1
        for message in cls._message_batch:
            for attempt in range(1, max_retries + 1):
                try:
                    async with cls.channel_pool.acquire() as channel:
                        await channel.default_exchange.publish(
                            message,
                            routing_key=settings.RABBITMQ_QUEUE_NAME
                        )
                    break
                except Exception as e:
                    logger.error(f"Failed to publish message (attempt {attempt}): {e}")
                    if attempt == max_retries:
                        logger.error(f"Giving up on message after {max_retries} attempts")
                    else:
                        await asyncio.sleep(retry_delay)
        cls._message_batch.clear()

    @classmethod
    async def close(cls):
        """
        Close RabbitMQ connection and cleanup tasks.
        
        This method ensures proper cleanup of resources when shutting down.
        """
        if cls._batch_task:
            cls._batch_task.cancel()
            try:
                await cls._batch_task
            except asyncio.CancelledError:
                pass
        
        if cls._connection_task:
            cls._connection_task.cancel()
            try:
                await cls._connection_task
            except asyncio.CancelledError:
                pass
        
        if cls.connection:
            await cls.connection.close()
            logger.info("Closed RabbitMQ connection")

    @classmethod
    async def check_connection(cls) -> bool:
        """
        Check if RabbitMQ connection is alive.
        
        Returns:
            bool: True if connection is active and working
        """
        try:
            if not cls.connection or cls.connection.is_closed:
                return False
            async with cls.channel_pool.acquire() as channel:
                await channel.declare_queue("health_check", auto_delete=True)
            return True
        except Exception as e:
            logger.error(f"RabbitMQ health check failed: {e}")
            return False

async def init_rabbitmq():
    """Initialize RabbitMQ connection."""
    await RabbitMQ.connect()

async def close_rabbitmq():
    """Close RabbitMQ connection."""
    await RabbitMQ.close()

async def get_rabbitmq_channel() -> Channel:
    """
    Get a RabbitMQ channel from the pool.
    
    Returns:
        Channel: RabbitMQ channel for message operations
        
    Raises:
        RuntimeError: If RabbitMQ is not initialized
    """
    if not RabbitMQ.channel_pool:
        raise RuntimeError("RabbitMQ not initialized")
    return await RabbitMQ.channel_pool.acquire() 