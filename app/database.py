from sqlalchemy import create_engine, MetaData, text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool, QueuePool
from app.config import settings

# Create database engine with optimized connection pooling
if "sqlite" in settings.database_url:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        echo=settings.environment == "development",
        # SQLite optimization
        poolclass=StaticPool,
        pool_pre_ping=True,
        pool_recycle=300
    )
else:
    # PostgreSQL/MySQL optimizations
    engine = create_engine(
        settings.database_url,
        # Connection pooling for production
        poolclass=QueuePool,
        pool_size=20,
        max_overflow=30,
        pool_pre_ping=True,
        pool_recycle=300,
        echo=settings.environment == "development"
    )

# Create session factory with optimized settings
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine,
    # Performance optimization
    expire_on_commit=False
)

# Create base class for models
Base = declarative_base()

# Custom metadata for multi-tenant setup
metadata = MetaData()

def get_db():
    """Database dependency for FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def set_restaurant_context(db, restaurant_id: str):
    """Set the restaurant context for Row Level Security (PostgreSQL only)"""
    if "postgresql" in settings.database_url:
        db.execute(text(f"SET app.current_restaurant_id = '{restaurant_id}'"))

def create_performance_indexes():
    """Create database indexes for performance optimization"""
    from app.models import Guest, RestaurantTable, Restaurant, User
    
    # Critical indexes for performance
    indexes = [
        # Restaurant-based queries (most common)
        Index('idx_guest_restaurant_id', Guest.restaurant_id),
        Index('idx_table_restaurant_id', RestaurantTable.restaurant_id),
        Index('idx_guest_status_restaurant', Guest.restaurant_id, Guest.status),
        Index('idx_table_status_restaurant', RestaurantTable.restaurant_id, RestaurantTable.status),
        
        # Time-based queries for sync operations
        Index('idx_guest_updated_at', Guest.updated_at),
        Index('idx_table_updated_at', RestaurantTable.updated_at),
        Index('idx_guest_created_at', Guest.created_at),
        
        # Authentication and user lookups
        Index('idx_user_email', User.email),
        Index('idx_restaurant_slug', Restaurant.slug),
        
        # Table assignment optimization
        Index('idx_table_current_guest', RestaurantTable.current_guest_id),
        Index('idx_guest_table_id', Guest.table_id),
        
        # Composite indexes for complex queries
        Index('idx_guest_restaurant_status_updated', Guest.restaurant_id, Guest.status, Guest.updated_at),
        Index('idx_table_restaurant_status_active', RestaurantTable.restaurant_id, RestaurantTable.status, RestaurantTable.is_active)
    ]
    
    return indexes
