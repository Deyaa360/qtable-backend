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
    
    # Create database tables first
    try:
        from app.database import engine
        from app.models import Base
        
        logger.info("🗄️  Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to create database tables: {str(e)}")
        # Don't stop the server, but log the error
    
    # Create admin user and restaurant if they don't exist
    try:
        from app.database import get_db
        from app.models import User, Restaurant
        from app.utils.security import get_password_hash
        
        db = next(get_db())
        
        # Check if admin user exists
        admin_email = "test@restaurant.com"
        existing_admin = db.query(User).filter(User.email == admin_email).first()
        
        if not existing_admin:
            logger.info("🔧 Creating admin user and restaurant...")
            
            # Create restaurant first
            restaurant = Restaurant(
                name="QTable Restaurant",
                slug="qtable-restaurant",
                address="123 Restaurant Street, City, State"
            )
            db.add(restaurant)
            db.flush()  # Get the restaurant ID
            
            # Create admin user
            admin_user = User(
                email=admin_email,
                hashed_password=get_password_hash("password123"),
                full_name="Restaurant Admin",
                role="admin",
                restaurant_id=restaurant.id
            )
            db.add(admin_user)
            db.commit()
            
            logger.info(f"✅ Admin user created: {admin_email}")
            logger.info(f"✅ Restaurant created: {restaurant.name} (ID: {restaurant.id})")
        else:
            logger.info(f"✅ Admin user already exists: {admin_email}")
            
        db.close()
    except Exception as e:
        logger.error(f"❌ Failed to create admin user: {str(e)}")
        # Don't stop the server if admin creation fails
    
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
