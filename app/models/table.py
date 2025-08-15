from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid

class RestaurantTable(Base):
    __tablename__ = "restaurant_tables"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    restaurant_id = Column(String, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    
    # Table Details
    table_number = Column(String(20), nullable=False)
    capacity = Column(Integer, nullable=False)
    min_party_size = Column(Integer, default=1)
    max_party_size = Column(Integer)
    
    # Floor Plan Position (matches iOS CGPoint as floats)
    position_x = Column(Float, nullable=False)  # x coordinate (0.0 to 1.0)
    position_y = Column(Float, nullable=False)  # y coordinate (0.0 to 1.0)
    shape = Column(String(20), default='round')  # round, square, rectangle, oval
    section = Column(String(100))  # Main Dining, Bar, Patio
    
    # Current Status (matches iOS enum exactly)
    status = Column(String(20), default='available')  # available, occupied, reserved, outOfService
    current_guest_id = Column(String)  # references reservations.id
    
    # Metadata
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    restaurant = relationship("Restaurant", back_populates="tables")
