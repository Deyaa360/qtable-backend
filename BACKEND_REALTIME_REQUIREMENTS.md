# 🚀 Backend Real-Time WebSocket Implementation Requirements

## Current Status
✅ **WebSocket Connection**: Working perfectly - clients connect to `ws://10.0.0.152:8000/realtime`  
✅ **Heartbeat System**: Ping/pong working correctly every 30 seconds  
✅ **Client Implementation**: Ready to receive and process real-time updates immediately  

❌ **Missing**: Data change notifications over WebSocket when restaurant data is modified

## The Problem
**Current Behavior**:
- Device A updates guest status → Backend saves to database ✅
- Device B sees no change until next polling cycle (3+ seconds) ❌

**Required Behavior**:
- Device A updates guest status → Backend saves to database ✅  
- Backend broadcasts WebSocket notification to all connected devices ✅
- Device B receives notification and updates UI immediately (~200ms) ✅

## Required Implementation

### 1. Data Change Detection
When ANY of these API endpoints receive data changes, trigger WebSocket broadcast:

#### Guest Operations:
```
POST   /restaurants/{id}/guests           # New walk-in guest
PUT    /restaurants/{id}/guests/{guest_id} # Status change, seating, etc.
PATCH  /restaurants/{id}/guests/{guest_id} # Partial updates
DELETE /restaurants/{id}/guests/{guest_id} # Guest removal
```

#### Table Operations:
```
PUT    /restaurants/{id}/tables/{table_id} # Table status change
PATCH  /restaurants/{id}/tables/{table_id} # Table updates
```

#### Transaction Operations:
```
POST   /transactions/atomic # Batch updates (multiple guests/tables)
```

### 2. WebSocket Message Format
When data changes occur, broadcast these JSON messages to ALL connected WebSocket clients:

#### Guest Updates:
```json
{
  "type": "guest_updated",
  "restaurant_id": "test-restaurant-1", 
  "guest_id": "guest-123",
  "action": "status_change",
  "timestamp": "2025-08-16T07:21:27.177385Z",
  "data": {
    "id": "guest-123",
    "status": "seated",
    "table_id": "table-456"
  }
}
```

#### New Guest Created:
```json
{
  "type": "guest_created",
  "restaurant_id": "test-restaurant-1",
  "guest_id": "guest-789", 
  "timestamp": "2025-08-16T07:21:27.177385Z",
  "data": {
    "id": "guest-789",
    "guestName": "John Doe",
    "partySize": 4,
    "status": "waiting"
  }
}
```

#### Table Updates:
```json
{
  "type": "table_updated", 
  "restaurant_id": "test-restaurant-1",
  "table_id": "table-456",
  "timestamp": "2025-08-16T07:21:27.177385Z",
  "data": {
    "id": "table-456",
    "status": "occupied",
    "guest_id": "guest-123"
  }
}
```

#### Atomic Transactions:
```json
{
  "type": "atomic_transaction_complete",
  "restaurant_id": "test-restaurant-1", 
  "timestamp": "2025-08-16T07:21:27.177385Z",
  "affected_entities": ["guest-123", "guest-456", "table-789"]
}
```

### 3. Broadcasting Logic

#### Current WebSocket Manager Structure:
```python
# Your existing WebSocket manager probably looks like this:
class WebSocketManager:
    def __init__(self):
        self.connections = {}  # {restaurant_id: [websocket_connections]}
    
    async def connect(self, websocket, restaurant_id):
        # Add to connections dict
        pass
    
    async def disconnect(self, websocket, restaurant_id): 
        # Remove from connections dict
        pass
```

#### Add Broadcasting Method:
```python
async def broadcast_data_change(self, restaurant_id: str, message: dict):
    """
    Broadcast data change to all connected clients for a restaurant
    """
    if restaurant_id not in self.connections:
        return
        
    # Convert to JSON string
    json_message = json.dumps(message)
    
    # Send to all connected clients for this restaurant
    disconnected = []
    for websocket in self.connections[restaurant_id]:
        try:
            await websocket.send_text(json_message)
            print(f"📡 Broadcast sent to client: {message['type']}")
        except Exception as e:
            print(f"❌ Failed to send to client: {e}")
            disconnected.append(websocket)
    
    # Clean up disconnected clients
    for ws in disconnected:
        self.connections[restaurant_id].remove(ws)
```

### 4. Integration Points

#### In Guest API Endpoints:
```python
@app.put("/restaurants/{restaurant_id}/guests/{guest_id}")
async def update_guest(restaurant_id: str, guest_id: str, guest_data: GuestUpdate):
    # 1. Save to database (existing code)
    updated_guest = await save_guest_to_db(guest_id, guest_data)
    
    # 2. NEW: Broadcast WebSocket notification
    await websocket_manager.broadcast_data_change(restaurant_id, {
        "type": "guest_updated",
        "restaurant_id": restaurant_id,
        "guest_id": guest_id, 
        "action": "update",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": updated_guest.dict()  # Include the full updated guest data
    })
    
    # 3. Return response (existing code)
    return {"success": True, "guest": updated_guest}
```

#### In Table API Endpoints:
```python
@app.put("/restaurants/{restaurant_id}/tables/{table_id}")
async def update_table(restaurant_id: str, table_id: str, table_data: TableUpdate):
    # 1. Save to database
    updated_table = await save_table_to_db(table_id, table_data)
    
    # 2. NEW: Broadcast WebSocket notification  
    await websocket_manager.broadcast_data_change(restaurant_id, {
        "type": "table_updated",
        "restaurant_id": restaurant_id,
        "table_id": table_id,
        "timestamp": datetime.utcnow().isoformat() + "Z", 
        "data": updated_table.dict()
    })
    
    return {"success": True, "table": updated_table}
```

#### In Atomic Transaction Endpoint:
```python
@app.post("/transactions/atomic")
async def atomic_transaction(restaurant_id: str, transaction_data: AtomicTransaction):
    # 1. Process all updates in transaction (existing code)
    results = await process_atomic_transaction(transaction_data)
    
    # 2. NEW: Broadcast single notification for all changes
    affected_entities = []
    for result in results:
        affected_entities.append(result.entity_id)
    
    await websocket_manager.broadcast_data_change(restaurant_id, {
        "type": "atomic_transaction_complete", 
        "restaurant_id": restaurant_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "affected_entities": affected_entities
    })
    
    return {"success": True, "results": results}
```

## Testing Instructions

### 1. Verify Current Setup:
- ✅ WebSocket connection at `ws://10.0.0.152:8000/realtime` works
- ✅ Ping/pong heartbeat every 30 seconds works  
- ✅ Restaurant identification message received: `{"type": "restaurant_connect", "restaurant_id": "test-restaurant", "platform": "iOS"}`

### 2. Test Real-Time Updates:
1. **Connect two iOS devices** to the same restaurant
2. **Device A**: Update a guest status (waiting → seated)
3. **Expected**: Device B should see the update within ~200ms (no manual refresh)
4. **Current**: Device B only sees update after 3+ seconds via polling

### 3. Debug Logs:
When broadcasting, add these logs to backend:
```python
print(f"📡 Broadcasting {message['type']} to {len(connections)} clients")
print(f"🎯 Message: {json_message}")
```

### 4. Verification on iOS:
When working correctly, iOS logs will show:
```
🔥 WebSocket message received: {"type": "guest_updated", "guest_id": "123"...
⚡ REAL data change detected via WebSocket - triggering immediate sync  
⚡ WebSocket notification sent in 0ms
✅ Real-time data refreshed successfully
```

## Performance Requirements
- **Latency**: WebSocket broadcast should occur within 50ms of API response
- **Reliability**: If WebSocket broadcast fails, API should still succeed  
- **Scalability**: Support 10+ concurrent devices per restaurant
- **Local Network**: ~200ms end-to-end update time on local network

## Current Implementation Status
✅ **iOS Client**: Ready to receive and process real-time WebSocket notifications  
✅ **WebSocket Infrastructure**: Connection and heartbeat working  
❌ **Data Change Broadcasting**: **NEEDS IMPLEMENTATION**

## Priority Implementation Order
1. **Guest status updates** (highest priority - most common operation)
2. **New walk-in guest creation** 
3. **Table status changes**
4. **Atomic transaction broadcasting**

The iOS app is fully ready to receive these WebSocket notifications and will update the UI immediately upon receipt. The missing piece is the backend broadcasting data changes when they occur.

Please implement the broadcasting functionality and test with two connected devices to verify ~200ms real-time updates are working.
