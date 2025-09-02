from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query
from fastapi.responses import HTMLResponse
from typing import Dict, List, Optional, Union
import json
import asyncio
from datetime import datetime, timezone
from app.dependencies import verify_token
from app.models import Guest, RestaurantTable
from app.utils.websocket_manager import connection_manager, optimized_guest_broadcast, optimized_table_broadcast
from app.utils.realtime_broadcaster import realtime_broadcaster
import logging

router = APIRouter(tags=["websockets"])
logger = logging.getLogger(__name__)

class RealtimeConnectionManager:
    def __init__(self):
        # Store connections globally (not per restaurant for now - can be enhanced)
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
    
    async def broadcast_to_all(self, message: dict):
        """Broadcast message to ALL connected clients as required by iOS spec"""
        if not self.active_connections:
            return
            
        disconnected = []
        message_json = json.dumps(message)
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.error(f"Failed to send message to connection: {e}")
                # Connection is broken, mark for removal
                disconnected.append(connection)
        
        # Remove broken connections
        for connection in disconnected:
            self.disconnect(connection)
        
        logger.info(f"Broadcasted message to {len(self.active_connections)} connections")

# Global connection manager
realtime_manager = RealtimeConnectionManager()

# ===== REAL-TIME DATA CHANGE BROADCASTING =====
# This is the missing piece that iOS developer requested

async def broadcast_data_change(restaurant_id: str, message: dict):
    """
    🚀 CRITICAL FUNCTION FOR REAL-TIME UPDATES
    
    Broadcasts data changes to all connected WebSocket clients immediately
    when API endpoints modify restaurant data.
    
    This enables Device A → update data → Device B sees change in ~200ms
    
    Args:
        restaurant_id: The restaurant where data changed
        message: The notification message with type, data, timestamp
    """
    try:
        # Add debug logging as requested by iOS developer
        logger.info(f"📡 Broadcasting {message['type']} to restaurant {restaurant_id}")
        logger.info(f"🎯 Message: {json.dumps(message)}")
        
        # 🚨 CRITICAL FIX: Use realtime_broadcaster for restaurant-specific connections
        await realtime_broadcaster.broadcast_data_change(restaurant_id, message)
        
        logger.info(f"✅ Real-time broadcast completed for {message['type']}")
        
    except Exception as e:
        logger.error(f"❌ Failed to broadcast data change: {e}")
        # Don't fail the API call if WebSocket broadcast fails
        pass

# Convenience functions for specific data types (matching iOS requirements)

async def broadcast_guest_data_change(restaurant_id: str, guest: Guest, action: str = "update"):
    """Broadcast guest data changes - PRIORITY #1 per iOS developer"""
    message = {
        "type": "guest_updated" if action == "update" else "guest_created",
        "restaurant_id": restaurant_id,
        "guest_id": str(guest.id),
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "data": {
            "id": str(guest.id),
            "guestName": f"{guest.first_name} {guest.last_name}",
            "firstName": guest.first_name,
            "lastName": guest.last_name,
            "partySize": guest.party_size,
            "status": guest.status,
            "table_id": str(guest.table_id) if guest.table_id else None,
            "email": guest.email,
            "phone": guest.phone
        }
    }
    
    await broadcast_data_change(restaurant_id, message)

async def broadcast_table_data_change(restaurant_id: str, table: RestaurantTable, action: str = "update"):
    """Broadcast table data changes - PRIORITY #3 per iOS developer"""
    message = {
        "type": "table_updated",
        "restaurant_id": restaurant_id,
        "table_id": str(table.id),
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "data": {
            "id": str(table.id),
            "tableNumber": table.table_number,
            "capacity": table.capacity,
            "status": table.status,
            "guest_id": str(table.current_guest_id) if hasattr(table, 'current_guest_id') and table.current_guest_id else None
        }
    }
    
    await broadcast_data_change(restaurant_id, message)

async def broadcast_atomic_transaction_complete(restaurant_id: str, affected_entities: List[str]):
    """Broadcast atomic transaction completion - PRIORITY #4 per iOS developer"""
    message = {
        "type": "atomic_transaction_complete",
        "restaurant_id": restaurant_id,
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "affected_entities": affected_entities
    }
    
    await broadcast_data_change(restaurant_id, message)

def guest_to_ios_format(guest: Guest) -> dict:
    """Convert backend Guest model to iOS GuestEntry format"""
    # Map backend status to iOS status
    status_mapping = {
        "Waitlist": "waiting",
        "waitlist": "waiting", 
        "Arrived": "waiting",
        "Seated": "seated",
        "Finished": "completed",
        "Cancelled": "completed",
        "No Show": "completed"
    }
    
    # Calculate wait time in minutes
    wait_time = 0
    if guest.check_in_time and guest.status in ["Waitlist", "waitlist", "Arrived"]:
        now = datetime.now(timezone.utc)
        if guest.check_in_time.tzinfo is None:
            check_in = guest.check_in_time.replace(tzinfo=timezone.utc)
        else:
            check_in = guest.check_in_time
        wait_time = int((now - check_in).total_seconds() / 60)
    
    return {
        "id": str(guest.id),
        "name": f"{guest.first_name or ''} {guest.last_name or ''}".strip() or "Unknown Guest",
        "partySize": guest.party_size or 1,
        "phoneNumber": guest.phone or "",
        "email": guest.email or "",
        "status": status_mapping.get(guest.status, "waiting"),
        "waitTime": max(0, wait_time),
        "tableId": str(guest.table_id) if guest.table_id else None,
        "notes": guest.notes or "",
        "arrivalTime": guest.check_in_time.isoformat() + 'Z' if guest.check_in_time else None,
        "isWalkIn": guest.reservation_time is None  # Walk-in if no reservation time
    }

def table_to_ios_format(table: RestaurantTable) -> dict:
    """Convert backend RestaurantTable model to iOS RestaurantTable format"""
    # Map backend status to iOS status  
    status_mapping = {
        "available": "available",
        "occupied": "occupied", 
        "reserved": "reserved",
        "cleaning": "needs_cleaning"
    }
    
    return {
        "id": str(table.id),
        "number": int(table.table_number) if table.table_number.isdigit() else 1,
        "capacity": table.capacity or 4,
        "status": status_mapping.get(table.status, "available"),
        "position": {
            "x": float(table.position_x or 0.0),
            "y": float(table.position_y or 0.0)
        },
        "currentGuestId": str(table.current_guest_id) if table.current_guest_id else None
    }

@router.websocket("/realtime")
async def realtime_websocket_endpoint(websocket: WebSocket, restaurant_id: str = Query(...)):
    """
    WebSocket endpoint for real-time updates matching iOS specifications
    URL: ws://your-domain.com/realtime?restaurant_id={restaurant_id}
    """
    try:
        # Use the new realtime broadcaster that supports restaurant-specific connections
        logger.error(f"🔥 [WEBSOCKET] About to connect WebSocket for restaurant: {restaurant_id}")
        await realtime_broadcaster.connect(websocket, restaurant_id)
        logger.error(f"🔥 [WEBSOCKET] WebSocket connected successfully for restaurant: {restaurant_id}")
        logger.error(f"🔥 [WEBSOCKET] Current connections: {realtime_broadcaster.get_connection_stats()}")
        logger.info(f"iOS client connected to realtime WebSocket for restaurant: {restaurant_id}")
        
        # Send initial connection confirmation
        await websocket.send_text(json.dumps({
            "type": "restaurant_connect",
            "restaurant_id": restaurant_id,
            "platform": "iOS",
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        }))
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (ping/heartbeat)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=35.0)
                
                try:
                    message = json.loads(data)
                    message_type = message.get("type", "")
                    
                    # Handle ping from iOS app (required every 30 seconds)
                    if message_type == "ping":
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                        }))
                        logger.debug("Responded to ping with pong")
                    
                except json.JSONDecodeError:
                    logger.warning(f"Received invalid JSON from WebSocket client: {data}")
                    
            except asyncio.TimeoutError:
                # No message received in 35 seconds, send heartbeat
                await websocket.send_text(json.dumps({
                    "type": "heartbeat", 
                    "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                }))
                logger.debug("Sent heartbeat to keep connection alive")
                
    except WebSocketDisconnect:
        realtime_broadcaster.disconnect(websocket, restaurant_id)
        logger.info(f"iOS client disconnected from realtime WebSocket for restaurant: {restaurant_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        realtime_broadcaster.disconnect(websocket, restaurant_id)

@router.websocket("/ws/restaurant/sync")
async def restaurant_sync_websocket_endpoint(websocket: WebSocket, restaurant_id: int = 1):
    """
    Enterprise-grade WebSocket endpoint for real-time restaurant synchronization
    URL: ws://[IP]:8000/ws/restaurant/sync?restaurant_id=1
    
    Implements the exact specification required by iOS developer:
    - Delta update broadcasting
    - Atomic transaction notifications
    - Full sync capability
    - ping/pong heartbeat mechanism
    """
    try:
        await realtime_manager.connect(websocket)
        logger.info(f"iOS client connected to restaurant sync WebSocket for restaurant {restaurant_id}")
        
        # Send initial connection confirmation
        await realtime_manager.send_personal_message(
            json.dumps({
                "type": "connection_established",
                "restaurant_id": restaurant_id,
                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "server_version": "1.0.0"
            }),
            websocket
        )
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (ping/heartbeat)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=35.0)
                
                try:
                    message = json.loads(data)
                    message_type = message.get("type", "")
                    
                    # Handle ping from iOS app (required every 30 seconds)
                    if message_type == "ping":
                        await realtime_manager.send_personal_message(
                            json.dumps({
                                "type": "pong",
                                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                            }),
                            websocket
                        )
                        logger.debug("Responded to ping with pong")
                    
                    # Handle full sync request
                    elif message_type == "request_full_sync":
                        await send_full_sync(websocket, restaurant_id)
                    
                except json.JSONDecodeError:
                    logger.warning(f"Received invalid JSON from WebSocket client: {data}")
                    
            except asyncio.TimeoutError:
                # No message received in 35 seconds, send heartbeat
                await realtime_manager.send_personal_message(
                    json.dumps({
                        "type": "heartbeat", 
                        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                    }),
                    websocket
                )
                logger.debug("Sent heartbeat to keep connection alive")
                
    except WebSocketDisconnect:
        realtime_manager.disconnect(websocket)
        logger.info(f"iOS client disconnected from restaurant sync WebSocket for restaurant {restaurant_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        realtime_manager.disconnect(websocket)

async def send_full_sync(websocket: WebSocket, restaurant_id: int):
    """Send full synchronization data to client"""
    from app.database import get_db
    
    try:
        # Get database session
        db = next(get_db())
        
        # Get all guests for the restaurant
        guests = db.query(Guest).filter(Guest.restaurant_id == restaurant_id).all()
        guest_data = [guest_to_ios_format(guest) for guest in guests]
        
        # Get all tables for the restaurant  
        tables = db.query(RestaurantTable).filter(RestaurantTable.restaurant_id == restaurant_id).all()
        table_data = [table_to_ios_format(table) for table in tables]
        
        # Send full sync message
        full_sync_message = {
            "type": "full_sync",
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "restaurant_id": restaurant_id,
            "data": {
                "guests": guest_data,
                "tables": table_data
            }
        }
        
        await realtime_manager.send_personal_message(
            json.dumps(full_sync_message),
            websocket
        )
        
        logger.info(f"Sent full sync with {len(guest_data)} guests and {len(table_data)} tables")
        
    except Exception as e:
        logger.error(f"Failed to send full sync: {e}")
        # Send error message
        await realtime_manager.send_personal_message(
            json.dumps({
                "type": "error",
                "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                "message": "Failed to retrieve full sync data",
                "error_code": "SYNC_ERROR"
            }),
            websocket
        )

# iOS-compatible broadcast functions matching their exact message format

async def broadcast_guest_created(guest: Guest):
    """Broadcast guest_created event to all connected iOS clients with optimization"""
    try:
        # Use optimized broadcast function
        await optimized_guest_broadcast(guest, "guest_created")
        
        # Legacy iOS-compatible message format for backward compatibility
        message = {
            "type": "guest_created",
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "guest": guest_to_ios_format(guest),
            "table": None,
            "guestId": None
        }
        await realtime_manager.broadcast_to_all(message)
        logger.info(f"Broadcasted guest_created for guest {guest.id}")
    except Exception as e:
        logger.error(f"Error broadcasting guest_created: {e}")

async def broadcast_guest_updated(guest: Guest):
    """Broadcast guest_updated event to all connected iOS clients with optimization"""
    try:
        # Use optimized broadcast function
        await optimized_guest_broadcast(guest, "guest_updated")
        
        # Legacy iOS-compatible message format for backward compatibility
        message = {
            "type": "guest_updated", 
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "guest": guest_to_ios_format(guest),
            "table": None,
            "guestId": None
        }
        await realtime_manager.broadcast_to_all(message)
        logger.info(f"Broadcasted guest_updated for guest {guest.id}")
    except Exception as e:
        logger.error(f"Error broadcasting guest_updated: {e}")

async def broadcast_guest_deleted(guest_id: str):
    """Broadcast guest_deleted event to all connected iOS clients"""
    message = {
        "type": "guest_deleted",
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "guest": None,
        "table": None,
        "guestId": guest_id
    }
    await realtime_manager.broadcast_to_all(message)
    logger.info(f"Broadcasted guest_deleted for guest {guest_id}")

async def broadcast_table_updated(table: RestaurantTable, action: str = "updated"):
    """Broadcast table_updated event to all connected iOS clients - FIXED FOR iOS REQUIREMENTS"""
    try:
        # iOS-compatible message format (EXACT MATCH)
        message = {
            "type": "table_updated",
            "restaurant_id": str(table.restaurant_id),
            "table_id": str(table.id),
            "action": action,  # "assigned", "cleared", "updated", etc.
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "data": {
                "id": str(table.id),
                "tableNumber": table.table_number,
                "capacity": table.capacity,
                "status": table.status,
                "position": {
                    "x": float(table.position_x or 0.0),
                    "y": float(table.position_y or 0.0)
                },
                "currentGuestId": str(table.current_guest_id) if table.current_guest_id else None,
                "section": table.section
            }
        }
        
        # Add debug logging as requested by iOS team
        logger.info(f"📡 Broadcasting table_updated to all clients for restaurant {table.restaurant_id}")
        logger.info(f"🎯 Table {table.id} action: {action}, status: {table.status}")
        logger.info(f"📄 Message: {json.dumps(message)}")
        
        await realtime_manager.broadcast_to_all(message)
        logger.info(f"✅ Successfully broadcasted table_updated for table {table.id}")
        
    except Exception as e:
        logger.error(f"❌ Error broadcasting table_updated: {e}")
        import traceback
        traceback.print_exc()

async def broadcast_delta_update(changes: List[dict], restaurant_id: int = 1):
    """
    Broadcast delta update with multiple changes as required by iOS specification
    
    Args:
        changes: List of change objects with structure:
            {
                "entity_type": "guest" | "table",
                "entity_id": "string",
                "action": "create" | "update" | "delete",
                "data": {object} | None
            }
        restaurant_id: ID of the restaurant for filtering connections
    """
    message = {
        "type": "delta_update",
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "restaurant_id": str(restaurant_id),
        "changes": changes
    }
    
    # 🚨 CRITICAL FIX: Use realtime_broadcaster instead of realtime_manager
    await realtime_broadcaster.broadcast_data_change(str(restaurant_id), message)
    logger.info(f"Broadcasted delta_update with {len(changes)} changes for restaurant {restaurant_id}")

async def broadcast_atomic_transaction_complete(transaction_id: str, changes: List[dict], restaurant_id: int = 1):
    """
    Broadcast atomic transaction completion as required by enterprise specification
    
    Args:
        transaction_id: Unique identifier for the atomic transaction
        changes: List of all changes made in the transaction
        restaurant_id: ID of the restaurant
    """
    message = {
        "type": "atomic_transaction_complete",
        "transaction_id": transaction_id,
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "restaurant_id": str(restaurant_id),
        "changes": changes
    }
    
    # 🚨 CRITICAL FIX: Use realtime_broadcaster instead of realtime_manager
    await realtime_broadcaster.broadcast_data_change(str(restaurant_id), message)
    logger.info(f"Broadcasted atomic_transaction_complete for transaction {transaction_id} with {len(changes)} changes")

# Export the broadcast functions for use in other modules
__all__ = [
    "router",
    "broadcast_guest_created",
    "broadcast_guest_updated", 
    "broadcast_guest_deleted",
    "broadcast_table_updated",
    "broadcast_delta_update",
    "broadcast_atomic_transaction_complete"
]
