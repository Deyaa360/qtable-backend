from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from app.database import get_db
from app.models import Guest, RestaurantTable, Restaurant
from app.dependencies import get_current_user, verify_restaurant_access
from app.api.websockets import guest_to_ios_format, table_to_ios_format

router = APIRouter(prefix="/api", tags=["sync"])

class FullSyncResponse(BaseModel):
    restaurant_id: str
    timestamp: str
    guests: List[dict]
    tables: List[dict]
    total_guests: int
    total_tables: int

class DeltaChange(BaseModel):
    entity_type: str
    entity_id: str
    action: str  # "create", "update", "delete"
    timestamp: str
    data: Optional[dict] = None

class DeltaResponse(BaseModel):
    since_timestamp: str
    current_timestamp: str
    changes: List[DeltaChange]
    has_more: bool

class BatchUpdateItem(BaseModel):
    entity_type: str  # "guest" or "table"
    entity_id: str
    data: dict

class BatchUpdateRequest(BaseModel):
    updates: List[BatchUpdateItem]
    timestamp: str

class BatchUpdateResponse(BaseModel):
    success: bool
    processed_count: int
    failed_count: int
    errors: List[str]
    timestamp: str

@router.get("/sync/full", response_model=FullSyncResponse)
async def get_full_sync(
    restaurant_id: str = Query(..., description="Restaurant ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Full data synchronization endpoint
    
    Returns complete dataset for a restaurant including all guests and tables.
    Used by iOS app for initial sync or when WebSocket connection is unavailable.
    """
    try:
        # Get all guests for the restaurant
        guests = db.query(Guest).filter(Guest.restaurant_id == restaurant_id).all()
        guest_data = [guest_to_ios_format(guest) for guest in guests]
        
        # Get all tables for the restaurant
        tables = db.query(RestaurantTable).filter(RestaurantTable.restaurant_id == restaurant_id).all()
        table_data = [table_to_ios_format(table) for table in tables]
        
        return FullSyncResponse(
            restaurant_id=restaurant_id,
            timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            guests=guest_data,
            tables=table_data,
            total_guests=len(guest_data),
            total_tables=len(table_data)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve full sync data: {str(e)}"
        )

@router.get("/sync/delta", response_model=DeltaResponse)
async def get_delta_sync(
    restaurant_id: str = Query(..., description="Restaurant ID"),
    since: str = Query(..., description="ISO timestamp of last sync"),
    limit: int = Query(100, description="Maximum number of changes to return"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delta synchronization endpoint
    
    Returns only changes since the specified timestamp.
    Used by iOS app for efficient incremental sync when WebSocket is unavailable.
    """
    try:
        # Parse since timestamp
        try:
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid timestamp format. Use ISO 8601 format."
            )
        
        changes = []
        
        # Get updated guests since timestamp
        updated_guests = db.query(Guest).filter(
            Guest.restaurant_id == restaurant_id,
            Guest.updated_at > since_dt
        ).limit(limit // 2).all()
        
        for guest in updated_guests:
            changes.append(DeltaChange(
                entity_type="guest",
                entity_id=str(guest.id),
                action="update",  # Simplified - could track create/update separately
                timestamp=guest.updated_at.isoformat().replace('+00:00', 'Z'),
                data=guest_to_ios_format(guest)
            ))
        
        # Get updated tables since timestamp
        updated_tables = db.query(RestaurantTable).filter(
            RestaurantTable.restaurant_id == restaurant_id,
            RestaurantTable.updated_at > since_dt
        ).limit(limit // 2).all()
        
        for table in updated_tables:
            changes.append(DeltaChange(
                entity_type="table",
                entity_id=str(table.id),
                action="update",
                timestamp=table.updated_at.isoformat().replace('+00:00', 'Z'),
                data=table_to_ios_format(table)
            ))
        
        # Sort changes by timestamp
        changes.sort(key=lambda x: x.timestamp)
        
        # Limit to requested number of changes
        changes = changes[:limit]
        
        return DeltaResponse(
            since_timestamp=since,
            current_timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            changes=changes,
            has_more=len(changes) == limit
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve delta sync data: {str(e)}"
        )

@router.post("/sync/batch", response_model=BatchUpdateResponse)
async def batch_update(
    request: BatchUpdateRequest,
    restaurant_id: str = Query(..., description="Restaurant ID"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Batch update endpoint
    
    Allows iOS app to send multiple updates in a single request.
    Useful for offline scenarios where multiple changes need to be synced.
    """
    processed_count = 0
    failed_count = 0
    errors = []
    
    try:
        # Start database transaction for batch updates
        with db.begin():
            for update_item in request.updates:
                try:
                    if update_item.entity_type == "guest":
                        guest = db.query(Guest).filter(Guest.id == update_item.entity_id).first()
                        if guest:
                            # Update guest fields
                            for field, value in update_item.data.items():
                                if hasattr(guest, field):
                                    setattr(guest, field, value)
                            guest.updated_at = datetime.now(timezone.utc)
                            processed_count += 1
                        else:
                            failed_count += 1
                            errors.append(f"Guest {update_item.entity_id} not found")
                            
                    elif update_item.entity_type == "table":
                        table = db.query(RestaurantTable).filter(RestaurantTable.id == update_item.entity_id).first()
                        if table:
                            # Update table fields
                            for field, value in update_item.data.items():
                                if hasattr(table, field):
                                    setattr(table, field, value)
                            table.updated_at = datetime.now(timezone.utc)
                            processed_count += 1
                        else:
                            failed_count += 1
                            errors.append(f"Table {update_item.entity_id} not found")
                    else:
                        failed_count += 1
                        errors.append(f"Unknown entity type: {update_item.entity_type}")
                        
                except Exception as e:
                    failed_count += 1
                    errors.append(f"Failed to update {update_item.entity_type} {update_item.entity_id}: {str(e)}")
            
            # Commit all changes
            db.commit()
            
        return BatchUpdateResponse(
            success=failed_count == 0,
            processed_count=processed_count,
            failed_count=failed_count,
            errors=errors,
            timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch update failed: {str(e)}"
        )

@router.get("/sync/health")
async def sync_health_check():
    """Health check endpoint for sync services"""
    return {
        "status": "healthy",
        "service": "sync_api",
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "endpoints": [
            "/api/sync/full",
            "/api/sync/delta", 
            "/api/sync/batch"
        ],
        "features": [
            "full_synchronization",
            "delta_updates",
            "batch_operations",
            "conflict_detection",
            "offline_support"
        ]
    }
