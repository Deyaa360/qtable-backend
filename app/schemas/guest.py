from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class GuestCreate(BaseModel):
    # Primary identifier - phone number as requested
    phone: str  # Make phone required as primary identifier
    
    # Name fields - flexible (can be empty strings)
    first_name: Optional[str] = ""
    last_name: Optional[str] = ""
    
    # Optional contact info
    email: Optional[EmailStr] = None
    notes: Optional[str] = None
    dietary_restrictions: Optional[List[str]] = None
    special_requests: Optional[str] = None

class GuestUpdate(BaseModel):
    # All fields optional for updates
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    notes: Optional[str] = None
    dietary_restrictions: Optional[List[str]] = None
    special_requests: Optional[str] = None

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
    createdAt: datetime
    lastUpdated: datetime

    class Config:
        from_attributes = True
