"""
Redis-based real-time broadcaster for cross-worker WebSocket communication.

This module handles broadcasting WebSocket messages across multiple Gunicorn workers
using Redis pub/sub channels. Each worker subscribes to restaurant-specific channels
and broadcasts messages to all workers handling that restaurant.
"""
import asyncio
import json
import logging
import os
from typing import Dict, List, Optional
from fastapi import WebSocket
import redis.asyncio as redis
from datetime import datetime

logger = logging.getLogger(__name__)

class RedisRealtimeBroadcaster:
    """Redis-based real-time data broadcaster for multi-worker WebSocket support"""
    
    def __init__(self):
        # Store local connections by restaurant_id: {restaurant_id: [websocket_connections]}
        self.local_connections: Dict[str, List[WebSocket]] = {}
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.worker_id = os.getpid()
        self.subscription_tasks: Dict[str, asyncio.Task] = {}
        
    async def initialize_redis(self):
        """Initialize Redis connection for pub/sub messaging"""
        try:
            # Try to connect to Redis (Railway provides REDIS_URL)
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            
            # Test connection
            await self.redis_client.ping()
            
            # Create pubsub client
            self.pubsub = self.redis_client.pubsub()
            
            logger.info(f"🔴 [WORKER-{self.worker_id}] Redis initialized successfully")
            return True
            
        except Exception as e:
            logger.warning(f"🔴 [WORKER-{self.worker_id}] Redis connection failed: {e}")
            logger.warning(f"🔴 [WORKER-{self.worker_id}] Falling back to single-worker mode")
            self.redis_client = None
            self.pubsub = None
            return False
    
    async def subscribe_to_restaurant(self, restaurant_id: str):
        """Subscribe to Redis channel for a specific restaurant"""
        if not self.pubsub:
            return
            
        channel_name = f"restaurant:{restaurant_id}:updates"
        
        try:
            await self.pubsub.subscribe(channel_name)
            logger.info(f"🔴 [WORKER-{self.worker_id}] Subscribed to {channel_name}")
            
            # Start listening task for this restaurant if not already started
            if restaurant_id not in self.subscription_tasks:
                task = asyncio.create_task(self._listen_to_channel(restaurant_id, channel_name))
                self.subscription_tasks[restaurant_id] = task
                
        except Exception as e:
            logger.error(f"🔴 [WORKER-{self.worker_id}] Failed to subscribe to {channel_name}: {e}")
    
    async def unsubscribe_from_restaurant(self, restaurant_id: str):
        """Unsubscribe from Redis channel when no local connections remain"""
        if not self.pubsub:
            return
            
        channel_name = f"restaurant:{restaurant_id}:updates"
        
        try:
            await self.pubsub.unsubscribe(channel_name)
            logger.info(f"🔴 [WORKER-{self.worker_id}] Unsubscribed from {channel_name}")
            
            # Cancel listening task
            if restaurant_id in self.subscription_tasks:
                self.subscription_tasks[restaurant_id].cancel()
                del self.subscription_tasks[restaurant_id]
                
        except Exception as e:
            logger.error(f"🔴 [WORKER-{self.worker_id}] Failed to unsubscribe from {channel_name}: {e}")
    
    async def _listen_to_channel(self, restaurant_id: str, channel_name: str):
        """Listen to Redis channel and broadcast to local WebSocket connections"""
        try:
            while True:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    try:
                        # Parse the message data
                        message_data = json.loads(message['data'])
                        
                        # Only process if this worker has local connections for this restaurant
                        if restaurant_id in self.local_connections and self.local_connections[restaurant_id]:
                            logger.debug(f"🔴 [WORKER-{self.worker_id}] Received Redis message for {restaurant_id}")
                            await self._broadcast_to_local_connections(restaurant_id, message_data)
                            
                    except Exception as e:
                        logger.error(f"🔴 [WORKER-{self.worker_id}] Error processing Redis message: {e}")
                        
                await asyncio.sleep(0.01)  # Small delay to prevent busy waiting
                
        except asyncio.CancelledError:
            logger.info(f"🔴 [WORKER-{self.worker_id}] Stopped listening to {channel_name}")
        except Exception as e:
            logger.error(f"🔴 [WORKER-{self.worker_id}] Error in Redis listener for {channel_name}: {e}")
    
    async def _broadcast_to_local_connections(self, restaurant_id: str, message: dict):
        """Broadcast message to local WebSocket connections only"""
        if restaurant_id not in self.local_connections:
            return
            
        # Convert to JSON string
        json_message = json.dumps(message)
        
        # Send to all local connected clients for this restaurant
        disconnected = []
        successful_broadcasts = 0
        
        for websocket in self.local_connections[restaurant_id].copy():
            try:
                await websocket.send_text(json_message)
                successful_broadcasts += 1
                logger.debug(f"📡 [WORKER-{self.worker_id}] Broadcast sent to local client: {message['type']}")
            except Exception as e:
                logger.warning(f"❌ [WORKER-{self.worker_id}] Failed to send to local client: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for ws in disconnected:
            self.disconnect(ws, restaurant_id)
        
        if successful_broadcasts > 0:
            logger.info(f"📡 [WORKER-{self.worker_id}] Broadcasted {message['type']} to {successful_broadcasts} local clients for restaurant {restaurant_id}")
    
    async def connect(self, websocket: WebSocket, restaurant_id: str):
        """Add a WebSocket connection for a restaurant"""
        await websocket.accept()
        
        logger.error(f"🔄 [WORKER-{self.worker_id}] WebSocket connecting for restaurant {restaurant_id}")
        
        # Add to local connections
        if restaurant_id not in self.local_connections:
            self.local_connections[restaurant_id] = []
            # Subscribe to Redis channel for this restaurant
            await self.subscribe_to_restaurant(restaurant_id)
        
        self.local_connections[restaurant_id].append(websocket)
        logger.error(f"✅ [WORKER-{self.worker_id}] WebSocket connected for restaurant {restaurant_id}. Local connections: {len(self.local_connections[restaurant_id])}")
    
    def disconnect(self, websocket: WebSocket, restaurant_id: str):
        """Remove a WebSocket connection"""
        if restaurant_id in self.local_connections and websocket in self.local_connections[restaurant_id]:
            self.local_connections[restaurant_id].remove(websocket)
            logger.info(f"📡 [WORKER-{self.worker_id}] WebSocket disconnected from restaurant {restaurant_id}. Remaining: {len(self.local_connections[restaurant_id])}")
            
            # Clean up empty restaurant connections and unsubscribe from Redis
            if not self.local_connections[restaurant_id]:
                del self.local_connections[restaurant_id]
                # Unsubscribe from Redis channel
                asyncio.create_task(self.unsubscribe_from_restaurant(restaurant_id))
    
    async def publish_to_redis(self, restaurant_id: str, message: dict):
        """Publish message to Redis channel for cross-worker broadcasting"""
        if not self.redis_client:
            # Redis not available, only broadcast locally
            await self._broadcast_to_local_connections(restaurant_id, message)
            return
            
        channel_name = f"restaurant:{restaurant_id}:updates"
        
        try:
            # Publish to Redis channel - this will reach ALL workers
            await self.redis_client.publish(channel_name, json.dumps(message))
            logger.debug(f"🔴 [WORKER-{self.worker_id}] Published to Redis channel {channel_name}")
            
        except Exception as e:
            logger.error(f"🔴 [WORKER-{self.worker_id}] Failed to publish to Redis: {e}")
            # Fallback to local broadcast only
            await self._broadcast_to_local_connections(restaurant_id, message)
    
    async def broadcast_data_change(self, restaurant_id: str, message: dict):
        """
        Main broadcast method - publishes to Redis for cross-worker communication
        """
        # Add worker info to debug multi-worker issues
        worker_id = os.getpid()
        logger.error(f"🔄 [WORKER-{worker_id}] Broadcasting {message.get('type')} to restaurant {restaurant_id}")
        logger.error(f"🔄 [WORKER-{worker_id}] Local connections: {dict(self.local_connections)}")
        
        # Publish to Redis (which will broadcast to all workers including this one)
        await self.publish_to_redis(restaurant_id, message)
        
        logger.info(f"📡 [WORKER-{worker_id}] Published {message['type']} to Redis for restaurant {restaurant_id}")
    
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
        logger.info(f"📡 [REDIS-{self.worker_id}] Broadcasting guest_created to all workers for restaurant {restaurant_id}")
        logger.info(f"🎯 [REDIS-{self.worker_id}] New guest {guest_id} created with status: {guest_data.get('status')}")
        logger.debug(f"📄 [REDIS-{self.worker_id}] Message: {message}")
        
        await self.broadcast_data_change(restaurant_id, message)
        
        logger.info(f"✅ [REDIS-{self.worker_id}] Successfully broadcasted guest_created for guest {guest_id}")
    
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
        logger.info(f"📡 [REDIS-{self.worker_id}] Broadcasting guest_updated to all workers for restaurant {restaurant_id}")
        logger.info(f"🎯 [REDIS-{self.worker_id}] Guest {guest_id} action: {action}, status: {guest_data.get('status')}")
        logger.debug(f"📄 [REDIS-{self.worker_id}] Message: {message}")
        
        await self.broadcast_data_change(restaurant_id, message)
        
        logger.info(f"✅ [REDIS-{self.worker_id}] Successfully broadcasted guest_updated for guest {guest_id}")
    
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
        logger.info(f"📡 [REDIS-{self.worker_id}] Broadcasting table_updated to all workers for restaurant {restaurant_id}")
        logger.info(f"🎯 [REDIS-{self.worker_id}] Table {table_id} action: {action}, status: {table_data.get('status')}")
        logger.debug(f"📄 [REDIS-{self.worker_id}] Message: {message}")
        
        await self.broadcast_data_change(restaurant_id, message)
        
        logger.info(f"✅ [REDIS-{self.worker_id}] Successfully broadcasted table_updated for table {table_id}")
    
    async def broadcast_atomic_transaction_complete(self, restaurant_id: str, affected_entities: List[str]):
        """Broadcast atomic transaction completion"""
        message = {
            "type": "atomic_transaction_complete",
            "restaurant_id": restaurant_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "affected_entities": affected_entities
        }
        
        logger.info(f"📡 [REDIS-{self.worker_id}] Broadcasting atomic_transaction_complete to all workers for restaurant {restaurant_id}")
        logger.info(f"🎯 [REDIS-{self.worker_id}] Affected entities: {affected_entities}")
        logger.debug(f"📄 [REDIS-{self.worker_id}] Message: {message}")
        
        await self.broadcast_data_change(restaurant_id, message)
        
        logger.info(f"✅ [REDIS-{self.worker_id}] Successfully broadcasted atomic_transaction_complete")

    async def broadcast_to_all_workers(self, restaurant_id: str, message: dict):
        """
        Broadcast message to ALL workers using Redis pub/sub.
        This is the main method for cross-worker communication.
        """
        logger.info(f"🔴 [REDIS-{self.worker_id}] Broadcasting to all workers for restaurant {restaurant_id}")
        await self.broadcast_data_change(restaurant_id, message)

    # Add the connections property for compatibility with existing code
    @property
    def connections(self):
        """Compatibility property - returns local connections"""
        return self.local_connections


# Create a global instance for the application to use
redis_broadcaster = RedisRealtimeBroadcaster()

# Export for easy importing
__all__ = ['RedisRealtimeBroadcaster', 'redis_broadcaster']
