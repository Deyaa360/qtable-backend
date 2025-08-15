from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models import Reservation, RestaurantTable, Guest, Restaurant, User
from app.schemas import ReservationResponse, ReservationCreate, ReservationUpdate
from app.dependencies import get_current_user, verify_restaurant_access
from app.utils.database_helper import log_activity

router = APIRouter(prefix="/restaurants", tags=["reservations"])

def reservation_to_response(reservation: Reservation) -> ReservationResponse:
    """Convert database reservation model to response schema"""
    return ReservationResponse(
        id=str(reservation.id),
        guestName=reservation.guest_name,
        partySize=reservation.party_size,
        status=reservation.status,
        reservationTime=reservation.reservation_time,
        checkInTime=reservation.check_in_time,
        seatedTime=reservation.seated_time,
        finishedTime=reservation.finished_time,
        assignedTableId=str(reservation.table_id) if reservation.table_id else None,
        contactInfo=reservation.guest_phone,
        notes=reservation.notes,
        createdAt=reservation.created_at,
        lastUpdated=reservation.updated_at
    )

@router.get("/{restaurant_id}/reservations", response_model=List[ReservationResponse])
async def get_reservations(
    restaurant_id: str = Path(..., description="Restaurant ID"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    date_filter: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get reservations for a restaurant"""
    
    # Base query (RLS will automatically filter by restaurant)
    query = db.query(Reservation).filter(Reservation.restaurant_id == restaurant_id)
    
    # Apply filters
    if status_filter:
        query = query.filter(Reservation.status == status_filter)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, "%Y-%m-%d").date()
            query = query.filter(Reservation.created_at.date() == filter_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
    
    # Order by creation time (newest first)
    reservations = query.order_by(Reservation.created_at.desc()).all()
    
    return [reservation_to_response(reservation) for reservation in reservations]

@router.post("/{restaurant_id}/reservations", response_model=ReservationResponse)
async def create_reservation(
    reservation_data: ReservationCreate,
    restaurant_id: str = Path(..., description="Restaurant ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new reservation (walk-in or scheduled)"""
    
    # Create reservation
    reservation = Reservation(
        restaurant_id=restaurant_id,
        guest_name=reservation_data.guest_name,
        party_size=reservation_data.party_size,
        reservation_time=reservation_data.reservation_time,
        guest_phone=reservation_data.contact_info,
        notes=reservation_data.notes,
        status=reservation_data.status or "waitlist"
    )
    
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    
    # Log activity
    log_activity(
        db=db,
        restaurant_id=restaurant_id,
        user_id=str(current_user.id),
        action="reservation_create",
        entity_type="reservation",
        entity_id=str(reservation.id),
        new_data={
            "guest_name": reservation.guest_name,
            "party_size": reservation.party_size,
            "status": reservation.status
        }
    )
    
    return reservation_to_response(reservation)

@router.put("/{restaurant_id}/reservations/{reservation_id}", response_model=ReservationResponse)
async def update_reservation(
    reservation_data: ReservationUpdate,
    restaurant_id: str = Path(..., description="Restaurant ID"),
    reservation_id: str = Path(..., description="Reservation ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a reservation (status changes, table assignments, etc.)"""
    
    # Get the reservation
    reservation = db.query(Reservation).filter(
        Reservation.id == reservation_id,
        Reservation.restaurant_id == restaurant_id
    ).first()
    
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found"
        )
    
    # Store old data for logging
    old_data = {
        "status": reservation.status,
        "table_id": str(reservation.table_id) if reservation.table_id else None
    }
    
    # Update fields that were provided
    if reservation_data.guest_name is not None:
        reservation.guest_name = reservation_data.guest_name
    if reservation_data.party_size is not None:
        reservation.party_size = reservation_data.party_size
    if reservation_data.status is not None:
        reservation.status = reservation_data.status
    if reservation_data.assigned_table_id is not None:
        reservation.table_id = reservation_data.assigned_table_id
        
        # If assigning to a table, update table status too
        if reservation_data.assigned_table_id:
            table = db.query(RestaurantTable).filter(
                RestaurantTable.id == reservation_data.assigned_table_id,
                RestaurantTable.restaurant_id == restaurant_id
            ).first()
            
            if not table:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Table not found"
                )
            
            # Check table availability
            if table.status in ["occupied", "reserved"] and table.current_guest_id != reservation.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Table is not available"
                )
            
            # Update table
            table.status = "occupied" if reservation_data.status == "seated" else "reserved"
            table.current_guest_id = reservation.id
    
    # Set timestamps based on status changes
    if reservation_data.status == "arrived" and reservation_data.check_in_time:
        reservation.check_in_time = reservation_data.check_in_time
    elif reservation_data.status == "seated" and reservation_data.seated_time:
        reservation.seated_time = reservation_data.seated_time
    elif reservation_data.status == "finished" and reservation_data.finished_time:
        reservation.finished_time = reservation_data.finished_time
        
        # Free up the table
        if reservation.table_id:
            table = db.query(RestaurantTable).filter(
                RestaurantTable.id == reservation.table_id
            ).first()
            if table:
                table.status = "available"
                table.current_guest_id = None
    
    if reservation_data.notes is not None:
        reservation.notes = reservation_data.notes
    
    # Save changes
    db.commit()
    db.refresh(reservation)
    
    # Log activity
    new_data = {
        "status": reservation.status,
        "table_id": str(reservation.table_id) if reservation.table_id else None
    }
    
    log_activity(
        db=db,
        restaurant_id=restaurant_id,
        user_id=str(current_user.id),
        action="reservation_update",
        entity_type="reservation",
        entity_id=str(reservation.id),
        old_data=old_data,
        new_data=new_data
    )
    
    return reservation_to_response(reservation)

@router.delete("/{restaurant_id}/reservations/{reservation_id}")
async def delete_reservation(
    restaurant_id: str = Path(..., description="Restaurant ID"),
    reservation_id: str = Path(..., description="Reservation ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete/cancel a reservation"""
    
    reservation = db.query(Reservation).filter(
        Reservation.id == reservation_id,
        Reservation.restaurant_id == restaurant_id
    ).first()
    
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reservation not found"
        )
    
    # Free up table if assigned
    if reservation.table_id:
        table = db.query(RestaurantTable).filter(
            RestaurantTable.id == reservation.table_id
        ).first()
        if table and table.current_guest_id == reservation.id:
            table.status = "available"
            table.current_guest_id = None
    
    # Update status to cancelled instead of deleting
    reservation.status = "cancelled"
    db.commit()
    
    # Log activity
    log_activity(
        db=db,
        restaurant_id=restaurant_id,
        user_id=str(current_user.id),
        action="reservation_cancel",
        entity_type="reservation",
        entity_id=str(reservation.id),
        old_data={"status": reservation.status}
    )
    
    return {"message": "Reservation cancelled successfully"}
