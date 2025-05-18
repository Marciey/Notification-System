# Notification System

A robust, scalable notification system built with FastAPI, MongoDB, and RabbitMQ. This system provides a reliable way to send and manage notifications across multiple channels.

## Features

- **Multi-channel Support**: Send notifications through email, SMS, and in-app channels
- **Reliable Delivery**: Built-in retry mechanism with exponential backoff
- **Real-time Processing**: Asynchronous processing using RabbitMQ
- **Scalable Storage**: MongoDB for persistent storage
- **RESTful API**: Clean and well-documented API endpoints
- **Health Monitoring**: Built-in health checks for all components
- **Pagination Support**: Efficient retrieval of notifications with pagination
- **Status Tracking**: Comprehensive notification status tracking
- **Error Handling**: Robust error handling and logging

## API Endpoints

### Notifications

- `POST /api/v1/notifications` - Create a new notification
- `GET /api/v1/notifications/{notification_id}` - Get a specific notification
- `GET /api/v1/users/{user_id}/notifications` - Get user notifications
- `PATCH /api/v1/notifications/{notification_id}/status` - Update notification status
- `GET /api/v1/health` - Check system health

### Request/Response Examples

#### Create Notification

```json
POST /api/v1/notifications
{
    "user_id": "user123",
    "title": "Welcome!",
    "message": "Welcome to our platform",
    "type": "email",
    "metadata": {
        "priority": "high",
        "category": "welcome"
    }
}
```

#### Get User Notifications

## Setup

1. **Prerequisites**

   - Docker
   - Docker Compose
   

3. **Running with Docker**

   **Development mode:**

   ```bash
   # Start all services
   docker-compose up --build

   # View logs
   docker-compose logs -f app        # Application logs
   docker-compose logs -f mongodb    # MongoDB logs
   docker-compose logs -f rabbitmq   # RabbitMQ logs
   ```

   **Production mode:**

   ```bash
   # Start all services in production mode
   docker-compose -f docker-compose.prod.yml up --build
   ```

4. **Accessing Services**

   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - RabbitMQ Management: http://localhost:15672 (guest/guest)

## Architecture

The system consists of several key components:

1. **API Layer** (FastAPI)
    - Handles HTTP requests
    - Input validation
    - Response serialization

2. **Service Layer**
    - Business logic
    - Notification processing
    - Retry mechanism

3. **Message Queue** (RabbitMQ)
    - Asynchronous processing
    - Message persistence
    - Load balancing

4. **Database** (MongoDB)
    - Notification storage
    - Status tracking
    - Analytics data


### Testing

```bash
# Run tests in Docker
docker-compose run --rm app pytest

# Run tests with coverage
docker-compose run --rm app pytest --cov=app tests/
```

## Error Handling

The system implements comprehensive error handling:

- Input validation using Pydantic models
- Proper HTTP status codes
- Detailed error messages
- Logging for debugging


## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request


This project is licensed under the MIT License - see the LICENSE file for details.
