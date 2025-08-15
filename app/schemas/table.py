from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

# Enums that match iOS exactly
class TableStatus(str, Enum):
    available = "available"
    occupied = "occupied" 
    reserved = "reserved"
    outOfService = "outOfService"

class TableShape(str, Enum):
    round = "round"
    square = "square"
    rectangle = "rectangle"
    oval = "oval"

# Position schema (matches iOS CGPoint)
class Position(BaseModel):
    x: float
    y: float

# Base table schema
class TableBase(BaseModel):
    table_number: str = None
    capacity: int = None
    position: Position = None
    shape: TableShape = TableShape.round
    section: Optional[str] = None

# Table creation schema  
class TableCreate(TableBase):
    table_number: str
    capacity: int
    position: Position

# Table update schema
class TableUpdate(BaseModel):
    table_number: Optional[str] = None
    capacity: Optional[int] = None
    status: Optional[TableStatus] = None
    position: Optional[Position] = None
    shape: Optional[TableShape] = None
    section: Optional[str] = None
    current_guest_id: Optional[str] = None

# Table response schema (matches iOS RestaurantTable exactly)
class TableResponse(BaseModel):
    id: str
    tableNumber: str  # camelCase to match iOS
    capacity: int
    status: TableStatus
    position: Position
    shape: TableShape
    section: Optional[str] = None
    currentGuestId: Optional[str] = None  # camelCase to match iOS
    lastUpdated: datetime  # camelCase to match iOS
    createdAt: datetime   # camelCase to match iOS
    
    class Config:
        from_attributes = True
