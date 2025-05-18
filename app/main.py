from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.v1.api import api_router
from app.core.mongodb import MongoDB
from app.core.rabbitmq import RabbitMQ
import logging
from app.routers import notifications

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="A simple notification service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Add CORS middleware with proper configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,  # Configure in settings
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error handler caught: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "message": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An unexpected error occurred"
        }
    )

# Startup events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    try:
        # Connect to MongoDB
        await MongoDB.connect_to_database()
        logger.info("Connected to MongoDB")

        # Connect to RabbitMQ
        await RabbitMQ.connect()
        logger.info("Connected to RabbitMQ")

    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise

# Shutdown events
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    try:
        # Close MongoDB connection
        await MongoDB.close_database_connection()
        logger.info("Closed MongoDB connection")

        # Close RabbitMQ connection
        await RabbitMQ.close()
        logger.info("Closed RabbitMQ connection")

    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Include routers
app.include_router(notifications.router)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to the Notification Service",
        "docs_url": "/docs",
        "health_check": "/api/v1/health"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check MongoDB connection
        db_status = await MongoDB.check_connection()
        
        # Check RabbitMQ connection
        rabbitmq_status = await RabbitMQ.check_connection()
        
        return {
            "status": "healthy" if db_status and rabbitmq_status else "unhealthy",
            "database": "connected" if db_status else "disconnected",
            "rabbitmq": "connected" if rabbitmq_status else "disconnected",
            "version": app.version
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e) if settings.DEBUG else "Health check failed"
        } 