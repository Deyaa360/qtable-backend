from functools import wraps
from typing import Dict, List, Optional
import logging
from sqlalchemy.orm import Session
from ..models import Guest, RestaurantTable, Reservation
from ..utils.cache import cache, invalidate_cache_pattern

logger = logging.getLogger(__name__)

class WebSocketConnectionManager:
    """Enhanced WebSocket connection manager with restaurant-based broadcasting"""
    
    def __init__(self):
        # Restaurant-specific connections
        self.restaurant_connections: Dict[str, List] = {}
        # Global connections (for admin dashboards)
        self.global_connections: List = []
        
    async def connect(self, websocket, restaurant_id: Optional[str] = None):
        """Connect a WebSocket client"""
        await websocket.accept()
        
        if restaurant_id:
            if restaurant_id not in self.restaurant_connections:
                self.restaurant_connections[restaurant_id] = []
            self.restaurant_connections[restaurant_id].append(websocket)
            logger.info(f"WebSocket connected for restaurant {restaurant_id}. Total connections: {len(self.restaurant_connections[restaurant_id])}")
        else:
            self.global_connections.append(websocket)
            logger.info(f"Global WebSocket connected. Total global connections: {len(self.global_connections)}")
    
    def disconnect(self, websocket, restaurant_id: Optional[str] = None):
        """Disconnect a WebSocket client"""
        try:
            if restaurant_id and restaurant_id in self.restaurant_connections:
                if websocket in self.restaurant_connections[restaurant_id]:
                    self.restaurant_connections[restaurant_id].remove(websocket)
                    logger.info(f"WebSocket disconnected from restaurant {restaurant_id}. Remaining: {len(self.restaurant_connections[restaurant_id])}")
                    
                    # Clean up empty restaurant connections
                    if not self.restaurant_connections[restaurant_id]:
                        del self.restaurant_connections[restaurant_id]
            else:
                if websocket in self.global_connections:
                    self.global_connections.remove(websocket)
                    logger.info(f"Global WebSocket disconnected. Remaining: {len(self.global_connections)}")
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {e}")
    
    async def send_to_restaurant(self, message: dict, restaurant_id: str):
        """Send message to all clients connected to a specific restaurant"""
        if restaurant_id not in self.restaurant_connections:
            logger.debug(f"No WebSocket connections for restaurant {restaurant_id}")
            return
        
        disconnected = []
        connections = self.restaurant_connections[restaurant_id].copy()  # Avoid modification during iteration
        
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to WebSocket connection: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected WebSockets
        for connection in disconnected:
            self.disconnect(connection, restaurant_id)
    
    async def send_to_all(self, message: dict):
        """Send message to all connected clients (all restaurants + global)"""
        # Send to all restaurant connections
        for restaurant_id in list(self.restaurant_connections.keys()):
            await self.send_to_restaurant(message, restaurant_id)
        
        # Send to global connections
        disconnected = []
        for connection in self.global_connections.copy():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send message to global WebSocket connection: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected global WebSockets
        for connection in disconnected:
            self.disconnect(connection)
    
    def get_connection_stats(self) -> Dict:
        """Get connection statistics"""
        restaurant_stats = {
            restaurant_id: len(connections) 
            for restaurant_id, connections in self.restaurant_connections.items()
        }
        
        return {
            'total_restaurants': len(self.restaurant_connections),
            'total_restaurant_connections': sum(len(connections) for connections in self.restaurant_connections.values()),
            'global_connections': len(self.global_connections),
            'restaurant_breakdown': restaurant_stats
        }

# Global connection manager instance
connection_manager = WebSocketConnectionManager()

def broadcast_optimization(func):
    """Decorator to add performance optimizations to broadcast functions"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            # Add small delay to batch rapid updates
            import asyncio
            await asyncio.sleep(0.001)  # 1ms delay to batch updates
            
            result = await func(*args, **kwargs)
            
            # Log broadcast performance
            stats = connection_manager.get_connection_stats()
            if stats['total_restaurant_connections'] > 0:
                logger.debug(f"Broadcast completed - {func.__name__}: {stats}")
            
            return result
        except Exception as e:
            logger.error(f"Broadcast optimization error in {func.__name__}: {e}")
            raise
    
    return wrapper

@broadcast_optimization
async def optimized_guest_broadcast(guest: Guest, event_type: str):
    """Optimized guest broadcasting with caching"""
    try:
        # Get restaurant ID from guest
        restaurant_id = guest.restaurant_id
        if not restaurant_id:
            logger.warning(f"Guest {guest.id} has no restaurant_id, broadcasting to all")
            restaurant_id = "global"
        
        # Create optimized message
        message = {
            "type": event_type,
            "data": {
                "id": str(guest.id),
                "firstName": guest.first_name,
                "lastName": guest.last_name,
                "partySize": guest.party_size,
                "status": guest.status,
                "tableId": str(guest.table_id) if guest.table_id else None,
                "updatedAt": guest.updated_at.isoformat() if guest.updated_at else None
            },
            "restaurantId": restaurant_id,
            "timestamp": str(guest.updated_at or guest.created_at)
        }
        
        # Broadcast to restaurant-specific connections
        await connection_manager.send_to_restaurant(message, restaurant_id)
        
        # Invalidate related cache
        invalidate_cache_pattern(f"dashboard:{restaurant_id}")
        
    except Exception as e:
        logger.error(f"Error in optimized guest broadcast: {e}")

@broadcast_optimization 
async def optimized_table_broadcast(table: RestaurantTable, event_type: str):
    """Optimized table broadcasting with caching"""
    try:
        restaurant_id = table.restaurant_id
        
        # Create optimized message
        message = {
            "type": event_type,
            "data": {
                "id": str(table.id),
                "tableNumber": table.table_number,
                "capacity": table.capacity,
                "status": table.status,
                "updatedAt": table.updated_at.isoformat() if table.updated_at else None
            },
            "restaurantId": restaurant_id,
            "timestamp": str(table.updated_at or table.created_at)
        }
        
        # Broadcast to restaurant-specific connections
        await connection_manager.send_to_restaurant(message, restaurant_id)
        
        # Invalidate related cache
        invalidate_cache_pattern(f"dashboard:{restaurant_id}")
        
    except Exception as e:
        logger.error(f"Error in optimized table broadcast: {e}")

# Performance monitoring
async def cleanup_connections():
    """Periodic cleanup of stale connections"""
    stats = connection_manager.get_connection_stats()
    logger.info(f"WebSocket connection stats: {stats}")
    
    # Add logic to ping connections and remove stale ones
    # This would be called periodically by a background task
