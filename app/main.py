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
