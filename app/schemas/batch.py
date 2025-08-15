from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Batch update request schemas
class BatchGuestUpdate(BaseModel):
    id: str
    status: Optional[str] = None
    assignedTableId: Optional[str] = None  # iOS camelCase
    table_id: Optional[str] = None  # backend snake_case support
    seatedTime: Optional[datetime] = None
    seated_time: Optional[datetime] = None  # backend snake_case support
    checkInTime: Optional[datetime] = None
    check_in_time: Optional[datetime] = None
    finishedTime: Optional[datetime] = None
    finished_time: Optional[datetime] = None
    partySize: Optional[int] = None
    party_size: Optional[int] = None

class BatchTableUpdate(BaseModel):
    id: str
    status: Optional[str] = None
    currentGuestId: Optional[str] = None  # iOS camelCase
    current_guest_id: Optional[str] = None  # backend snake_case support

class BatchUpdateRequest(BaseModel):
    guests: Optional[List[BatchGuestUpdate]] = []
    tables: Optional[List[BatchTableUpdate]] = []

# Batch update response schemas
class BatchGuestResponse(BaseModel):
    id: str
    name: str
    firstName: str
    lastName: str
    email: Optional[str] = None
    phone: Optional[str] = None
    partySize: Optional[int] = None
    status: Optional[str] = None
    tableId: Optional[str] = None
    reservationTime: Optional[datetime] = None
    checkInTime: Optional[datetime] = None
    seatedTime: Optional[datetime] = None
    finishedTime: Optional[datetime] = None
    notes: Optional[str] = None
    dietaryRestrictions: List[str] = []
    specialRequests: Optional[str] = None
    totalVisits: int = 0
    createdAt: datetime
    lastUpdated: datetime

    class Config:
        from_attributes = True

class BatchTableResponse(BaseModel):
    id: str
    tableNumber: str
    capacity: int
    status: str
    position: dict  # {x: float, y: float}
    shape: str
    section: Optional[str] = None
    currentGuestId: Optional[str] = None
    lastUpdated: datetime
    createdAt: datetime

    class Config:
        from_attributes = True

class BatchUpdateResponse(BaseModel):
    success: bool
    updated_guests: List[BatchGuestResponse]
    updated_tables: List[BatchTableResponse]
    timestamp: datetime
    errors: Optional[List[str]] = None
