from pydantic import BaseModel, EmailStr
from typing import Optional

# Login request
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# Registration request  
class RegisterRequest(BaseModel):
    restaurant_name: str
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None

# Token response
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    restaurant_id: str
    user_id: str

# Current user response
class UserResponse(BaseModel):
    id: str
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    restaurant_id: str
    restaurant_name: str
    
    class Config:
        from_attributes = True

# Restaurant response  
class RestaurantResponse(BaseModel):
    id: str
    name: str
    email: str
    subscription_tier: str
    subscription_status: str
    
    class Config:
        from_attributes = True
