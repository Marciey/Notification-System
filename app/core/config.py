from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List

class Settings(BaseSettings):
    """Application settings."""
    
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Notification Service"
    
    # MongoDB Settings
    MONGODB_URL: str = "mongodb://mongodb:27017"
    MONGODB_DB: str = "notification_service"
    
    # RabbitMQ Settings
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    RABBITMQ_QUEUE_NAME: str = "notifications"
    RABBITMQ_PREFETCH_COUNT: int = 10
    RABBITMQ_BATCH_SIZE: int = 10
    RABBITMQ_BATCH_TIMEOUT: int = 5  # seconds
    
    # CORS settings
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings() 