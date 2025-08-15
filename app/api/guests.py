from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import Guest, Reservation, Restaurant, User
from app.schemas import GuestResponse, GuestCreate, GuestUpdate
from app.dependencies import get_current_user, verify_restaurant_access
from app.utils.database_helper import log_activity

router = APIRouter(prefix="/restaurants", tags=["guests"])

def guest_to_response(guest: Guest) -> GuestResponse:
    """Convert database guest model to response schema"""
    # Combine first and last name for the name field
    full_name = f"{guest.first_name or ''} {guest.last_name or ''}".strip()
    if not full_name:  # If both first_name and last_name are empty
        full_name = "Unknown Guest"
    
    return GuestResponse(
        id=str(guest.id),
        name=full_name,  # Combined name field (Option 1)
        firstName=guest.first_name or "",
        lastName=guest.last_name or "",
        email=guest.email,
        phone=guest.phone,
        totalVisits=guest.total_visits,
        notes=guest.notes,
        dietaryRestrictions=guest.dietary_restrictions or [],
        specialRequests=guest.special_requests,
        createdAt=guest.created_at,
        lastUpdated=guest.updated_at
    )

@router.get("/{restaurant_id}/guests", response_model=List[GuestResponse])
async def get_guests(
    restaurant_id: str = Path(..., description="Restaurant ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all guests for a restaurant"""
    guests = db.query(Guest).filter(
        # Guest.restaurant_id == restaurant_id  # Temporarily disabled for testing
    ).order_by(Guest.created_at.desc()).all()
    
    return [guest_to_response(guest) for guest in guests]

@router.post("/{restaurant_id}/guests", response_model=GuestResponse)
async def create_guest(
    guest_data: GuestCreate,
    restaurant_id: str = Path(..., description="Restaurant ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new guest profile"""
    guest = Guest(
        # restaurant_id=restaurant_id,  # Temporarily disabled for testing
        first_name=guest_data.first_name,
        last_name=guest_data.last_name,
        email=guest_data.email,
        phone=guest_data.phone,
        notes=guest_data.notes,
        dietary_restrictions=guest_data.dietary_restrictions,
        special_requests=guest_data.special_requests
    )
    
    db.add(guest)
    db.commit()
    db.refresh(guest)
    
    # Log activity
    log_activity(
        db=db,
        restaurant_id=restaurant_id,
        user_id=str(current_user.id),
        action="guest_create",
        entity_type="guest",
        entity_id=str(guest.id),
        new_data={
            "name": f"{guest.first_name} {guest.last_name}",
            "email": guest.email
        }
    )
    
    return guest_to_response(guest)

@router.get("/{restaurant_id}/guests/{guest_id}", response_model=GuestResponse)
async def get_guest(
    restaurant_id: str = Path(..., description="Restaurant ID"),
    guest_id: str = Path(..., description="Guest ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific guest"""
    guest = db.query(Guest).filter(
        Guest.id == guest_id
        # Guest.restaurant_id == restaurant_id  # Temporarily disabled for testing
    ).first()
    
    if not guest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest not found"
        )
    
    return guest_to_response(guest)

@router.put("/{restaurant_id}/guests/{guest_id}", response_model=GuestResponse)
async def update_guest(
    guest_data: GuestUpdate,
    restaurant_id: str = Path(..., description="Restaurant ID"),
    guest_id: str = Path(..., description="Guest ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a guest profile"""
    guest = db.query(Guest).filter(
        Guest.id == guest_id
    ).first()
    
    if not guest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest not found"
        )
    
    # Store old data for logging
    old_data = {
        "name": f"{guest.first_name} {guest.last_name}",
        "email": guest.email,
        "phone": guest.phone
    }
    
    # Update fields that were provided
    if guest_data.first_name is not None:
        guest.first_name = guest_data.first_name
    if guest_data.last_name is not None:
        guest.last_name = guest_data.last_name
    if guest_data.email is not None:
        guest.email = guest_data.email
    if guest_data.phone is not None:
        guest.phone = guest_data.phone
    if guest_data.notes is not None:
        guest.notes = guest_data.notes
    if guest_data.dietary_restrictions is not None:
        guest.dietary_restrictions = guest_data.dietary_restrictions
    if guest_data.special_requests is not None:
        guest.special_requests = guest_data.special_requests
    
    db.commit()
    db.refresh(guest)
    
    # Log activity
    new_data = {
        "name": f"{guest.first_name} {guest.last_name}",
        "email": guest.email,
        "phone": guest.phone
    }
    
    log_activity(
        db=db,
        restaurant_id=restaurant_id,
        user_id=str(current_user.id),
        action="guest_update",
        entity_type="guest",
        entity_id=str(guest.id),
        old_data=old_data,
        new_data=new_data
    )
    
    return guest_to_response(guest)

@router.delete("/{restaurant_id}/guests/{guest_id}")
async def delete_guest(
    restaurant_id: str = Path(..., description="Restaurant ID"),
    guest_id: str = Path(..., description="Guest ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a guest profile"""
    guest = db.query(Guest).filter(
        Guest.id == guest_id
        # Guest.restaurant_id == restaurant_id  # Temporarily disabled for testing
    ).first()
    
    if not guest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Guest not found"
        )
    
    # Check if guest has active reservations
    active_reservations = db.query(Reservation).filter(
        Reservation.guest_id == guest_id,
        Reservation.status.in_(["waitlist", "arrived", "seated"])
    ).count()
    
    if active_reservations > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete guest with active reservations"
        )
    
    db.delete(guest)
    db.commit()
    
    # Log activity
    log_activity(
        db=db,
        restaurant_id=restaurant_id,
        user_id=str(current_user.id),
        action="guest_delete",
        entity_type="guest",
        entity_id=str(guest.id),
        old_data={
            "name": f"{guest.first_name} {guest.last_name}",
            "email": guest.email
        }
    )
    
    return {"success": True, "message": "Guest deleted successfully"}
