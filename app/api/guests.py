from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import Guest, Reservation, Restaurant, User, RestaurantTable
from app.schemas import GuestResponse, GuestCreate, GuestUpdate
from app.dependencies import get_current_user, verify_restaurant_access
from app.utils.database_helper import log_activity

router = APIRouter(prefix="/restaurants", tags=["guests"])

def sync_guest_table_relationship(db: Session, guest_id: str, table_id: Optional[str], old_table_id: Optional[str] = None):
    """
    Synchronize the bidirectional relationship between guest and table.
    When a guest is assigned to a table, update the table's current_guest_id.
    When a guest is removed from a table, clear the table's current_guest_id.
    """
    # Clear old table assignment if guest was previously assigned to a different table
    if old_table_id and old_table_id != table_id:
        old_table = db.query(RestaurantTable).filter(RestaurantTable.id == old_table_id).first()
        if old_table and old_table.current_guest_id == guest_id:
            old_table.current_guest_id = None
    
    # Set new table assignment
    if table_id:
        table = db.query(RestaurantTable).filter(RestaurantTable.id == table_id).first()
        if table:
            # Clear any other guest assigned to this table
            if table.current_guest_id and table.current_guest_id != guest_id:
                other_guest = db.query(Guest).filter(Guest.id == table.current_guest_id).first()
                if other_guest:
                    other_guest.table_id = None
                    other_guest.status = "waitlist"  # Reset status when table is taken
            
            # Assign table to new guest
            table.current_guest_id = guest_id
            table.status = "occupied" if table_id else "available"

def handle_guest_status_change(db: Session, guest: Guest, old_status: str, new_status: str):
    """
    Handle automatic table clearing when guest status changes from "Seated" to any other status.
    This implements the business logic required by the iOS frontend.
    """
    from datetime import datetime
    
    # If guest was seated and is no longer seated, clear the table
    if old_status == "Seated" and new_status != "Seated":
        if guest.table_id:
            # Find and clear the table
            table = db.query(RestaurantTable).filter(RestaurantTable.id == guest.table_id).first()
            if table:
                table.status = "available"
                table.current_guest_id = None
                # table.updated_at will be automatically updated by SQLAlchemy
            
            # Clear guest's table assignment
            guest.table_id = None
        
        # Set finished time if status is finished
        if new_status == "Finished":
            guest.finished_time = datetime.utcnow()
    
    # Update guest status
    guest.status = new_status

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
        
        # Table assignment fields
        partySize=guest.party_size,
        status=guest.status,
        tableId=guest.table_id,
        reservationTime=guest.reservation_time,
        checkInTime=guest.check_in_time,
        seatedTime=guest.seated_time,
        finishedTime=guest.finished_time,
        
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
        special_requests=guest_data.special_requests,
        
        # Table assignment fields
        party_size=guest_data.party_size,
        status=guest_data.status,
        table_id=guest_data.table_id,
        reservation_time=guest_data.reservation_time,
        check_in_time=guest_data.check_in_time,
        seated_time=guest_data.seated_time,
        finished_time=guest_data.finished_time
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
    
    # Store old data for logging and status change detection
    old_data = {
        "name": f"{guest.first_name} {guest.last_name}",
        "email": guest.email,
        "phone": guest.phone
    }
    old_status = guest.status  # Store old status for automatic table clearing
    
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
    
    # Store old table_id for relationship sync
    old_table_id = guest.table_id
    
    # Update table assignment fields
    if guest_data.party_size is not None:
        guest.party_size = guest_data.party_size
    if guest_data.table_id is not None:
        guest.table_id = guest_data.table_id
    if guest_data.reservation_time is not None:
        guest.reservation_time = guest_data.reservation_time
    if guest_data.check_in_time is not None:
        guest.check_in_time = guest_data.check_in_time
    if guest_data.seated_time is not None:
        guest.seated_time = guest_data.seated_time
    if guest_data.finished_time is not None:
        guest.finished_time = guest_data.finished_time
    
    # Handle status changes with automatic table clearing
    if guest_data.status is not None:
        handle_guest_status_change(db, guest, old_status, guest_data.status)
    
    # Sync guest-table relationship if table assignment changed
    if guest_data.table_id is not None and guest.table_id != old_table_id:
        sync_guest_table_relationship(db, guest_id, guest.table_id, old_table_id)
    
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
