from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db, set_restaurant_context
from app.models import User, Restaurant
from app.utils.security import verify_token

# Security scheme
security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user"""
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Verify token
    payload = verify_token(credentials.credentials)
    if payload is None:
        raise credentials_exception
    
    # Get user from database
    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user"
        )
    
    return user

async def get_current_restaurant(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Restaurant:
    """Get the current user's restaurant and set context"""
    
    restaurant = db.query(Restaurant).filter(Restaurant.id == current_user.restaurant_id).first()
    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    if not restaurant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Restaurant account is inactive"
        )
    
    # Set restaurant context for RLS
    set_restaurant_context(db, str(restaurant.id))
    
    return restaurant

async def verify_restaurant_access(
    restaurant_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Restaurant:
    """Verify user has access to the specified restaurant"""
    
    # Check if user belongs to this restaurant
    if str(current_user.restaurant_id) != restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this restaurant"
        )
    
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if restaurant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    
    if not restaurant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Restaurant account is inactive"
        )
    
    # Set restaurant context for RLS
    set_restaurant_context(db, restaurant_id)
    
    return restaurant

def require_role(required_roles: list[str]):
    """Dependency factory to require specific user roles"""
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {', '.join(required_roles)}"
            )
        return current_user
    return role_checker

# Common role dependencies - these should be function calls, not Depends
def require_owner():
    return require_role(["owner"])

def require_manager():
    return require_role(["owner", "manager"])

def require_staff():
    return require_role(["owner", "manager", "staff"])
