from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from typing import Dict, List
import json
import asyncio
from datetime import datetime
from app.dependencies import verify_token
from app.schemas import WebSocketMessage

router = APIRouter(tags=["websockets"])

class ConnectionManager:
    def __init__(self):
        # Store connections by restaurant_id
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, restaurant_id: str):
        await websocket.accept()
        if restaurant_id not in self.active_connections:
            self.active_connections[restaurant_id] = []
        self.active_connections[restaurant_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, restaurant_id: str):
        if restaurant_id in self.active_connections:
            if websocket in self.active_connections[restaurant_id]:
                self.active_connections[restaurant_id].remove(websocket)
            if not self.active_connections[restaurant_id]:
                del self.active_connections[restaurant_id]
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    async def broadcast_to_restaurant(self, message: dict, restaurant_id: str):
        """Broadcast message to all connections for a restaurant"""
        if restaurant_id in self.active_connections:
            disconnected = []
            
            for connection in self.active_connections[restaurant_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    # Connection is broken, mark for removal
                    disconnected.append(connection)
            
            # Remove broken connections
            for connection in disconnected:
                self.disconnect(connection, restaurant_id)

# Global connection manager
manager = ConnectionManager()

@router.websocket("/restaurants/{restaurant_id}/live")
async def websocket_endpoint(websocket: WebSocket, restaurant_id: str):
    """WebSocket endpoint for real-time updates"""
    
    # Note: In production, you'd want to authenticate the WebSocket connection
    # For now, we'll accept all connections but in reality you'd verify the JWT token
    
    try:
        await manager.connect(websocket, restaurant_id)
        
        # Send initial connection confirmation
        await manager.send_personal_message(
            json.dumps({
                "type": "connection_established",
                "message": "Connected to real-time updates",
                "restaurant_id": restaurant_id,
                "timestamp": datetime.utcnow().isoformat()
            }),
            websocket
        )
        
        # Keep connection alive and handle incoming messages
        while True:
            # Wait for messages from client (heartbeat, etc.)
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Handle client messages if needed (e.g., heartbeat)
                message = json.loads(data)
                if message.get("type") == "ping":
                    await manager.send_personal_message(
                        json.dumps({"type": "pong", "timestamp": datetime.utcnow().isoformat()}),
                        websocket
                    )
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                await manager.send_personal_message(
                    json.dumps({"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()}),
                    websocket
                )
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, restaurant_id)

async def broadcast_table_update(restaurant_id: str, table_data: dict):
    """Broadcast table update to all connected clients for a restaurant"""
    message = {
        "type": "table_update",
        "data": table_data,
        "timestamp": datetime.utcnow().isoformat(),
        "restaurant_id": restaurant_id
    }
    await manager.broadcast_to_restaurant(message, restaurant_id)

async def broadcast_reservation_update(restaurant_id: str, reservation_data: dict):
    """Broadcast reservation update to all connected clients for a restaurant"""
    message = {
        "type": "reservation_update",
        "data": reservation_data,
        "timestamp": datetime.utcnow().isoformat(),
        "restaurant_id": restaurant_id
    }
    await manager.broadcast_to_restaurant(message, restaurant_id)

async def broadcast_floor_plan_update(restaurant_id: str, tables_data: list):
    """Broadcast full floor plan update"""
    message = {
        "type": "floor_plan_update",
        "data": tables_data,
        "timestamp": datetime.utcnow().isoformat(),
        "restaurant_id": restaurant_id
    }
    await manager.broadcast_to_restaurant(message, restaurant_id)

# Export the broadcast functions for use in other modules
__all__ = [
    "router",
    "broadcast_table_update",
    "broadcast_reservation_update", 
    "broadcast_floor_plan_update"
]
