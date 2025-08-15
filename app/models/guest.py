from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid

class Guest(Base):
    __tablename__ = "guests"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # restaurant_id = Column(String, ForeignKey("restaurants.id"), nullable=False)  # Temporarily removed
    
    # Contact Info
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(255))
    phone = Column(String(20))
    
    # Table Assignment Fields (for current visit/reservation)
    party_size = Column(Integer)
    status = Column(String(20), default='waitlist')  # confirmed, arrived, seated, finished, cancelled, no_show, running_late, waitlist
    table_id = Column(String, ForeignKey("restaurant_tables.id"))
    
    # Timing Fields
    reservation_time = Column(DateTime)
    check_in_time = Column(DateTime)
    seated_time = Column(DateTime)
    finished_time = Column(DateTime)
    
    # Preferences
    dietary_restrictions = Column(JSON, default=[])
    special_requests = Column(Text)
    notes = Column(Text)
    
    # Metadata
    total_visits = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    # restaurant = relationship("Restaurant", back_populates="guests")  # Temporarily removed
    reservations = relationship("Reservation", back_populates="guest")
    table = relationship("RestaurantTable", foreign_keys=[table_id])
