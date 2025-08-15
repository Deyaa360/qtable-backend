# QTable Backend API 🚀

Multi-tenant restaurant table management API server built with FastAPI, PostgreSQL, and WebSockets for real-time updates.

## Features ✨

- **Multi-tenant architecture** with Row Level Security
- **Real-time updates** via WebSockets
- **JWT authentication** with role-based access
- **RESTful API** matching iOS app models exactly
- **Database migrations** with Alembic
- **Production ready** with proper error handling

## Quick Start 🏃‍♂️

### 1. Environment Setup

```bash
# Clone and navigate to project
cd qtable-backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Database Setup

#### Option A: Railway (Recommended for Production)
1. Sign up at [Railway.app](https://railway.app)
2. Create new project → Add PostgreSQL
3. Copy connection string
4. Add to `.env` file

#### Option B: Local PostgreSQL
```bash
# Install PostgreSQL locally
# Create database
createdb qtable_db

# Set environment variables
DATABASE_URL=postgresql://postgres:password@localhost:5432/qtable_db
```

### 3. Environment Variables

Create `.env` file:
```bash
cp .env.example .env
```

Update `.env` with your values:
```bash
DATABASE_URL=postgresql://username:password@host:port/database
SECRET_KEY=your-super-secret-key-here
REDIS_URL=redis://localhost:6379
ENVIRONMENT=development
```

### 4. Database Migration

```bash
# Initialize Alembic (first time only)
alembic init alembic

# Create initial migration
alembic revision --autogenerate -m "Initial migration"

# Run migrations
alembic upgrade head
```

### 5. Run the Server

```bash
# Development server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Server will be available at:
- **API:** http://localhost:8000
- **Docs:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## API Endpoints 📡

### Authentication
```http
POST /auth/login          # Staff login
POST /auth/register       # Restaurant signup
GET  /auth/me            # Current user info
```

### Tables (Floor Plan)
```http
GET    /restaurants/{id}/tables           # Get all tables
PUT    /restaurants/{id}/tables/{table_id} # Update table
POST   /restaurants/{id}/tables           # Create table
DELETE /restaurants/{id}/tables/{table_id} # Delete table
```

### Reservations
```http
GET    /restaurants/{id}/reservations      # List reservations
POST   /restaurants/{id}/reservations      # Create reservation
PUT    /restaurants/{id}/reservations/{id} # Update reservation
DELETE /restaurants/{id}/reservations/{id} # Cancel reservation
```

### WebSocket
```http
WS /restaurants/{id}/live    # Real-time updates
```

## Example Usage 💡

### 1. Register Restaurant
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "restaurant_name": "Pizza Palace",
    "email": "owner@pizzapalace.com",
    "password": "password123",
    "first_name": "John",
    "last_name": "Doe"
  }'
```

### 2. Login
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "owner@pizzapalace.com",
    "password": "password123"
  }'
```

### 3. Get Tables (with JWT token)
```bash
curl -X GET "http://localhost:8000/restaurants/{restaurant_id}/tables" \
  -H "Authorization: Bearer {your_jwt_token}"
```

### 4. Update Table Status
```bash
curl -X PUT "http://localhost:8000/restaurants/{restaurant_id}/tables/{table_id}" \
  -H "Authorization: Bearer {your_jwt_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "occupied",
    "currentGuestId": "reservation_uuid"
  }'
```

## Data Models 📊

The API exactly matches the iOS app models:

### Table Response
```json
{
  "id": "uuid",
  "tableNumber": "A1",
  "capacity": 4,
  "status": "available",
  "position": {"x": 0.2, "y": 0.3},
  "shape": "round",
  "section": "Main Dining",
  "currentGuestId": null,
  "lastUpdated": "2025-08-13T10:30:00Z",
  "createdAt": "2025-08-01T09:00:00Z"
}
```

### Reservation Response
```json
{
  "id": "uuid",
  "guestName": "John Smith",
  "partySize": 4,
  "status": "seated",
  "reservationTime": "2025-08-13T19:00:00Z",
  "checkInTime": "2025-08-13T18:55:00Z",
  "seatedTime": "2025-08-13T19:05:00Z",
  "assignedTableId": "table_uuid",
  "contactInfo": "+1234567890",
  "notes": "Birthday celebration",
  "createdAt": "2025-08-13T18:55:00Z",
  "lastUpdated": "2025-08-13T19:05:00Z"
}
```

## WebSocket Events 📡

### Table Update
```json
{
  "type": "table_update",
  "data": {TableResponse},
  "timestamp": "2025-08-13T19:05:00Z",
  "restaurant_id": "uuid"
}
```

### Reservation Update
```json
{
  "type": "reservation_update",
  "data": {ReservationResponse},
  "timestamp": "2025-08-13T19:05:00Z",
  "restaurant_id": "uuid"
}
```

## Development 🛠

### Project Structure
```
qtable-backend/
├── app/
│   ├── api/           # API routes
│   ├── models/        # SQLAlchemy models
│   ├── schemas/       # Pydantic schemas
│   ├── services/      # Business logic
│   ├── utils/         # Utilities
│   ├── main.py        # FastAPI app
│   ├── config.py      # Settings
│   └── database.py    # DB connection
├── alembic/           # DB migrations
├── requirements.txt
└── .env              # Environment variables
```

### Adding New Features

1. **Add Model:** Create SQLAlchemy model in `app/models/`
2. **Add Schema:** Create Pydantic schema in `app/schemas/`
3. **Add API:** Create router in `app/api/`
4. **Add Migration:** `alembic revision --autogenerate -m "description"`
5. **Run Migration:** `alembic upgrade head`

### Testing
```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest
```

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
