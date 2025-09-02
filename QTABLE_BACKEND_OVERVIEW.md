# QTable Backend - System Overview

## 🎯 Project Overview

QTable is a **real-time restaurant table management system** built with FastAPI, featuring multi-worker WebSocket broadcasting, comprehensive CRUD operations, and production-ready deployment on Railway. The system enables restaurant staff to manage guests, tables, and reservations with instant updates across all connected devices.

## 🏗️ Architecture

### Core Technologies
- **FastAPI** - Modern Python web framework with automatic API documentation
- **PostgreSQL** - Primary database for persistent data storage
- **Redis** - Pub/sub messaging for cross-worker WebSocket communication
- **Railway** - Cloud deployment platform with auto-scaling
- **Gunicorn + Uvicorn** - Production ASGI server setup
- **WebSockets** - Real-time bidirectional communication with iOS clients

### Multi-Worker Architecture
The application runs on **4 Gunicorn workers** in production, with Redis enabling seamless communication:
- **Worker Distribution**: API requests are load-balanced across workers
- **WebSocket Connections**: Can connect to any worker
- **Cross-Worker Broadcasting**: Redis pub/sub ensures all workers receive real-time updates
- **Zero Message Loss**: Updates reach all connected clients regardless of worker distribution

## 📁 Project Structure

```
qtable-backend/
├── app/
│   ├── api/                    # API route modules
│   │   ├── auth.py            # Authentication & authorization
│   │   ├── guests.py          # Guest management endpoints
│   │   ├── tables.py          # Table management endpoints
│   │   ├── reservations.py    # Reservation system
│   │   ├── websockets.py      # WebSocket real-time connections
│   │   ├── batch.py           # High-performance batch operations
│   │   ├── dashboard.py       # Dashboard data aggregation
│   │   ├── atomic.py          # Atomic transaction operations
│   │   └── sync.py            # Data synchronization endpoints
│   │
│   ├── models/                # SQLAlchemy ORM models
│   │   ├── user.py           # User authentication model
│   │   ├── restaurant.py     # Restaurant entity model
│   │   ├── guest.py          # Guest/customer model
│   │   ├── table.py          # Restaurant table model
│   │   └── reservation.py    # Reservation booking model
│   │
│   ├── utils/                 # Utility modules
│   │   ├── redis_broadcaster.py    # Redis-based real-time broadcasting
│   │   ├── websocket_manager.py    # WebSocket connection management
│   │   ├── security.py            # Authentication & password handling
│   │   └── database.py            # Database connection & session management
│   │
│   ├── config.py             # Application configuration
│   ├── database.py           # Database setup & initialization
│   ├── dependencies.py       # FastAPI dependency injection
│   └── main.py              # Application entry point
│
├── requirements.txt          # Python dependencies
├── Procfile                 # Railway deployment configuration
└── README.md               # Project documentation
```

## 🔧 Core Features

### 1. Real-Time WebSocket Broadcasting
- **Multi-Worker Support**: Redis pub/sub enables broadcasting across all Gunicorn workers
- **Restaurant-Specific Channels**: Isolated real-time updates per restaurant
- **Message Types**: guest_created, guest_updated, table_updated, atomic_transaction_complete
- **Automatic Reconnection**: Robust WebSocket connection management
- **iOS-Compatible Format**: Structured JSON messages matching mobile app requirements

### 2. Guest Management
- **Complete CRUD Operations**: Create, read, update, delete guests
- **Status Tracking**: waiting, seated, completed
- **Table Assignment**: Link guests to specific tables
- **Batch Operations**: High-performance bulk updates
- **Search & Filtering**: Find guests by name, status, or table

### 3. Table Management
- **Dynamic Table Layout**: Configurable table positions and shapes
- **Status Management**: available, occupied, reserved, out_of_service
- **Capacity Tracking**: Party size validation
- **Visual Representation**: X/Y coordinates for restaurant floor plans
- **Section Organization**: Group tables by restaurant areas

### 4. Batch Processing
- **Atomic Transactions**: Ensure data consistency across multiple operations
- **High Performance**: Optimized bulk operations for busy restaurants
- **Real-Time Broadcasting**: Instant updates for all batch changes
- **Error Handling**: Rollback on failure to maintain data integrity

### 5. Authentication & Security
- **JWT Token Authentication**: Secure API access
- **Password Hashing**: bcrypt for secure password storage
- **Admin User Management**: Role-based access control
- **CORS Configuration**: Cross-origin request handling for web clients

## 🌐 API Endpoints

### Authentication
- `POST /auth/login` - User authentication
- `POST /auth/register` - User registration
- `GET /auth/me` - Current user information

### Guests
- `GET /restaurants/{id}/guests` - List all guests
- `POST /restaurants/{id}/guests` - Create new guest
- `PUT /restaurants/{id}/guests/{guest_id}` - Update guest
- `DELETE /restaurants/{id}/guests/{guest_id}` - Delete guest

### Tables
- `GET /restaurants/{id}/tables` - List all tables
- `POST /restaurants/{id}/tables` - Create new table
- `PUT /restaurants/{id}/tables/{table_id}` - Update table
- `DELETE /restaurants/{id}/tables/{table_id}` - Delete table

### Real-Time
- `WebSocket /realtime?restaurant_id={id}` - Real-time updates
- `POST /restaurants/{id}/batch-update` - Batch operations with broadcasting

### Dashboard
- `GET /api/v1/dashboard/{restaurant_id}` - Aggregated dashboard data
- `GET /restaurants/{id}/dashboard-data` - Legacy dashboard endpoint

## 🚀 Deployment Architecture

### Railway Configuration
- **Auto-Scaling**: 4 Gunicorn workers with Uvicorn ASGI
- **Environment Variables**: Secure configuration management
- **Database**: Managed PostgreSQL with automatic backups
- **Redis**: Managed Redis instance for pub/sub messaging
- **Health Checks**: Automated monitoring and restart capabilities

### Environment Variables
```bash
DATABASE_URL=postgresql://...      # PostgreSQL connection
REDIS_URL=redis://...             # Redis connection for pub/sub
SECRET_KEY=...                    # JWT token signing
ADMIN_EMAIL=test@restaurant.com   # Default admin user
ADMIN_PASSWORD=password123        # Default admin password
ENVIRONMENT=production            # Runtime environment
LOG_LEVEL=INFO                   # Logging verbosity
```

### Production Settings
- **CORS Origins**: Configured for production domains
- **Security Headers**: HTTPS enforcement and security policies
- **Database Pooling**: Optimized connection management
- **Error Handling**: Structured error responses and logging
- **Performance Monitoring**: Request/response timing and metrics

## 🔄 Real-Time Data Flow

### WebSocket Message Flow
1. **Client Connection**: iOS app connects to WebSocket endpoint
2. **Worker Assignment**: Connection handled by any available worker
3. **Channel Subscription**: Worker subscribes to restaurant-specific Redis channel
4. **Data Change**: API request modifies database (on any worker)
5. **Redis Broadcast**: Change published to Redis channel
6. **Cross-Worker Delivery**: All workers receive message via Redis pub/sub
7. **Client Update**: Workers with connections forward message to iOS clients
8. **Instant Sync**: All connected devices receive update simultaneously

### Message Format
```json
{
  "type": "guest_updated",
  "restaurant_id": "382926a9-84f3-45e1-9cb3-26db4ef09a53",
  "guest_id": "7405ffbf-498b-48d3-944a-9e35cc7c1c69",
  "action": "status_changed",
  "timestamp": "2025-09-02T06:03:11.039837Z",
  "data": {
    "id": "7405ffbf-498b-48d3-944a-9e35cc7c1c69",
    "guestName": "John Doe",
    "status": "seated",
    "tableId": "f9174969-1ab8-43f0-9a2b-eb1099990b4b",
    "partySize": 4
  }
}
```

## 🛡️ Error Handling & Reliability

### Database Reliability
- **Connection Pooling**: Efficient database connection management
- **Transaction Isolation**: ACID compliance for data consistency
- **Automatic Reconnection**: Database failover handling
- **Migration Support**: Schema evolution capabilities

### Redis Fallback
- **Graceful Degradation**: Falls back to single-worker mode if Redis unavailable
- **Connection Retry**: Automatic Redis reconnection attempts
- **Error Logging**: Comprehensive Redis connection monitoring
- **Performance Metrics**: Redis pub/sub latency tracking

### WebSocket Resilience
- **Connection Cleanup**: Automatic cleanup of disconnected clients
- **Heartbeat Monitoring**: Connection health checks
- **Graceful Shutdown**: Proper WebSocket closure handling
- **Error Recovery**: Robust error handling for network issues

## 📊 Monitoring & Logging

### Structured Logging
- **Worker Identification**: Each log entry tagged with worker ID
- **Request Tracing**: Complete request/response lifecycle tracking
- **Performance Metrics**: API response times and database query performance
- **Error Aggregation**: Centralized error reporting and analysis

### Health Monitoring
- **Health Check Endpoint**: `/health` for load balancer monitoring
- **Database Status**: Connection and query health verification
- **Redis Status**: Pub/sub system health monitoring
- **Worker Status**: Individual worker health and performance

## 🔮 Future Enhancements

### Planned Features
- **Analytics Dashboard**: Advanced reporting and insights
- **Multi-Restaurant Support**: Enhanced tenant isolation
- **Reservation System**: Advanced booking and scheduling
- **Integration APIs**: Third-party service integrations
- **Mobile Push Notifications**: Enhanced real-time capabilities

### Scalability Improvements
- **Database Sharding**: Horizontal scaling for large deployments
- **Redis Clustering**: Enhanced pub/sub performance
- **CDN Integration**: Static asset optimization
- **Caching Layer**: Redis-based application caching

## 🎯 Key Benefits

1. **Real-Time Performance**: Instant updates across all connected devices
2. **Production Ready**: Robust multi-worker deployment with fallback strategies
3. **Scalable Architecture**: Handles multiple restaurants and concurrent users
4. **Modern Technology Stack**: FastAPI, PostgreSQL, Redis for optimal performance
5. **Comprehensive API**: Full CRUD operations with real-time broadcasting
6. **iOS Integration**: Structured data format optimized for mobile consumption
7. **Cloud Native**: Railway deployment with managed services and auto-scaling

---

*This QTable backend system provides a solid foundation for restaurant management with real-time capabilities, designed for production use with comprehensive error handling and monitoring.*
