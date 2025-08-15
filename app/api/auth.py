from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database import get_db
from app.models import User, Restaurant
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.utils.security import verify_password, get_password_hash, create_access_token, create_restaurant_slug
from app.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """Authenticate user and return access token"""
    
    # Find user by email
    user = db.query(User).filter(User.email == login_data.email).first()
    
    # Verify user exists and password is correct
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive"
        )
    
    # Check if restaurant is active
    restaurant = db.query(Restaurant).filter(Restaurant.id == user.restaurant_id).first()
    if not restaurant or not restaurant.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Restaurant account is inactive"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=30)  # Could be configurable
    access_token = create_access_token(
        data={"sub": str(user.id), "restaurant_id": str(user.restaurant_id)},
        expires_delta=access_token_expires
    )
    
    # Update last login
    from datetime import datetime
    user.last_login_at = datetime.utcnow()
    db.commit()
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        restaurant_id=str(user.restaurant_id),
        user_id=str(user.id)
    )

@router.post("/register", response_model=dict)
async def register(
    register_data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """Register a new restaurant and owner user"""
    
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == register_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create restaurant slug
    restaurant_slug = create_restaurant_slug(register_data.restaurant_name)
    
    # Check if slug already exists
    existing_restaurant = db.query(Restaurant).filter(Restaurant.slug == restaurant_slug).first()
    if existing_restaurant:
        # Add number suffix if slug exists
        counter = 1
        while existing_restaurant:
            new_slug = f"{restaurant_slug}-{counter}"
            existing_restaurant = db.query(Restaurant).filter(Restaurant.slug == new_slug).first()
            if not existing_restaurant:
                restaurant_slug = new_slug
                break
            counter += 1
    
    try:
        # Create restaurant
        restaurant = Restaurant(
            name=register_data.restaurant_name,
            slug=restaurant_slug,
            email=register_data.email,
            subscription_tier="basic",
            subscription_status="trial"
        )
        db.add(restaurant)
        db.flush()  # Get the restaurant ID
        
        # Create owner user
        user = User(
            restaurant_id=restaurant.id,
            email=register_data.email,
            password_hash=get_password_hash(register_data.password),
            first_name=register_data.first_name,
            last_name=register_data.last_name,
            role="owner"
        )
        db.add(user)
        db.commit()
        
        return {
            "message": "Restaurant created successfully",
            "restaurant_id": str(restaurant.id),
            "user_id": str(user.id)
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create restaurant account"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user information"""
    
    restaurant = db.query(Restaurant).filter(Restaurant.id == current_user.restaurant_id).first()
    
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        role=current_user.role,
        restaurant_id=str(current_user.restaurant_id),
        restaurant_name=restaurant.name if restaurant else ""
    )
