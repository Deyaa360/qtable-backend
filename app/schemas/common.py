from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime

# Generic API response wrapper
class APIResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None

# Error response
class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error_code: Optional[str] = None

# WebSocket message format
class WebSocketMessage(BaseModel):
    type: str  # table_update, reservation_update, etc.
    data: Any
    timestamp: datetime
    restaurant_id: str

# Pagination
class PaginationParams(BaseModel):
    page: int = 1
    limit: int = 50
    
class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    limit: int
    has_next: bool
    has_prev: bool
