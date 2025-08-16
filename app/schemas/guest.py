from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime

class GuestCreate(BaseModel):
    # Name fields - first_name required for walk-ins
    first_name: str  # Required field
    last_name: Optional[str] = ""
    
    # Party size - required for walk-ins
    party_size: int  # Required field, must be positive
    
    # Status - defaults to Waitlist for walk-ins
    status: Optional[str] = "Waitlist"  # Match iOS requirement exactly
    
    # Optional contact info
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    notes: Optional[str] = None
    dietary_restrictions: Optional[List[str]] = None
    special_requests: Optional[str] = None
    
    # Table assignment fields (should be null for walk-ins)
    table_id: Optional[str] = None
    reservation_time: Optional[datetime] = None
    check_in_time: Optional[datetime] = None
    seated_time: Optional[datetime] = None
    finished_time: Optional[datetime] = None
    
    @validator('party_size')
    def validate_party_size(cls, v):
        if v is not None and v < 1:
            raise ValueError('party_size must be a positive integer')
        return v
    
    @validator('status')
    def validate_status(cls, v):
        valid_statuses = ["Waitlist", "Seated", "Finished", "Cancelled", "No Show", "Running Late", "Arrived"]
        if v and v not in valid_statuses:
            raise ValueError(f'status must be one of: {", ".join(valid_statuses)}')
        return v

class GuestUpdate(BaseModel):
    # All fields optional for updates
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    notes: Optional[str] = None
    dietary_restrictions: Optional[List[str]] = None
    special_requests: Optional[str] = None
    
    # Table assignment fields for updates
    party_size: Optional[int] = None
    status: Optional[str] = None
    table_id: Optional[str] = None
    reservation_time: Optional[datetime] = None
    check_in_time: Optional[datetime] = None
    seated_time: Optional[datetime] = None
    finished_time: Optional[datetime] = None

class GuestResponse(BaseModel):
    id: str
    name: str  # Combined first + last name for flexibility
    firstName: str
    lastName: str
    email: Optional[str] = None
    phone: Optional[str] = None
    totalVisits: int
    notes: Optional[str] = None
    dietaryRestrictions: List[str]
    specialRequests: Optional[str] = None
    
    # Table assignment fields in response
    partySize: Optional[int] = None
    status: Optional[str] = None
    tableId: Optional[str] = None
    reservationTime: Optional[datetime] = None
    checkInTime: Optional[datetime] = None
    seatedTime: Optional[datetime] = None
    finishedTime: Optional[datetime] = None
    
    createdAt: datetime
    lastUpdated: datetime

    class Config:
        from_attributes = True
