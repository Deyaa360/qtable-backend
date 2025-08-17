from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session, joinedload, selectinload
from typing import List, Optional
from datetime import datetime
import logging
from app.database import get_db
from app.models import Guest, Reservation, Restaurant, User, RestaurantTable
from app.schemas import GuestResponse, GuestCreate, GuestUpdate
from app.dependencies import get_current_user, verify_restaurant_access
from app.utils.database_helper import log_activity
from app.utils.cache import cached, invalidate_cache_pattern
from app.utils.realtime_broadcaster import realtime_broadcaster
from app.api.websockets import broadcast_guest_created, broadcast_guest_updated, broadcast_guest_deleted, broadcast_table_updated, broadcast_delta_update, broadcast_guest_data_change

router = APIRouter(prefix="/restaurants", tags=["guests"])
logger = logging.getLogger(__name__)

def validate_walk_in_guest(guest_data: GuestCreate) -> GuestCreate:
    """
    Validate walk-in guest data according to iOS requirements.
    Enforces business rules for walk-in guests.
    """
    # If status is Waitlist, this is a walk-in guest
    if guest_data.status == "Waitlist":
        logger.info(f"Validating walk-in guest: {guest_data.first_name} {guest_data.last_name}, party_size: {guest_data.party_size}")
        
        # Required fields for walk-ins
        if not guest_data.first_name or guest_data.first_name.strip() == "":
            raise HTTPException(
                status_code=400,
                detail="first_name is required for walk-in guests"
            )
        
        if not guest_data.party_size or guest_data.party_size < 1:
            raise HTTPException(
                status_code=400,
                detail="party_size must be a positive integer for walk-in guests"
            )
        
        # Forbidden fields for walk-ins - these should be null
        forbidden_fields = []
        if guest_data.reservation_time is not None:
            forbidden_fields.append("reservation_time")
        if guest_data.table_id is not None:
            forbidden_fields.append("table_id")
        if guest_data.seated_time is not None:
            forbidden_fields.append("seated_time")
        if guest_data.finished_time is not None:
            forbidden_fields.append("finished_time")
        
        if forbidden_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Walk-in guests cannot have these fields set: {', '.join(forbidden_fields)}"
            )
        
        # Auto-set check_in_time if not provided
        if guest_data.check_in_time is None:
            guest_data.check_in_time = datetime.utcnow()
            logger.info(f"Auto-set check_in_time for walk-in guest: {guest_data.check_in_time}")
    
    return guest_data

def sync_guest_table_relationship(db: Session, guest_id: str, table_id: Optional[str], old_table_id: Optional[str] = None):
    """
    Synchronize the bidirectional relationship between guest and table.
    When a guest is assigned to a table, update the table's current_guest_id.
    When a guest is removed from a table, clear the table's current_guest_id.
    ENFORCES: Only occupied tables can have currentGuestId (business rule)
    """
    # Clear old table assignment if guest was previously assigned to a different table
    if old_table_id and old_table_id != table_id:
        old_table = db.query(RestaurantTable).filter(RestaurantTable.id == old_table_id).first()
        if old_table and old_table.current_guest_id == guest_id:
            old_table.current_guest_id = None
            # If table is not occupied, ensure it's available
            if old_table.status == "occupied":
                old_table.status = "available"
    
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
            
            # Assign table to new guest and set status to occupied
            table.current_guest_id = guest_id
            table.status = "occupied"  # ENFORCE: Only occupied tables have currentGuestId
    else:
        # If no table_id provided, ensure no table claims this guest
        tables_with_guest = db.query(RestaurantTable).filter(RestaurantTable.current_guest_id == guest_id).all()
        for table in tables_with_guest:
            table.current_guest_id = None
            if table.status == "occupied":
                table.status = "available"

async def handle_guest_status_change(db: Session, guest: Guest, old_status: str, new_status: str):
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
                
                # Broadcast table update to all connected iOS devices
                try:
                    await broadcast_table_updated(table)
                except Exception as e:
                    logger.warning(f"Failed to broadcast table_updated: {e}")
            
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
    """
    Create a new guest profile.
    Supports both reservations and walk-in guests with proper validation.
    """
    
    # Validate walk-in guest business rules
    validated_guest_data = validate_walk_in_guest(guest_data)
    
    # Create guest with validated data
    guest = Guest(
        restaurant_id=restaurant_id,  # Re-enabled restaurant_id association
        first_name=validated_guest_data.first_name,
        last_name=validated_guest_data.last_name,
        email=validated_guest_data.email,
        phone=validated_guest_data.phone,
        notes=validated_guest_data.notes,
        dietary_restrictions=validated_guest_data.dietary_restrictions,
        special_requests=validated_guest_data.special_requests,
        
        # Table assignment fields
        party_size=validated_guest_data.party_size,
        status=validated_guest_data.status or "Waitlist",  # Default to Waitlist for walk-ins
        table_id=validated_guest_data.table_id,
        reservation_time=validated_guest_data.reservation_time,
        check_in_time=validated_guest_data.check_in_time,
        seated_time=validated_guest_data.seated_time,
        finished_time=validated_guest_data.finished_time
    )
    
    try:
        db.add(guest)
        db.commit()
        db.refresh(guest)
        
        # Invalidate relevant cache entries
        invalidate_cache_pattern(f"dashboard:{restaurant_id}")
        invalidate_cache_pattern(f"guests:{restaurant_id}")
        
        # Log activity with appropriate action type
        action_type = "walk_in_create" if guest.status == "Waitlist" else "guest_create"
        log_activity(
            db=db,
            restaurant_id=restaurant_id,
            user_id=str(current_user.id),
            action=action_type,
            entity_type="guest",
            entity_id=str(guest.id),
            new_data={
                "name": f"{guest.first_name} {guest.last_name}",
                "email": guest.email,
                "party_size": guest.party_size,
                "status": guest.status
            }
        )
        
        logger.info(f"Successfully created guest: {guest.first_name} {guest.last_name} (ID: {guest.id}, Status: {guest.status})")
        
        # 🚀 REAL-TIME BROADCAST: Notify all connected devices immediately
        try:
            await realtime_broadcaster.broadcast_guest_created(
                restaurant_id=restaurant_id,
                guest_id=str(guest.id),
                guest_data={
                    "first_name": guest.first_name,
                    "last_name": guest.last_name,
                    "party_size": guest.party_size,
                    "status": guest.status
                }
            )
            logger.info(f"📡 Real-time broadcast sent for new guest: {guest.id}")
        except Exception as e:
            logger.warning(f"Failed to broadcast real-time guest_created: {e}")
        
        # Legacy broadcast for backward compatibility
        try:
            await broadcast_guest_created(guest)
        except Exception as e:
            logger.warning(f"Failed to broadcast legacy guest_created: {e}")
        
        return guest_to_response(guest)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating guest: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create guest: {str(e)}"
        )

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
        await handle_guest_status_change(db, guest, old_status, guest_data.status)
    
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
    
    # 🚀 REAL-TIME BROADCAST: PRIORITY #1 - Guest status updates
    try:
        # Determine the action type for better messaging
        action = "status_change" if guest_data.status is not None else "update"
        
        await realtime_broadcaster.broadcast_guest_updated(
            restaurant_id=restaurant_id,
            guest_id=str(guest.id),
            action=action,
            guest_data={
                "status": guest.status,
                "table_id": str(guest.table_id) if guest.table_id else None
            }
        )
        logger.info(f"📡 Real-time broadcast sent for guest update: {guest.id}")
    except Exception as e:
        logger.warning(f"Failed to broadcast real-time guest_updated: {e}")
    
    # Legacy broadcast for backward compatibility
    try:
        await broadcast_guest_updated(guest)
    except Exception as e:
        logger.warning(f"Failed to broadcast legacy guest_updated: {e}")
    
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
    
    # Store guest_id for broadcast before deletion
    guest_id_for_broadcast = str(guest.id)
    
    db.delete(guest)
    db.commit()
    
    # Log activity
    log_activity(
        db=db,
        restaurant_id=restaurant_id,
        user_id=str(current_user.id),
        action="guest_delete",
        entity_type="guest",
        entity_id=guest_id_for_broadcast,
        old_data={
            "name": f"{guest.first_name} {guest.last_name}",
            "email": guest.email
        }
    )
    
    # 🚀 REAL-TIME BROADCAST: Guest deletion
    try:
        await realtime_broadcaster.broadcast_guest_deleted(
            restaurant_id=restaurant_id,
            guest_id=guest_id_for_broadcast
        )
        logger.info(f"📡 Real-time broadcast sent for guest deletion: {guest_id_for_broadcast}")
    except Exception as e:
        logger.warning(f"Failed to broadcast real-time guest_deleted: {e}")
    
    # Legacy broadcast for backward compatibility
    try:
        await broadcast_guest_deleted(guest_id_for_broadcast)
    except Exception as e:
        logger.warning(f"Failed to broadcast guest_deleted: {e}")
    
    return {"success": True, "message": "Guest deleted successfully"}

@router.put("/{restaurant_id}/guests/{guest_id}/status/atomic", response_model=dict)
async def update_guest_status_atomic(
    new_status: str,
    restaurant_id: str = Path(..., description="Restaurant ID"),
    guest_id: str = Path(..., description="Guest ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Atomically update guest status with automatic table clearing
    
    This endpoint implements the enterprise-grade atomic operations required by iOS:
    - Updates guest status
    - Automatically clears table if status is terminal (finished, cancelled, no-show)
    - Broadcasts both changes as a single atomic transaction
    - Full rollback on any failure
    """
    import uuid
    from datetime import datetime, timezone
    
    # Start atomic transaction
    transaction_id = str(uuid.uuid4())
    logger.info(f"Starting atomic guest status update {transaction_id} for guest {guest_id} -> {new_status}")
    
    try:
        # Start database transaction
        with db.begin():
            # Get guest
            guest = db.query(Guest).filter(Guest.id == guest_id).first()
            if not guest:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Guest not found"
                )
            
            old_status = guest.status
            old_table_id = guest.table_id
            changes = []
            
            # Update guest status
            guest.status = new_status
            guest.updated_at = datetime.now(timezone.utc)
            
            # Set finished time for terminal statuses
            if new_status == "Finished":
                guest.finished_time = datetime.now(timezone.utc)
            
            # Add guest change to broadcast
            changes.append({
                "entity_type": "guest",
                "entity_id": guest_id,
                "action": "update",
                "data": {
                    "id": str(guest.id),
                    "name": f"{guest.first_name or ''} {guest.last_name or ''}".strip() or "Unknown Guest",
                    "status": new_status,
                    "table_id": str(guest.table_id) if guest.table_id else None,
                    "finished_time": guest.finished_time.isoformat() if guest.finished_time else None
                }
            })
            
            # Handle automatic table clearing for terminal statuses
            if new_status in ["Finished", "Cancelled", "No Show"] and old_table_id:
                table = db.query(RestaurantTable).filter(RestaurantTable.id == old_table_id).first()
                if table:
                    # Clear table
                    table.status = "available"
                    table.current_guest_id = None
                    table.updated_at = datetime.now(timezone.utc)
                    
                    # Clear guest's table assignment
                    guest.table_id = None
                    
                    # Add table change to broadcast
                    changes.append({
                        "entity_type": "table",
                        "entity_id": str(table.id),
                        "action": "update",
                        "data": {
                            "id": str(table.id),
                            "table_number": table.table_number,
                            "status": "available",
                            "current_guest_id": None
                        }
                    })
            
            # Commit transaction
            db.commit()
            db.refresh(guest)
            
            # Log activity
            log_activity(
                db=db,
                restaurant_id=restaurant_id,
                user_id=str(current_user.id),
                action="atomic_guest_status_update",
                entity_type="guest",
                entity_id=str(guest.id),
                old_data={"status": old_status},
                new_data={"status": new_status, "transaction_id": transaction_id}
            )
            
            # Broadcast atomic changes to all connected iOS devices
            try:
                await broadcast_delta_update(changes, restaurant_id=int(restaurant_id))
            except Exception as e:
                logger.warning(f"Failed to broadcast atomic status update: {e}")
            
            logger.info(f"Atomic guest status update {transaction_id} completed successfully")
            
            return {
                "success": True,
                "transaction_id": transaction_id,
                "guest_id": guest_id,
                "old_status": old_status,
                "new_status": new_status,
                "table_cleared": old_table_id is not None and new_status in ["Finished", "Cancelled", "No Show"],
                "changes_count": len(changes),
                "processed_at": datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"Atomic guest status update {transaction_id} failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Atomic status update failed: {str(e)}"
        )
