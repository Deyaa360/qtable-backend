from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    restaurant_id = Column(String, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"))
    
    action = Column(String(100), nullable=False)  # table_update, guest_seated, etc.
    entity_type = Column(String(50))  # table, reservation, guest
    entity_id = Column(String)
    
    old_data = Column(JSON)
    new_data = Column(JSON)
    log_metadata = Column(JSON, default={})
    
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    restaurant = relationship("Restaurant", back_populates="activity_logs")
    user = relationship("User")
