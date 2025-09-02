from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging
from app.config import settings
from app.api import auth, tables, reservations, guests, websockets
from app.api import batch, dashboard, atomic, sync

# Configure logging
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="QTable API",
    description="Multi-tenant restaurant table management API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "qtable-api"}

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "QTable API Server",
        "version": "1.0.0",
        "docs": "/docs"
    }

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=404,
        content={"success": False, "message": "Resource not found"}
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error"}
    )

# Include API routers
app.include_router(auth.router)
app.include_router(tables.router)
app.include_router(reservations.router)
app.include_router(guests.router)
app.include_router(websockets.router)
app.include_router(batch.router)  # High-performance batch operations
app.include_router(dashboard.router)  # New /api/v1/dashboard endpoints
app.include_router(dashboard.restaurant_router)  # Original /restaurants/{id}/dashboard-data (compatibility)
app.include_router(atomic.router)  # Enterprise-grade atomic operations
app.include_router(sync.router)  # Full and delta sync endpoints

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 QTable API Server starting up...")
    logger.info(f"📊 Environment: {settings.environment}")
    logger.info(f"🗄️  Database: {settings.database_url[:50]}...")
    
    # Initialize Redis broadcaster for cross-worker WebSocket communication
    try:
        from app.utils.redis_broadcaster import redis_broadcaster
        await redis_broadcaster.initialize_redis()
        logger.info("🔴 Redis broadcaster initialized")
    except Exception as e:
        logger.warning(f"🔴 Redis broadcaster initialization failed: {e}")
        logger.warning("🔴 WebSocket broadcasting will work in single-worker mode only")
    
    # Initialize database on startup
    try:
        from app.database import engine, Base, SessionLocal
        # Import ALL models so they register with Base
        from app.models.user import User
        from app.models.restaurant import Restaurant
        from app.models.table import RestaurantTable
        from app.models.guest import Guest
        from app.models.reservation import Reservation
        from app.utils.security import get_password_hash
        
        logger.info("🔧 Initializing database...")
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created")
        
        # Create admin user if not exists
        db = SessionLocal()
        try:
            admin_user = db.query(User).filter(User.email == "test@restaurant.com").first()
            if not admin_user:
                logger.info("👤 Creating admin user...")
                admin_user = User(
                    email="test@restaurant.com",
                    username="admin",
                    full_name="Test Admin",
                    hashed_password=get_password_hash("password123"),
                    is_admin=True,
                    is_active=True
                )
                db.add(admin_user)
                db.commit()
                logger.info("✅ Admin user created")
            else:
                logger.info("✅ Admin user exists")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Database init failed: {str(e)}")
        import traceback
        traceback.print_exc()
    
# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("👋 QTable API Server shutting down...")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development"
    )
