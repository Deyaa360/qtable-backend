# QTable Backend API 🚀

Enterprise-grade restaurant table management API with real-time synchronization, atomic operations, and multi-device support.

## Features ✨

- **Real-time synchronization** - WebSocket-based live updates across all devices
- **Atomic operations** - ACID-compliant transactions for data integrity
- **Enterprise reliability** - Industry-standard error handling and recovery
- **Multi-device support** - Seamless synchronization across iOS, web, and other platforms
- **Walk-in guest management** - Complete lifecycle from check-in to seating
- **Table management** - Real-time status updates and availability tracking
- **Production ready** - Optimized for deployment and monitoring

## Quick Start 🏃‍♂️

### 1. Installation

```bash
# Clone repository
git clone <repository-url>
cd qtable-backend

# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your settings
# DATABASE_URL=sqlite:///./qtable.db (default)
# SECRET_KEY=your-secret-key
```

### 3. Database Setup

```bash
# Initialize database
alembic upgrade head

```

### 4. Start Server

```bash
# Development
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Server runs at: `http://localhost:8000`

## API Documentation 📚

- **Interactive API Docs**: `http://localhost:8000/docs`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

## Real-time Features 🔄

### WebSocket Endpoints

1. **General Real-time**: `ws://localhost:8000/realtime`
2. **Restaurant Sync**: `ws://localhost:8000/ws/restaurant/sync`

### Message Format

```json
{
  "type": "guest_updated|table_updated|reservation_updated",
  "data": { /* entity data */ },
  "timestamp": "2024-01-01T00:00:00Z",
  "restaurant_id": 1
}
```

### Heartbeat

- **Ping interval**: 30 seconds
- **Connection timeout**: 5 minutes
- **Auto-reconnect**: Client responsibility

## Core Endpoints 🛠️

### Guest Management
- `POST /api/guests/` - Create walk-in guest
- `GET /api/guests/` - List all guests
- `PUT /api/guests/{id}/status/atomic` - Update status atomically
- `DELETE /api/guests/{id}` - Remove guest

### Table Management  
- `GET /api/tables/` - List all tables
- `PUT /api/tables/{id}` - Update table status
- `POST /api/tables/` - Create new table

### Reservations
- `GET /api/reservations/` - List reservations
- `POST /api/reservations/` - Create reservation
- `PUT /api/reservations/{id}` - Update reservation

### Atomic Operations
- `POST /api/atomic/batch` - Execute atomic batch operations

### Sync API
- `GET /api/sync/full` - Full data sync
- `GET /api/sync/delta` - Delta sync since timestamp
- `POST /api/sync/batch` - Batch data updates

## Production Deployment 🚀

### Environment Variables

```bash
DATABASE_URL=sqlite:///./qtable.db
SECRET_KEY=your-production-secret-key
ENVIRONMENT=production
WS_HEARTBEAT_INTERVAL=30
WS_CONNECTION_TIMEOUT=300
LOG_LEVEL=INFO
```

### Security Checklist

- [ ] Change default SECRET_KEY
- [ ] Use HTTPS in production
- [ ] Configure CORS properly
- [ ] Set up monitoring
- [ ] Enable logging
- [ ] Regular database backups

## Architecture 🏗️

### Database Schema
- **Guests**: Walk-in guest management
- **Tables**: Restaurant table inventory
- **Reservations**: Reservation system
- **Activity Log**: Audit trail

### Real-time Sync
- WebSocket connections for live updates
- Atomic operations ensure data consistency
- Automatic broadcasting to all connected clients
- iOS-compatible message format

### Error Handling
- Comprehensive exception handling
- Automatic rollback on failures
- Detailed error logging
- Graceful degradation
## Support �

For questions or issues:
- Check the API documentation at `/docs`
- Review error logs for debugging
- Ensure all environment variables are configured
- Verify database connectivity

## License �

This project is proprietary software. All rights reserved.

## Production Deployment 🚀

### Railway
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Multi-Tenancy 🏢

The API uses PostgreSQL Row Level Security for data isolation:

- Every table has `restaurant_id` column
- RLS policies automatically filter by restaurant
- JWT tokens contain `restaurant_id`
- Database context is set per request

## Security 🔒

- **JWT Authentication** with configurable expiration
- **Password hashing** with bcrypt
- **Row Level Security** for multi-tenancy
- **CORS** protection
- **Input validation** with Pydantic

## Monitoring 📊

- **Health check:** `/health`
- **API docs:** `/docs`
- **Activity logging** for all operations
- **Error handling** with proper HTTP status codes

## Support 💬

For questions or issues:
1. Check the API documentation at `/docs`
2. Review the technical specifications
3. Check the activity logs for debugging

---

**Ready to power restaurant operations! 🍽️**
