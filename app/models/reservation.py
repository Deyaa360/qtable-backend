from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid

class Reservation(Base):
    __tablename__ = "reservations"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    restaurant_id = Column(String, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    guest_id = Column(String, ForeignKey("guests.id"))  # null for walk-ins without profile
    table_id = Column(String, ForeignKey("restaurant_tables.id"))
    
    # Reservation Details
    party_size = Column(Integer, nullable=False)
    reservation_time = Column(DateTime)  # null for walk-ins
    duration_minutes = Column(Integer, default=90)
    
    # Guest Info (for walk-ins without guest profile - matches iOS exactly)
    guest_name = Column(String(200), nullable=False)  # always required
    guest_phone = Column(String(20))
    guest_email = Column(String(255))
    
    # Status & Tracking (matches iOS enum exactly)
    status = Column(String(20), default='waitlist')  # waitlist, confirmed, arrived, partiallyArrived, seated, finished, cancelled, noShow, runningLate
    source = Column(String(20), default='walk_in')  # online, walk_in, phone, imported
    
    # Timestamps (match iOS model exactly)
    check_in_time = Column(DateTime)
    seated_time = Column(DateTime)
    finished_time = Column(DateTime)
    
    # Metadata
    notes = Column(Text)
    special_requests = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    restaurant = relationship("Restaurant", back_populates="reservations")
    guest = relationship("Guest", back_populates="reservations")
    table = relationship("RestaurantTable", foreign_keys=[table_id])
