from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List
import logging
from datetime import datetime
from app.database import get_db
from app.models import RestaurantTable, Restaurant, User, Guest
from app.schemas import TableResponse, TableCreate, TableUpdate, Position
from app.dependencies import get_current_user, verify_restaurant_access
from app.utils.database_helper import log_activity
from app.utils.realtime_broadcaster import realtime_broadcaster
from app.api.websockets import broadcast_table_updated, broadcast_table_data_change, broadcast_guest_updated

router = APIRouter(prefix="/restaurants", tags=["tables"])
logger = logging.getLogger(__name__)

# Canvas size constants for coordinate conversion
CANVAS_WIDTH = 800.0
CANVAS_HEIGHT = 600.0

def normalize_position(position: Position) -> Position:
    """Convert pixel coordinates to normalized (0.0-1.0) coordinates if needed"""
    x = position.x
    y = position.y
    
    # If coordinates are > 1.0, assume they're pixel coordinates and convert
    if x > 1.0:
        x = x / CANVAS_WIDTH
    if y > 1.0:
        y = y / CANVAS_HEIGHT
    
    # Ensure coordinates are within bounds
    x = max(0.0, min(1.0, x))
    y = max(0.0, min(1.0, y))
    
    return Position(x=x, y=y)

def table_to_response(table: RestaurantTable) -> TableResponse:
    """Convert database table model to response schema"""
    # Convert snake_case status to camelCase for iOS compatibility
    status_mapping = {
        'out_of_service': 'outOfService',
        'available': 'available',
        'occupied': 'occupied',
        'reserved': 'reserved'
    }
    
    return TableResponse(
        id=str(table.id),
        tableNumber=table.table_number,
        capacity=table.capacity,
        status=status_mapping.get(table.status, table.status),
        position=Position(x=table.position_x, y=table.position_y),
        shape=table.shape,
        section=table.section,
        currentGuestId=str(table.current_guest_id) if table.current_guest_id else None,
        lastUpdated=table.updated_at,
        createdAt=table.created_at
    )

@router.get("/{restaurant_id}/tables", response_model=List[TableResponse])
async def get_tables(
    restaurant_id: str = Path(..., description="Restaurant ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all tables for a restaurant (floor plan)"""
    
    # Query tables for this restaurant (RLS will automatically filter)
    tables = db.query(RestaurantTable).filter(
        RestaurantTable.restaurant_id == restaurant_id,
        RestaurantTable.is_active == True
    ).order_by(RestaurantTable.table_number).all()
    
    return [table_to_response(table) for table in tables]

@router.put("/{restaurant_id}/tables/{table_id}", response_model=TableResponse)
async def update_table(
    table_data: TableUpdate,
    restaurant_id: str = Path(..., description="Restaurant ID"),
    table_id: str = Path(..., description="Table ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a table (typically status changes)"""
    
    # Get the table
    table = db.query(RestaurantTable).filter(
        RestaurantTable.id == table_id,
        RestaurantTable.restaurant_id == restaurant_id
    ).first()
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    # Store old data for logging
    old_data = {
        "status": table.status,
        "current_guest_id": str(table.current_guest_id) if table.current_guest_id else None
    }
    
    # Update fields that were provided
    if table_data.table_number is not None:
        table.table_number = table_data.table_number
    if table_data.capacity is not None:
        table.capacity = table_data.capacity
    if table_data.status is not None:
        table.status = table_data.status
    if table_data.position is not None:
        normalized_position = normalize_position(table_data.position)
        table.position_x = normalized_position.x
        table.position_y = normalized_position.y
    if table_data.shape is not None:
        table.shape = table_data.shape
    if table_data.section is not None:
        table.section = table_data.section
    
    # Handle both current_guest_id and currentGuestId (for iOS compatibility)
    guest_id_to_set = None
    if table_data.current_guest_id is not None:
        guest_id_to_set = table_data.current_guest_id
    elif table_data.currentGuestId is not None:
        guest_id_to_set = table_data.currentGuestId
    
    # CRITICAL FIX: Handle table clearing properly to avoid constraint violation
    # If we're clearing a table (setting status to available AND clearing guest_id)
    is_clearing_table = (
        table_data.status == "available" and 
        (guest_id_to_set == "" or guest_id_to_set is None) and
        table.current_guest_id is not None
    )
    
    if is_clearing_table:
        # When clearing a table, MUST clear guest_id FIRST, then set status
        logger.info(f"🧹 Clearing table {table.id}: guest_id {table.current_guest_id} -> None, status {table.status} -> available")
        
        # Update the guest status to finished if guest exists (before clearing the reference)
        current_guest_id = table.current_guest_id
        if current_guest_id:
            guest = db.query(Guest).filter(Guest.id == current_guest_id).first()
            if guest and guest.status == "Seated":
                guest.status = "finished"
                guest.table_id = None
                logger.info(f"👤 Updated guest {guest.id} status to finished")
        
        # Now clear the table assignment
        table.current_guest_id = None
        table.status = "available"
    else:
        # Normal update flow - set guest_id first, then status
        if guest_id_to_set is not None:
            table.current_guest_id = guest_id_to_set
        
        # Enforce business rule: Only occupied tables can have currentGuestId
        if table_data.status is not None:
            if table_data.status == "available" and table.current_guest_id:
                # If setting table to available but it still has a guest, clear the guest first
                logger.warning(f"⚠️ Setting table {table.id} to available but it has guest {table.current_guest_id}, clearing guest")
                table.current_guest_id = None
            table.status = table_data.status
    
    # Save changes
    db.commit()
    db.refresh(table)
    
    # Log activity
    new_data = {
        "status": table.status,
        "current_guest_id": str(table.current_guest_id) if table.current_guest_id else None
    }
    
    log_activity(
        db=db,
        restaurant_id=restaurant_id,
        user_id=str(current_user.id),
        action="table_update",
        entity_type="table",
        entity_id=str(table.id),
        old_data=old_data,
        new_data=new_data
    )
    
    # 🚀 REAL-TIME BROADCAST: PRIORITY #3 - Table status updates
    try:
        await realtime_broadcaster.broadcast_table_updated(
            restaurant_id=restaurant_id,
            table_id=str(table.id),
            table_data={
                "status": table.status,
                "guest_id": str(table.current_guest_id) if table.current_guest_id else None
            }
        )
        logger.info(f"📡 Real-time broadcast sent for table update: {table.id}")
    except Exception as e:
        logger.warning(f"Failed to broadcast real-time table_updated: {e}")
    
    # Legacy broadcast for backward compatibility
    try:
        await broadcast_table_updated(table)
    except Exception as e:
        logger.warning(f"Failed to broadcast legacy table_updated: {e}")
    
    return table_to_response(table)

@router.post("/{restaurant_id}/tables", response_model=TableResponse)
async def create_table(
    table_data: TableCreate,
    restaurant_id: str = Path(..., description="Restaurant ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new table"""
    
    # Check if table number already exists
    existing_table = db.query(RestaurantTable).filter(
        RestaurantTable.restaurant_id == restaurant_id,
        RestaurantTable.table_number == table_data.table_number
    ).first()
    
    if existing_table:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Table {table_data.table_number} already exists"
        )
    
    # Normalize position coordinates
    normalized_position = normalize_position(table_data.position)
    
    # Create new table
    table = RestaurantTable(
        restaurant_id=restaurant_id,
        table_number=table_data.table_number,
        capacity=table_data.capacity,
        position_x=normalized_position.x,
        position_y=normalized_position.y,
        shape=table_data.shape,
        section=table_data.section
    )
    
    db.add(table)
    db.commit()
    db.refresh(table)
    
    # Log activity
    log_activity(
        db=db,
        restaurant_id=restaurant_id,
        user_id=str(current_user.id),
        action="table_create",
        entity_type="table",
        entity_id=str(table.id),
        new_data={"table_number": table.table_number, "capacity": table.capacity}
    )
    
    return table_to_response(table)

@router.delete("/{restaurant_id}/tables/{table_id}")
async def delete_table(
    restaurant_id: str = Path(..., description="Restaurant ID"),
    table_id: str = Path(..., description="Table ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a table (soft delete)"""
    
    table = db.query(RestaurantTable).filter(
        RestaurantTable.id == table_id,
        RestaurantTable.restaurant_id == restaurant_id
    ).first()
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    # Check if table is currently occupied
    if table.status == "occupied":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete an occupied table"
        )
    
    # Soft delete
    table.is_active = False
    db.commit()
    
    # Log activity
    log_activity(
        db=db,
        restaurant_id=restaurant_id,
        user_id=str(current_user.id),
        action="table_delete",
        entity_type="table",
        entity_id=str(table.id),
        old_data={"table_number": table.table_number}
    )
    
    return {"message": "Table deleted successfully"}

@router.put("/{restaurant_id}/tables/{table_id}/clear", response_model=dict)
async def clear_table(
    restaurant_id: str = Path(..., description="Restaurant ID"),
    table_id: str = Path(..., description="Table ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Clear a table - dedicated endpoint for iOS app table clearing
    This endpoint properly handles the business rule constraints
    """
    # Get the table
    table = db.query(RestaurantTable).filter(
        RestaurantTable.id == table_id,
        RestaurantTable.restaurant_id == restaurant_id,
        RestaurantTable.is_active == True
    ).first()
    
    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )
    
    logger.info(f"🧹 CLEAR TABLE REQUEST: table_id={table_id}, current_status={table.status}, current_guest={table.current_guest_id}")
    
    # Store original data for response
    original_guest_id = table.current_guest_id
    guest_data = None
    
    # Update guest status to finished if there's a current guest
    if table.current_guest_id:
        guest = db.query(Guest).filter(Guest.id == table.current_guest_id).first()
        if guest:
            logger.info(f"👤 Found guest {guest.id} with status {guest.status}, updating to finished")
            guest.status = "finished"
            guest.table_id = None
            guest.finished_time = datetime.utcnow()
            guest_data = {
                "id": guest.id,
                "status": "finished",
                "assignedTableId": None,
                "finishedTime": guest.finished_time.isoformat() + "Z",
                "lastUpdated": datetime.utcnow().isoformat() + "Z"
            }
            
            # Broadcast guest update
            try:
                await broadcast_guest_updated(guest)
                logger.info(f"📡 Broadcasted guest update for {guest.id}")
            except Exception as e:
                logger.warning(f"Failed to broadcast guest update: {e}")
    
    # Clear table (order is critical to avoid constraint violation)
    table.current_guest_id = None  # Clear guest reference FIRST
    table.status = "available"     # Then set status to available
    
    db.commit()
    db.refresh(table)
    
    logger.info(f"✅ Table {table_id} cleared successfully")
    
    # Broadcast table update
    try:
        await broadcast_table_updated(table)
        await realtime_broadcaster.broadcast_delta({
            "type": "table_updated",
            "data": {
                "id": table.id,
                "status": table.status,
                "currentGuestId": None
            }
        })
        logger.info(f"📡 Broadcasted table clear for {table_id}")
    except Exception as e:
        logger.warning(f"Failed to broadcast table update: {e}")
    
    # Log activity
    log_activity(
        db=db,
        restaurant_id=restaurant_id,
        user_id=str(current_user.id),
        action="table_clear",
        entity_type="table",
        entity_id=str(table.id),
        old_data={
            "status": "occupied",
            "current_guest_id": original_guest_id
        },
        new_data={
            "status": "available", 
            "current_guest_id": None
        }
    )
    
    # Return success response with both table and guest data
    response = {
        "success": True,
        "message": "Table cleared successfully",
        "table": {
            "id": table.id,
            "status": "available",
            "currentGuestId": None,
            "lastUpdated": table.updated_at.isoformat() + "Z"
        }
    }
    
    if guest_data:
        response["guest"] = guest_data
    
    return response

@router.post("/{restaurant_id}/tables/bulk", response_model=List[TableResponse])
async def bulk_sync_tables(
    tables_data: List[TableUpdate],
    restaurant_id: str = Path(..., description="Restaurant ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Bulk sync tables (for syncing entire floor plan from iPad)"""
    
    updated_tables = []
    
    for table_update in tables_data:
        # This would need table_id in the update data
        # Implementation depends on how the iPad sends bulk updates
        pass
    
    return updated_tables
