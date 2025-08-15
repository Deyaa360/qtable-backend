from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

# Guest status enum (matches iOS exactly)
class GuestStatus(str, Enum):
    waitlist = "waitlist"
    confirmed = "confirmed"
    arrived = "arrived"
    partiallyArrived = "partiallyArrived"
    seated = "seated"
    finished = "finished"
    cancelled = "cancelled"
    noShow = "noShow"
    runningLate = "runningLate"

# Base reservation schema
class ReservationBase(BaseModel):
    guest_name: str = None
    party_size: int = None
    status: GuestStatus = GuestStatus.waitlist

# Reservation creation schema
class ReservationCreate(ReservationBase):
    guest_name: str
    party_size: int
    reservation_time: Optional[datetime] = None
    contact_info: Optional[str] = None
    notes: Optional[str] = None

# Reservation update schema
class ReservationUpdate(BaseModel):
    guest_name: Optional[str] = None
    party_size: Optional[int] = None
    status: Optional[GuestStatus] = None
    assigned_table_id: Optional[str] = None
    check_in_time: Optional[datetime] = None
    seated_time: Optional[datetime] = None
    finished_time: Optional[datetime] = None
    notes: Optional[str] = None

# Reservation response schema (matches iOS GuestEntry exactly)
class ReservationResponse(BaseModel):
    id: str
    guestName: str  # camelCase to match iOS
    partySize: int  # camelCase to match iOS
    status: GuestStatus
    reservationTime: Optional[datetime] = None  # camelCase to match iOS
    checkInTime: Optional[datetime] = None      # camelCase to match iOS
    seatedTime: Optional[datetime] = None       # camelCase to match iOS
    finishedTime: Optional[datetime] = None     # camelCase to match iOS
    assignedTableId: Optional[str] = None       # camelCase to match iOS
    contactInfo: Optional[str] = None           # camelCase to match iOS
    notes: Optional[str] = None
    createdAt: datetime     # camelCase to match iOS
    lastUpdated: datetime   # camelCase to match iOS
    
    class Config:
        from_attributes = True
