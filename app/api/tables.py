from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import RestaurantTable, Restaurant, User
from app.schemas import TableResponse, TableCreate, TableUpdate, Position
from app.dependencies import get_current_user, verify_restaurant_access
from app.utils.database_helper import log_activity

router = APIRouter(prefix="/restaurants", tags=["tables"])

def table_to_response(table: RestaurantTable) -> TableResponse:
    """Convert database table model to response schema"""
    return TableResponse(
        id=str(table.id),
        tableNumber=table.table_number,
        capacity=table.capacity,
        status=table.status,
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
        table.position_x = table_data.position.x
        table.position_y = table_data.position.y
    if table_data.shape is not None:
        table.shape = table_data.shape
    if table_data.section is not None:
        table.section = table_data.section
    if table_data.current_guest_id is not None:
        table.current_guest_id = table_data.current_guest_id
    
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
    
    # Create new table
    table = RestaurantTable(
        restaurant_id=restaurant_id,
        table_number=table_data.table_number,
        capacity=table_data.capacity,
        position_x=table_data.position.x,
        position_y=table_data.position.y,
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
