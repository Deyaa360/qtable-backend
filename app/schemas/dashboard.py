from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from .table import Position

# Dashboard optimized schemas
class MinimalGuestResponse(BaseModel):
    """Minimal guest data for dashboard performance"""
    id: str
    name: str
    status: str
    tableId: Optional[str] = None
    partySize: Optional[int] = None
    lastUpdated: datetime

    class Config:
        from_attributes = True

class MinimalTableResponse(BaseModel):
    """Minimal table data for dashboard performance"""
    id: str
    tableNumber: str
    capacity: int  # ADDED: Required for iOS app compatibility
    position: Position  # ADDED: Required for floor plan positioning
    status: str
    currentGuestId: Optional[str] = None
    lastUpdated: datetime

    class Config:
        from_attributes = True

class DashboardStatsResponse(BaseModel):
    """Dashboard statistics for quick overview"""
    total_guests: int
    total_tables: int
    occupancy_rate: float
    guests_by_status: dict  # {"waitlist": 5, "seated": 10, etc.}
    tables_by_status: dict  # {"available": 8, "occupied": 12, etc.}

class DashboardDataResponse(BaseModel):
    """Optimized dashboard data response"""
    guests: List[MinimalGuestResponse]
    tables: List[MinimalTableResponse]
    stats: DashboardStatsResponse
    lastUpdated: datetime
    isFullSync: bool  # True for full data, False for delta

# Delta update schemas
class GuestUpdate(BaseModel):
    id: str
    action: str  # "updated", "created", "deleted"
    data: Optional[MinimalGuestResponse] = None
    lastUpdated: datetime

class TableUpdate(BaseModel):
    id: str
    action: str  # "updated", "created", "deleted"
    data: Optional[MinimalTableResponse] = None
    lastUpdated: datetime

class DeltaUpdatesResponse(BaseModel):
    """Delta updates for incremental sync"""
    guestUpdates: List[GuestUpdate]
    tableUpdates: List[TableUpdate]
    deletedGuests: List[str]
    deletedTables: List[str]
    timestamp: datetime
