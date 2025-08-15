# Import all schemas here for easy access
from .table import TableResponse, TableCreate, TableUpdate, TableStatus, TableShape, Position
from .reservation import ReservationResponse, ReservationCreate, ReservationUpdate, GuestStatus
from .guest import GuestResponse, GuestCreate, GuestUpdate
from .auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse, RestaurantResponse
from .common import APIResponse, ErrorResponse, WebSocketMessage, PaginationParams, PaginatedResponse

__all__ = [
    # Table schemas
    "TableResponse",
    "TableCreate", 
    "TableUpdate",
    "TableStatus",
    "TableShape",
    "Position",
    
    # Reservation schemas
    "ReservationResponse",
    "ReservationCreate",
    "ReservationUpdate", 
    "GuestStatus",
    
    # Guest schemas
    "GuestResponse",
    "GuestCreate",
    "GuestUpdate",
    
    # Auth schemas
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserResponse",
    "RestaurantResponse",
    
    # Common schemas
    "APIResponse",
    "ErrorResponse",
    "WebSocketMessage",
    "PaginationParams",
    "PaginatedResponse"
]
