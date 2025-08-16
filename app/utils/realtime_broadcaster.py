from typing import Dict, List
import json
import logging
from datetime import datetime
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class RealtimeDataBroadcaster:
    """Real-time data change broadcaster for WebSocket notifications"""
    
    def __init__(self):
        # Store connections by restaurant_id: {restaurant_id: [websocket_connections]}
        self.connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, restaurant_id: str):
        """Add a WebSocket connection for a restaurant"""
        await websocket.accept()
        
        if restaurant_id not in self.connections:
            self.connections[restaurant_id] = []
        
        self.connections[restaurant_id].append(websocket)
        logger.info(f"📡 WebSocket connected for restaurant {restaurant_id}. Total connections: {len(self.connections[restaurant_id])}")
    
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
        if restaurant_id not in self.connections:
            logger.debug(f"📡 No WebSocket connections for restaurant {restaurant_id}")
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
        logger.debug(f"🎯 Message: {json_message}")
    
    async def broadcast_guest_created(self, restaurant_id: str, guest_id: str, guest_data: dict):
        """Broadcast new guest creation"""
        message = {
            "type": "guest_created",
            "restaurant_id": restaurant_id,
            "guest_id": guest_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "id": guest_id,
                "guestName": f"{guest_data.get('first_name', '')} {guest_data.get('last_name', '')}".strip(),
                "partySize": guest_data.get('party_size', 0),
                "status": guest_data.get('status', 'waiting')
            }
        }
        await self.broadcast_data_change(restaurant_id, message)
    
    async def broadcast_guest_updated(self, restaurant_id: str, guest_id: str, action: str, guest_data: dict):
        """Broadcast guest status update"""
        message = {
            "type": "guest_updated",
            "restaurant_id": restaurant_id,
            "guest_id": guest_id,
            "action": action,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "id": guest_id,
                "status": guest_data.get('status'),
                "table_id": guest_data.get('table_id')
            }
        }
        await self.broadcast_data_change(restaurant_id, message)
    
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
    
    async def broadcast_table_updated(self, restaurant_id: str, table_id: str, table_data: dict):
        """Broadcast table status update"""
        message = {
            "type": "table_updated",
            "restaurant_id": restaurant_id,
            "table_id": table_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "data": {
                "id": table_id,
                "status": table_data.get('status'),
                "guest_id": table_data.get('guest_id')
            }
        }
        await self.broadcast_data_change(restaurant_id, message)
    
    async def broadcast_atomic_transaction_complete(self, restaurant_id: str, affected_entities: List[str]):
        """Broadcast atomic transaction completion"""
        message = {
            "type": "atomic_transaction_complete",
            "restaurant_id": restaurant_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "affected_entities": affected_entities
        }
        await self.broadcast_data_change(restaurant_id, message)
    
    def get_connection_stats(self) -> Dict:
        """Get connection statistics for monitoring"""
        return {
            "total_restaurants": len(self.connections),
            "total_connections": sum(len(connections) for connections in self.connections.values()),
            "restaurant_breakdown": {
                restaurant_id: len(connections) 
                for restaurant_id, connections in self.connections.items()
            }
        }

# Global broadcaster instance
realtime_broadcaster = RealtimeDataBroadcaster()
