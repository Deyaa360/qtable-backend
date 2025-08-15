from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Float, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid

class Restaurant(Base):
    __tablename__ = "restaurants"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    phone = Column(String(20))
    address = Column(JSON)
    timezone = Column(String(50), default='UTC')
    
    # Subscription
    subscription_tier = Column(String(20), default='basic')
    subscription_status = Column(String(20), default='trial')
    stripe_customer_id = Column(String(255))
    trial_ends_at = Column(DateTime)
    
    # Settings
    settings = Column(JSON, default={})
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    users = relationship("User", back_populates="restaurant", cascade="all, delete-orphan")
    tables = relationship("RestaurantTable", back_populates="restaurant", cascade="all, delete-orphan")
    reservations = relationship("Reservation", back_populates="restaurant", cascade="all, delete-orphan")
    # guests = relationship("Guest", back_populates="restaurant", cascade="all, delete-orphan")  # Temporarily removed
    activity_logs = relationship("ActivityLog", back_populates="restaurant", cascade="all, delete-orphan")
