from typing import Dict, List
import json
import logging
from datetime import datetime
from fastapi import WebSocket
import asyncio
import os

logger = logging.getLogger(__name__)

class RealtimeDataBroadcaster:
    """Real-time data change broadcaster for WebSocket notifications"""
    
    def __init__(self):
        # Store connections by restaurant_id: {restaurant_id: [websocket_connections]}
        self.connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, restaurant_id: str):
        """Add a WebSocket connection for a restaurant"""
        await websocket.accept()
        
        # Add critical debug info for multi-worker debugging
        import os
        worker_id = os.getpid()
        logger.error(f"🔄 [WORKER-{worker_id}] WebSocket connecting for restaurant {restaurant_id}")
        
        if restaurant_id not in self.connections:
            self.connections[restaurant_id] = []
        
        self.connections[restaurant_id].append(websocket)
        logger.error(f"� [WORKER-{worker_id}] ✅ WebSocket connected for restaurant {restaurant_id}. Total connections: {len(self.connections[restaurant_id])}")
        logger.error(f"🔄 [WORKER-{worker_id}] All connections: {dict(self.connections)}")
    
    def disconnect(self, websocket: WebSocket, restaurant_id: str):
        """Remove a WebSocket connection"""
        if restaurant_id in self.connections and websocket in self.connections[restaurant_id]:
            self.connections[restaurant_id].remove(websocket)
            logger.info(f"📡 WebSocket disconnected from restaurant {restaurant_id}. Remaining: {len(self.connections[restaurant_id])}")
            
            # Clean up empty restaurant connections
            if not self.connections[restaurant_id]:
                del self.connections[restaurant_id]
    
    async def broadcast_data_change(self, restaurant_id: str, message: dict):
        """
        Broadcast data change to all connected clients for a restaurant
        Matches the exact format specified in BACKEND_REALTIME_REQUIREMENTS.md
        """
        # Add critical debug info for multi-worker debugging
        import os
        worker_id = os.getpid()
        logger.error(f"🔄 [WORKER-{worker_id}] Broadcasting {message.get('type')} to restaurant {restaurant_id}")
        logger.error(f"🔄 [WORKER-{worker_id}] Current connections: {dict(self.connections)}")
        
        if restaurant_id not in self.connections:
            logger.error(f"� [WORKER-{worker_id}] ❌ No WebSocket connections for restaurant {restaurant_id}")
            logger.error(f"🔄 [WORKER-{worker_id}] Available restaurants: {list(self.connections.keys())}")
            return
        
        # Convert to JSON string
        json_message = json.dumps(message)
        
        # Send to all connected clients for this restaurant
        disconnected = []
        successful_broadcasts = 0
        
        for websocket in self.connections[restaurant_id].copy():  # Copy to avoid modification during iteration
            try:
                await websocket.send_text(json_message)
                successful_broadcasts += 1
                logger.debug(f"📡 Broadcast sent to client: {message['type']}")
            except Exception as e:
                logger.warning(f"❌ Failed to send to client: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws, restaurant_id)
        
        logger.info(f"📡 Broadcasting {message['type']} to {successful_broadcasts} clients for restaurant {restaurant_id}")
        logger.debug(f"�� Message: {json_message}")
    
    async def broadcast_guest_created(self, restaurant_id: str, guest_id: str, guest_data: dict):
        """
        Broadcast new guest creation with complete data format matching iOS requirements
        
        Args:
            restaurant_id: ID of the restaurant
            guest_id: ID of the newly created guest
            guest_data: Dictionary with complete guest data
        """
        message = {
            "type": "guest_created",
            "restaurant_id": restaurant_id,
            "guest_id": guest_id,
            "action": "created",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "id": guest_id,
                "guestName": guest_data.get('guestName', guest_data.get('name', 'Unknown Guest')),
                "firstName": guest_data.get('firstName', ''),
                "lastName": guest_data.get('lastName', ''),
                "partySize": guest_data.get('partySize', guest_data.get('party_size', 1)),
                "status": guest_data.get('status', 'waiting'),
                "tableId": guest_data.get('tableId', guest_data.get('table_id')),
                "email": guest_data.get('email', ''),
                "phone": guest_data.get('phone', ''),
                "notes": guest_data.get('notes', '')
            }
        }
        
        # Add debug logging to track what we're sending
        logger.info(f"📡 Broadcasting guest_created to all clients for restaurant {restaurant_id}")
        logger.info(f"🎯 New guest {guest_id} created with status: {guest_data.get('status')}")
        logger.debug(f"📄 Message: {message}")
        
        await self.broadcast_data_change(restaurant_id, message)
        
        logger.info(f"✅ Successfully broadcasted guest_created for guest {guest_id}")
    
    async def broadcast_guest_updated(self, restaurant_id: str, guest_id: str, action: str, guest_data: dict):
        """
        Broadcast guest status update with complete data format matching iOS requirements
        
        Args:
            restaurant_id: ID of the restaurant
            guest_id: ID of the guest being updated
            action: Type of action (status_changed, table_assigned, table_cleared, info_updated)
            guest_data: Dictionary with guest data including status, table_id, name, etc.
        """
        message = {
            "type": "guest_updated",
            "restaurant_id": restaurant_id,
            "guest_id": guest_id,
            "action": action,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "id": guest_id,
                "guestName": guest_data.get('guestName', guest_data.get('name', 'Unknown Guest')),
                "firstName": guest_data.get('firstName', ''),
                "lastName": guest_data.get('lastName', ''),
                "partySize": guest_data.get('partySize', guest_data.get('party_size', 1)),
                "status": guest_data.get('status'),
                "tableId": guest_data.get('tableId', guest_data.get('table_id')),
                "email": guest_data.get('email', ''),
                "phone": guest_data.get('phone', ''),
                "notes": guest_data.get('notes', '')
            }
        }
        
        # Add debug logging to track what we're sending
        logger.info(f"📡 Broadcasting guest_updated to all clients for restaurant {restaurant_id}")
        logger.info(f"🎯 Guest {guest_id} action: {action}, status: {guest_data.get('status')}")
        logger.debug(f"📄 Message: {message}")
        
        await self.broadcast_data_change(restaurant_id, message)
        
        logger.info(f"✅ Successfully broadcasted guest_updated for guest {guest_id}")
    
    async def broadcast_guest_deleted(self, restaurant_id: str, guest_id: str):
        """Broadcast guest deletion"""
        message = {
            "type": "guest_deleted",
            "restaurant_id": restaurant_id,
            "guest_id": guest_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "id": guest_id
            }
        }
        await self.broadcast_data_change(restaurant_id, message)
    
    async def broadcast_table_updated(self, restaurant_id: str, table_id: str, action: str, table_data: dict):
        """
        Broadcast table status update with complete data format matching iOS requirements
        
        Args:
            restaurant_id: ID of the restaurant
            table_id: ID of the table being updated
            action: Type of action (status_changed, guest_assigned, guest_cleared, updated)
            table_data: Dictionary with complete table data
        """
        message = {
            "type": "table_updated",
            "restaurant_id": restaurant_id,
            "table_id": table_id,
            "action": action,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "id": table_id,
                "tableNumber": table_data.get('table_number', table_data.get('tableNumber', 'Unknown')),
                "capacity": table_data.get('capacity', 4),
                "status": table_data.get('status', 'available'),
                "position": {
                    "x": float(table_data.get('x', table_data.get('position_x', 0.0))),
                    "y": float(table_data.get('y', table_data.get('position_y', 0.0)))
                },
                "shape": table_data.get('shape', 'rectangle'),
                "section": table_data.get('section', ''),
                "currentGuestId": table_data.get('current_guest_id', table_data.get('guest_id')),
                "updatedAt": datetime.utcnow().isoformat() + "Z"
            }
        }
        
        # Add debug logging to track what we're sending
        logger.info(f"📡 Broadcasting table_updated to all clients for restaurant {restaurant_id}")
        logger.info(f"🎯 Table {table_id} action: {action}, status: {table_data.get('status')}")
        logger.debug(f"📄 Message: {message}")
        
        await self.broadcast_data_change(restaurant_id, message)
        
        logger.info(f"✅ Successfully broadcasted table_updated for table {table_id}")
    
    async def broadcast_atomic_transaction_complete(self, restaurant_id: str, affected_entities: List[str]):
        """Broadcast atomic transaction completion"""
        message = {
            "type": "atomic_transaction_complete",
            "restaurant_id": restaurant_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "affected_entities": affected_entities
        }
        
        logger.info(f"📡 Broadcasting atomic_transaction_complete to all clients for restaurant {restaurant_id}")
        logger.info(f"🎯 Affected entities: {affected_entities}")
        logger.debug(f"📄 Message: {message}")
        
        await self.broadcast_data_change(restaurant_id, message)
        
        logger.info(f"✅ Successfully broadcasted atomic_transaction_complete")
    
    async def broadcast_to_all_workers(self, restaurant_id: str, message: dict):
        """
        Compatibility method for batch.py - just calls the regular broadcast_data_change.
        In the future, this will be replaced with Redis pub/sub for true cross-worker broadcasting.
        """
        logger.warning(f"🔄 [COMPATIBILITY] broadcast_to_all_workers called - using regular broadcast for now")
        await self.broadcast_data_change(restaurant_id, message)
    
    def get_connection_stats(self):
        """Get statistics about current WebSocket connections"""
        total_connections = sum(len(connections) for connections in self.connections.values())
        return {
            "total_restaurants": len(self.connections),
            "total_connections": total_connections,
            "restaurant_breakdown": {
                restaurant_id: len(connections)
                for restaurant_id, connections in self.connections.items()
            }
        }

# Global broadcaster instance
realtime_broadcaster = RealtimeDataBroadcaster()
