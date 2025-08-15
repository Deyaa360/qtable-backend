from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.config import settings

# Create database engine
if "sqlite" in settings.database_url:
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False},
        echo=settings.environment == "development"
    )
else:
    engine = create_engine(
        settings.database_url,
        poolclass=StaticPool,
        echo=settings.environment == "development"
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
