from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, and_
from typing import Optional
from datetime import datetime
from app.database import get_db
from app.models import Guest, RestaurantTable, Restaurant, User
from app.schemas.dashboard import (
    DashboardDataResponse, MinimalGuestResponse, MinimalTableResponse, 
    DashboardStatsResponse, DeltaUpdatesResponse, GuestUpdate, TableUpdate
)
from app.schemas.guest import GuestResponse
from app.schemas.table import TableResponse, Position
from app.dependencies import get_current_user, verify_restaurant_access
from app.utils.cache import cached, invalidate_cache_pattern
import logging

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
logger = logging.getLogger(__name__)

# Original restaurant-specific endpoint (keeping for compatibility)
restaurant_router = APIRouter(prefix="/restaurants", tags=["dashboard"])

def guest_to_minimal_response(guest: Guest) -> MinimalGuestResponse:
    """Convert guest to minimal response for performance"""
    full_name = f"{guest.first_name or ''} {guest.last_name or ''}".strip()
    if not full_name:
        full_name = "Unknown Guest"
    
    return MinimalGuestResponse(
        id=str(guest.id),
        name=full_name,
        status=guest.status or "waitlist",
        tableId=guest.table_id,
        partySize=guest.party_size,
        lastUpdated=guest.updated_at
    )

def table_to_minimal_response(table: RestaurantTable) -> MinimalTableResponse:
    """Convert table to minimal response for performance"""
    return MinimalTableResponse(
        id=str(table.id),
        tableNumber=table.table_number,
        capacity=table.capacity,  # ADDED: Required for iOS app compatibility
        position=Position(x=table.position_x, y=table.position_y),  # ADDED: Required for floor plan positioning
        status=table.status,
        currentGuestId=str(table.current_guest_id) if table.current_guest_id else None,
        lastUpdated=table.updated_at
    )

def guest_to_full_response(guest: Guest) -> GuestResponse:
    """Convert guest to full response when needed"""
    full_name = f"{guest.first_name or ''} {guest.last_name or ''}".strip()
    if not full_name:
        full_name = "Unknown Guest"
    
    return GuestResponse(
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

def table_to_full_response(table: RestaurantTable) -> TableResponse:
    """Convert table to full response when needed"""
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

@router.get("/{restaurant_id}/dashboard-data", response_model=DashboardDataResponse)
@cached(timeout=30, key_prefix="dashboard")  # Cache for 30 seconds
async def get_dashboard_data(
    restaurant_id: str = Path(..., description="Restaurant ID"),
    since: Optional[datetime] = Query(None, description="ISO8601 timestamp for delta updates"),
    minimal: bool = Query(True, description="Return minimal data for performance"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DashboardDataResponse:
    """
    Optimized dashboard data endpoint that replaces separate /guests and /tables calls.
    Supports both full and delta syncing with minimal data transfer.
    """
    logger.info(f"Dashboard data request - since: {since}, minimal: {minimal}")
    
    # Build base queries with optimized loading
    guests_query = db.query(Guest)  # All guests for now (multi-tenancy temporarily disabled)
    tables_query = db.query(RestaurantTable).options(
        joinedload(RestaurantTable.reservations)
    ).filter(
        RestaurantTable.restaurant_id == restaurant_id,
        RestaurantTable.is_active == True
    )
    
    # If 'since' is provided, only get updated records (delta sync)
    if since:
        guests_query = guests_query.filter(Guest.updated_at > since)
        tables_query = tables_query.filter(RestaurantTable.updated_at > since)
        is_full_sync = False
    else:
        is_full_sync = True
    
    # Execute queries
    guests = guests_query.order_by(Guest.created_at.desc()).all()
    tables = tables_query.order_by(RestaurantTable.table_number).all()
    
    # Convert to appropriate response format
    if minimal:
        guest_responses = [guest_to_minimal_response(guest) for guest in guests]
        table_responses = [table_to_minimal_response(table) for table in tables]
    else:
        guest_responses = [guest_to_full_response(guest) for guest in guests]
        table_responses = [table_to_full_response(table) for table in tables]
    
    # Calculate dashboard statistics (only for full sync to avoid expensive queries)
    if is_full_sync:
        # Get all guests and tables for stats calculation
        all_guests = db.query(Guest).filter(Guest.restaurant_id == restaurant_id).all()  # FIXED: Multi-tenant filtering
        all_tables = db.query(RestaurantTable).filter(
            RestaurantTable.restaurant_id == restaurant_id,
            RestaurantTable.is_active == True
        ).all()
        
        # Calculate guest statistics
        guest_status_counts = {}
        for guest in all_guests:
            status = guest.status or "waitlist"
            guest_status_counts[status] = guest_status_counts.get(status, 0) + 1
        
        # Calculate table statistics
        table_status_counts = {}
        occupied_tables = 0
        for table in all_tables:
            status = table.status or "available"
            table_status_counts[status] = table_status_counts.get(status, 0) + 1
            if status == "occupied":
                occupied_tables += 1
        
        # Calculate occupancy rate
        total_tables = len(all_tables)
        occupancy_rate = (occupied_tables / total_tables) if total_tables > 0 else 0.0
        
        stats = DashboardStatsResponse(
            total_guests=len(all_guests),
            total_tables=total_tables,
            occupancy_rate=round(occupancy_rate, 2),
            guests_by_status=guest_status_counts,
            tables_by_status=table_status_counts
        )
    else:
        # For delta updates, don't recalculate expensive stats
        stats = DashboardStatsResponse(
            total_guests=0,
            total_tables=0,
            occupancy_rate=0.0,
            guests_by_status={},
            tables_by_status={}
        )
    
    logger.info(f"Dashboard data response: {len(guest_responses)} guests, {len(table_responses)} tables")
    
    return DashboardDataResponse(
        guests=guest_responses,
        tables=table_responses,
        stats=stats,
        lastUpdated=datetime.utcnow(),
        isFullSync=is_full_sync
    )

@router.get("/{restaurant_id}/updates", response_model=DeltaUpdatesResponse)
async def get_delta_updates(
    restaurant_id: str = Path(..., description="Restaurant ID"),
    since: datetime = Query(..., description="ISO8601 timestamp for delta updates"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delta/incremental updates endpoint - returns only changes since the specified timestamp.
    Optimized for minimal network traffic and fast synchronization.
    """
    logger.info(f"Delta updates request since: {since}")
    
    # Get updated guests
    updated_guests = db.query(Guest).filter(Guest.updated_at > since).all()
    
    # Get updated tables
    updated_tables = db.query(RestaurantTable).filter(
        RestaurantTable.restaurant_id == restaurant_id,
        RestaurantTable.is_active == True,
        RestaurantTable.updated_at > since
    ).all()
    
    # Convert to update format
    guest_updates = [
        GuestUpdate(
            id=str(guest.id),
            action="updated",  # In future, track actual action type
            data=guest_to_minimal_response(guest),
            lastUpdated=guest.updated_at
        )
        for guest in updated_guests
    ]
    
    table_updates = [
        TableUpdate(
            id=str(table.id),
            action="updated",  # In future, track actual action type
            data=table_to_minimal_response(table),
            lastUpdated=table.updated_at
        )
        for table in updated_tables
    ]
    
    # TODO: Implement actual deletion tracking in future
    # For now, return empty arrays
    deleted_guests = []
    deleted_tables = []
    
    logger.info(f"Delta updates: {len(guest_updates)} guests, {len(table_updates)} tables")
    
    return DeltaUpdatesResponse(
        guestUpdates=guest_updates,
        tableUpdates=table_updates,
        deletedGuests=deleted_guests,
        deletedTables=deleted_tables,
        timestamp=datetime.utcnow()
    )

# ===== NEW API V1 ENDPOINTS =====
# These endpoints match the iOS app expectations

@router.get("/data", response_model=DashboardDataResponse)
@cached(timeout=30, key_prefix="dashboard_v1")  # Cache for 30 seconds
async def get_dashboard_data_v1(
    since: Optional[datetime] = Query(None, description="ISO8601 timestamp for delta updates"),
    minimal: bool = Query(True, description="Return minimal data for performance"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DashboardDataResponse:
    """
    iOS-compatible dashboard data endpoint: /api/v1/dashboard/data
    Automatically uses the current user's restaurant context.
    """
    logger.info(f"V1 Dashboard data request - user: {current_user.email}, since: {since}, minimal: {minimal}")
    
    restaurant_id = current_user.restaurant_id
    
    # Build base queries with optimized loading - using restaurant_id from authenticated user
    guests_query = db.query(Guest).filter(Guest.restaurant_id == restaurant_id)  # FIXED: Multi-tenant filtering
    tables_query = db.query(RestaurantTable).options(
        joinedload(RestaurantTable.reservations)
    ).filter(
        RestaurantTable.restaurant_id == restaurant_id,
        RestaurantTable.is_active == True
    )
    
    # If 'since' is provided, only get updated records (delta sync)
    if since:
        guests_query = guests_query.filter(Guest.updated_at > since)
        tables_query = tables_query.filter(RestaurantTable.updated_at > since)
        is_full_sync = False
    else:
        is_full_sync = True
    
    # Execute queries
    guests = guests_query.order_by(Guest.created_at.desc()).all()
    tables = tables_query.order_by(RestaurantTable.table_number).all()
    
    # Convert to appropriate response format
    if minimal:
        guest_responses = [guest_to_minimal_response(guest) for guest in guests]
        table_responses = [table_to_minimal_response(table) for table in tables]
    else:
        guest_responses = [guest_to_full_response(guest) for guest in guests]
        table_responses = [table_to_full_response(table) for table in tables]
    
    # Calculate dashboard statistics (only for full sync to avoid expensive queries)
    if is_full_sync:
        # Get all guests and tables for stats calculation
        all_guests = db.query(Guest).filter(Guest.restaurant_id == restaurant_id).all()  # FIXED: Multi-tenant filtering
        all_tables = db.query(RestaurantTable).filter(
            RestaurantTable.restaurant_id == restaurant_id,
            RestaurantTable.is_active == True
        ).all()
        
        # Calculate guest statistics
        guest_status_counts = {}
        for guest in all_guests:
            status = guest.status or "waitlist"
            guest_status_counts[status] = guest_status_counts.get(status, 0) + 1
        
        # Calculate table statistics
        table_status_counts = {}
        occupied_tables = 0
        for table in all_tables:
            status = table.status or "available"
            table_status_counts[status] = table_status_counts.get(status, 0) + 1
            if status == "occupied":
                occupied_tables += 1
        
        # Calculate occupancy rate
        total_tables = len(all_tables)
        occupancy_rate = (occupied_tables / total_tables) if total_tables > 0 else 0.0
        
        stats = DashboardStatsResponse(
            total_guests=len(all_guests),
            total_tables=total_tables,
            occupancy_rate=round(occupancy_rate, 2),
            guests_by_status=guest_status_counts,
            tables_by_status=table_status_counts
        )
    else:
        # For delta updates, don't recalculate expensive stats
        stats = DashboardStatsResponse(
            total_guests=0,
            total_tables=0,
            occupancy_rate=0.0,
            guests_by_status={},
            tables_by_status={}
        )
    
    logger.info(f"V1 Dashboard data response: {len(guest_responses)} guests, {len(table_responses)} tables")
    
    return DashboardDataResponse(
        guests=guest_responses,
        tables=table_responses,
        stats=stats,
        lastUpdated=datetime.utcnow(),
        isFullSync=is_full_sync
    )

# ===== ORIGINAL RESTAURANT-SPECIFIC ENDPOINTS =====
# Keep these for backward compatibility

@restaurant_router.get("/{restaurant_id}/dashboard-data", response_model=DashboardDataResponse)
@cached(timeout=30, key_prefix="restaurant_dashboard")  # Cache for 30 seconds
async def get_dashboard_data_restaurant(
    restaurant_id: str = Path(..., description="Restaurant ID"),
    since: Optional[datetime] = Query(None, description="ISO8601 timestamp for delta updates"),
    minimal: bool = Query(True, description="Return minimal data for performance"),
    restaurant: Restaurant = Depends(verify_restaurant_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DashboardDataResponse:
    """
    Original restaurant-specific dashboard endpoint (kept for compatibility).
    Use /api/v1/dashboard/data for new implementations.
    """
    # This is the original implementation - just call the main function
    # but we need to modify it to work with the restaurant_id parameter
    return await get_restaurant_dashboard_data(restaurant_id, since, minimal, restaurant, current_user, db)

async def get_restaurant_dashboard_data(
    restaurant_id: str,
    since: Optional[datetime],
    minimal: bool,
    restaurant: Restaurant,
    current_user: User,
    db: Session
) -> DashboardDataResponse:
    """Implementation for restaurant-specific dashboard data"""
    logger.info(f"Restaurant dashboard data request - restaurant: {restaurant_id}, since: {since}, minimal: {minimal}")
    
    # Build base queries with optimized loading
    guests_query = db.query(Guest)  # All guests for now (multi-tenancy temporarily disabled)
    tables_query = db.query(RestaurantTable).options(
        joinedload(RestaurantTable.reservations)
    ).filter(
        RestaurantTable.restaurant_id == restaurant_id,
        RestaurantTable.is_active == True
    )
    
    # If 'since' is provided, only get updated records (delta sync)
    if since:
        guests_query = guests_query.filter(Guest.updated_at > since)
        tables_query = tables_query.filter(RestaurantTable.updated_at > since)
        is_full_sync = False
    else:
        is_full_sync = True
    
    # Execute queries
    guests = guests_query.order_by(Guest.created_at.desc()).all()
    tables = tables_query.order_by(RestaurantTable.table_number).all()
    
    # Convert to appropriate response format
    if minimal:
        guest_responses = [guest_to_minimal_response(guest) for guest in guests]
        table_responses = [table_to_minimal_response(table) for table in tables]
    else:
        guest_responses = [guest_to_full_response(guest) for guest in guests]
        table_responses = [table_to_full_response(table) for table in tables]
    
    # Calculate dashboard statistics (only for full sync to avoid expensive queries)
    if is_full_sync:
        # Get all guests and tables for stats calculation
        all_guests = db.query(Guest).filter(Guest.restaurant_id == restaurant_id).all()  # FIXED: Multi-tenant filtering
        all_tables = db.query(RestaurantTable).filter(
            RestaurantTable.restaurant_id == restaurant_id,
            RestaurantTable.is_active == True
        ).all()
        
        # Calculate guest statistics
        guest_status_counts = {}
        for guest in all_guests:
            status = guest.status or "waitlist"
            guest_status_counts[status] = guest_status_counts.get(status, 0) + 1
        
        # Calculate table statistics
        table_status_counts = {}
        occupied_tables = 0
        for table in all_tables:
            status = table.status or "available"
            table_status_counts[status] = table_status_counts.get(status, 0) + 1
            if status == "occupied":
                occupied_tables += 1
        
        # Calculate occupancy rate
        total_tables = len(all_tables)
        occupancy_rate = (occupied_tables / total_tables) if total_tables > 0 else 0.0
        
        stats = DashboardStatsResponse(
            total_guests=len(all_guests),
            total_tables=total_tables,
            occupancy_rate=round(occupancy_rate, 2),
            guests_by_status=guest_status_counts,
            tables_by_status=table_status_counts
        )
    else:
        # For delta updates, don't recalculate expensive stats
        stats = DashboardStatsResponse(
            total_guests=0,
            total_tables=0,
            occupancy_rate=0.0,
            guests_by_status={},
            tables_by_status={}
        )
    
    logger.info(f"Restaurant dashboard data response: {len(guest_responses)} guests, {len(table_responses)} tables")
    
    return DashboardDataResponse(
        guests=guest_responses,
        tables=table_responses,
        stats=stats,
        lastUpdated=datetime.utcnow(),
        isFullSync=is_full_sync
    )
