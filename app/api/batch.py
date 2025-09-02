from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models import Guest, RestaurantTable, Restaurant, User
from app.schemas.batch import BatchUpdateRequest, BatchUpdateResponse, BatchGuestResponse, BatchTableResponse
from app.schemas.table import Position
from app.dependencies import get_current_user, verify_restaurant_access
from app.utils.database_helper import log_activity
from app.utils.realtime_broadcaster import realtime_broadcaster
import logging

router = APIRouter(prefix="/restaurants", tags=["batch-operations"])
logger = logging.getLogger(__name__)

def handle_guest_status_change_batch(db: Session, guest: Guest, old_status: str, new_status: str):
    """
    Handle automatic table clearing when guest status changes from "Seated" to any other status.
    This implements the business logic required by the iOS frontend for batch operations.
    """
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

def guest_to_batch_response(guest: Guest) -> BatchGuestResponse:
    """Convert database guest model to batch response schema"""
    full_name = f"{guest.first_name or ''} {guest.last_name or ''}".strip()
    if not full_name:
        full_name = "Unknown Guest"
    
    return BatchGuestResponse(
        id=str(guest.id),
        name=full_name,
        firstName=guest.first_name or "",
        lastName=guest.last_name or "",
        email=guest.email,
        phone=guest.phone,
        totalVisits=guest.total_visits,
        notes=guest.notes,
        dietaryRestrictions=guest.dietary_restrictions or [],
        specialRequests=guest.special_requests,
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

def table_to_batch_response(table: RestaurantTable) -> BatchTableResponse:
    """Convert database table model to batch response schema"""
    return BatchTableResponse(
        id=str(table.id),
        tableNumber=table.table_number,
        capacity=table.capacity,
        status=table.status,
        position={"x": table.position_x, "y": table.position_y},
        shape=table.shape,
        section=table.section,
        currentGuestId=str(table.current_guest_id) if table.current_guest_id else None,
        lastUpdated=table.updated_at,
        createdAt=table.created_at
    )

def sync_guest_table_relationship_batch(db: Session, guest_id: str, table_id: str = None, old_table_id: str = None):
    """
    Optimized version of guest-table relationship sync for batch operations
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
                    other_guest.status = "waitlist"
            
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

@router.post("/{restaurant_id}/batch-update", response_model=BatchUpdateResponse)
async def batch_update(
    batch_data: BatchUpdateRequest,
    restaurant_id: str = Path(..., description="Restaurant ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Batch update endpoint for high-performance operations.
    Updates multiple guests and tables atomically in a single transaction.
    """
    # 🚨 CRITICAL DEBUG: Use error level so it shows in Railway logs
    logger.error(f"🚨 [BATCH ENDPOINT] CALLED! Restaurant: {restaurant_id}")
    logger.error(f"🚨 [BATCH ENDPOINT] Guests to update: {len(batch_data.guests or [])}")
    logger.error(f"🚨 [BATCH ENDPOINT] Tables to update: {len(batch_data.tables or [])}")
    logger.error(f"🚨 [BATCH ENDPOINT] Current timestamp: {datetime.utcnow()}")
    
    logger.info(f"Batch update request: {len(batch_data.guests or [])} guests, {len(batch_data.tables or [])} tables")
    
    updated_guests = []
    updated_tables = []
    errors = []
    
    try:
        # Process guest updates
        if batch_data.guests:
            for guest_update in batch_data.guests:
                try:
                    guest = db.query(Guest).filter(Guest.id == guest_update.id).first()
                    if not guest:
                        errors.append(f"Guest {guest_update.id} not found")
                        continue
                    
                    # Store old table_id and status for relationship sync and status change detection
                    old_table_id = guest.table_id
                    old_status = guest.status
                    
                    # Handle status changes with automatic table clearing
                    if guest_update.status is not None:
                        handle_guest_status_change_batch(db, guest, old_status, guest_update.status)
                    
                    # Handle table assignment (both naming conventions)
                    table_id_to_set = guest_update.assignedTableId or guest_update.table_id
                    if table_id_to_set is not None:
                        guest.table_id = table_id_to_set
                        # Sync bidirectional relationship
                        sync_guest_table_relationship_batch(db, guest_update.id, table_id_to_set, old_table_id)
                    
                    # Handle timing fields (both naming conventions)
                    seated_time = guest_update.seatedTime or guest_update.seated_time
                    if seated_time is not None:
                        guest.seated_time = seated_time
                    
                    check_in_time = guest_update.checkInTime or guest_update.check_in_time
                    if check_in_time is not None:
                        guest.check_in_time = check_in_time
                    
                    finished_time = guest_update.finishedTime or guest_update.finished_time
                    if finished_time is not None:
                        guest.finished_time = finished_time
                    
                    party_size = guest_update.partySize or guest_update.party_size
                    if party_size is not None:
                        guest.party_size = party_size
                    
                    updated_guests.append(guest_to_batch_response(guest))
                    
                except Exception as e:
                    logger.error(f"Error updating guest {guest_update.id}: {e}")
                    errors.append(f"Error updating guest {guest_update.id}: {str(e)}")
        
        # Process table updates
        if batch_data.tables:
            for table_update in batch_data.tables:
                try:
                    table = db.query(RestaurantTable).filter(RestaurantTable.id == table_update.id).first()
                    if not table:
                        errors.append(f"Table {table_update.id} not found")
                        continue
                    
                    # Update table fields
                    if table_update.status is not None:
                        table.status = table_update.status
                    
                    # Handle guest assignment (both naming conventions)
                    guest_id_to_set = table_update.currentGuestId or table_update.current_guest_id
                    if guest_id_to_set is not None:
                        table.current_guest_id = guest_id_to_set
                    
                    updated_tables.append(table_to_batch_response(table))
                    
                except Exception as e:
                    logger.error(f"Error updating table {table_update.id}: {e}")
                    errors.append(f"Error updating table {table_update.id}: {str(e)}")
        
        # Commit all changes atomically
        db.commit()
        
        # 🚀 REAL-TIME BROADCAST: Send individual entity updates first
        try:
            # 🚨 CRITICAL DEBUG: Add error-level logging so it shows up in Railway
            logger.error(f"🚨 [BATCH] Starting broadcasts for {len(updated_guests)} guests, {len(updated_tables)} tables")
            logger.error(f"🚨 [BATCH] Restaurant ID: {restaurant_id}")
            logger.error(f"🚨 [BATCH] WebSocket connections: {realtime_broadcaster.connections}")
            
            # Broadcast individual guest updates (iOS requires these!)
            for guest in updated_guests:
                logger.error(f"🚨 [BATCH] About to broadcast guest_updated for guest {guest.id}")
                
                guest_data = {
                    "guestName": f"{guest.firstName or ''} {guest.lastName or ''}".strip(),
                    "firstName": guest.firstName or '',
                    "lastName": guest.lastName or '',
                    "partySize": guest.party_size or 1,
                    "status": guest.status,
                    "table_id": str(guest.table_id) if guest.table_id else None,
                    "email": guest.email or '',
                    "phone": guest.phone or '',
                    "notes": guest.notes or ''
                }
                
                await realtime_broadcaster.broadcast_guest_updated(
                    restaurant_id=restaurant_id,
                    guest_id=str(guest.id),
                    action="status_changed",  # Primary action for batch updates
                    guest_data=guest_data
                )
                logger.error(f"[BATCH] [BATCH] ✅ Successfully broadcasted guest_updated for guest {guest.id}")
            
            # Broadcast individual table updates
            for table in updated_tables:
                logger.error(f"🚨 [BATCH] About to broadcast table_updated for table {table.id}")
                
                await realtime_broadcaster.broadcast_table_updated(
                    restaurant_id=restaurant_id,
                    table_id=str(table.id),
                    action="status_changed",
                    table_data={
                        "id": str(table.id),
                        "table_number": table.table_number,
                        "status": table.status,
                        "current_guest_id": str(table.current_guest_id) if table.current_guest_id else None,
                        "capacity": table.capacity,
                        "x": table.position.get("x", 0.0),
                        "y": table.position.get("y", 0.0)
                    }
                )
                logger.error(f"[BATCH] [BATCH] ✅ Successfully broadcasted table_updated for table {table.id}")
                
        except Exception as e:
            logger.error(f"🚨 [BATCH] ❌ Failed to broadcast individual entity updates: {e}")
            import traceback
            logger.error(f"🚨 [BATCH] ❌ Traceback: {traceback.format_exc()}")
        
        # 🚀 REAL-TIME BROADCAST: PRIORITY #4 - Atomic transaction complete AFTER individual updates
        try:
            affected_entities = []
            for guest in updated_guests:
                affected_entities.append(f"guest-{guest.id}")
            for table in updated_tables:
                affected_entities.append(f"table-{table.id}")
            
            logger.error(f"🚨 [BATCH] About to broadcast atomic_transaction_complete for {len(affected_entities)} entities")
            
            await realtime_broadcaster.broadcast_atomic_transaction_complete(
                restaurant_id=restaurant_id,
                affected_entities=affected_entities
            )
            logger.error(f"[BATCH] [BATCH] ✅ Successfully broadcasted atomic_transaction_complete")
        except Exception as e:
            logger.error(f"🚨 [BATCH] ❌ Failed to broadcast atomic_transaction_complete: {e}")
            import traceback
            logger.error(f"🚨 [BATCH] ❌ Traceback: {traceback.format_exc()}")
        
        # Log the batch operation
        log_activity(
            db=db,
            restaurant_id=restaurant_id,
            user_id=str(current_user.id),
            action="batch_update",
            entity_type="batch",
            entity_id="batch_operation",
            new_data={
                "guests_updated": len(updated_guests),
                "tables_updated": len(updated_tables),
                "errors": len(errors)
            }
        )
        
        logger.info(f"Batch update completed: {len(updated_guests)} guests, {len(updated_tables)} tables updated")
        
        return BatchUpdateResponse(
            success=len(errors) == 0,
            updated_guests=updated_guests,
            updated_tables=updated_tables,
            timestamp=datetime.utcnow(),
            errors=errors if errors else None
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Batch update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch update failed: {str(e)}"
        )
