from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid
import logging
from pydantic import BaseModel

from app.database import get_db
from app.models import Guest, RestaurantTable, Restaurant
from app.dependencies import get_current_user
from app.api.websockets import broadcast_atomic_transaction_complete, broadcast_delta_update

router = APIRouter(prefix="/api/v1/atomic", tags=["atomic_operations"])
logger = logging.getLogger(__name__)

class AtomicGuestOperation(BaseModel):
    id: str
    operation: str  # "create", "update", "delete"
    data: Optional[Dict[str, Any]] = None

class AtomicTableOperation(BaseModel):
    id: str
    operation: str  # "create", "update", "delete"
    data: Optional[Dict[str, Any]] = None

class AtomicBatchRequest(BaseModel):
    transaction_id: str
    timestamp: str
    guests: Optional[List[AtomicGuestOperation]] = []
    tables: Optional[List[AtomicTableOperation]] = []
    metadata: Optional[Dict[str, Any]] = {}

class AtomicOperationResult(BaseModel):
    entity_type: str
    entity_id: str
    status: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class AtomicBatchResponse(BaseModel):
    success: bool
    transaction_id: str
    processed_at: str
    results: List[AtomicOperationResult]
    error: Optional[str] = None
    rolled_back: Optional[bool] = None

class AtomicTransactionService:
    """
    Enterprise-grade atomic transaction service for restaurant operations
    Implements ACID compliance with full rollback capability
    """
    
    @staticmethod
    def validate_transaction(db: Session, transaction_data: AtomicBatchRequest) -> None:
        """Validate ALL operations before executing ANY"""
        
        # Validate guest operations
        for guest_op in transaction_data.guests:
            if guest_op.operation == "create":
                if not guest_op.data:
                    raise ValueError(f"Guest create operation requires data")
                
                # Validate required fields for guest creation
                required_fields = ["first_name", "party_size", "restaurant_id"]
                for field in required_fields:
                    if field not in guest_op.data:
                        raise ValueError(f"Guest create operation missing required field: {field}")
                
                # Validate party size
                if guest_op.data.get("party_size", 0) < 1:
                    raise ValueError("Party size must be positive")
                    
            elif guest_op.operation == "update":
                # Check if guest exists
                guest = db.query(Guest).filter(Guest.id == guest_op.id).first()
                if not guest:
                    raise ValueError(f"Guest with ID {guest_op.id} not found")
                    
                # If assigning to table, validate table availability
                if guest_op.data and "table_id" in guest_op.data and guest_op.data["table_id"]:
                    table = db.query(RestaurantTable).filter(RestaurantTable.id == guest_op.data["table_id"]).first()
                    if not table:
                        raise ValueError(f"Table with ID {guest_op.data['table_id']} not found")
                    
                    # Check table capacity vs party size
                    party_size = guest_op.data.get("party_size", guest.party_size)
                    if party_size > table.capacity:
                        raise ValueError(f"Party size {party_size} exceeds table capacity {table.capacity}")
                        
            elif guest_op.operation == "delete":
                # Check if guest exists
                guest = db.query(Guest).filter(Guest.id == guest_op.id).first()
                if not guest:
                    raise ValueError(f"Guest with ID {guest_op.id} not found")
        
        # Validate table operations
        for table_op in transaction_data.tables:
            if table_op.operation == "create":
                if not table_op.data:
                    raise ValueError(f"Table create operation requires data")
                    
                # Validate required fields
                required_fields = ["table_number", "capacity", "restaurant_id"]
                for field in required_fields:
                    if field not in table_op.data:
                        raise ValueError(f"Table create operation missing required field: {field}")
                        
            elif table_op.operation == "update":
                # Check if table exists
                table = db.query(RestaurantTable).filter(RestaurantTable.id == table_op.id).first()
                if not table:
                    raise ValueError(f"Table with ID {table_op.id} not found")
                    
                # If changing capacity, validate against current guest
                if table_op.data and "capacity" in table_op.data and table.current_guest_id:
                    guest = db.query(Guest).filter(Guest.id == table.current_guest_id).first()
                    if guest and guest.party_size > table_op.data["capacity"]:
                        raise ValueError(f"Cannot reduce table capacity below current guest party size")
                        
            elif table_op.operation == "delete":
                # Check if table exists
                table = db.query(RestaurantTable).filter(RestaurantTable.id == table_op.id).first()
                if not table:
                    raise ValueError(f"Table with ID {table_op.id} not found")
                    
                # Cannot delete occupied table
                if table.current_guest_id:
                    raise ValueError(f"Cannot delete table {table_op.id}: currently occupied by guest {table.current_guest_id}")

    @staticmethod
    def execute_guest_operation(db: Session, operation: AtomicGuestOperation) -> AtomicOperationResult:
        """Execute a single guest operation"""
        try:
            if operation.operation == "create":
                # Create new guest
                guest_data = operation.data.copy()
                guest_data["id"] = operation.id
                guest_data["created_at"] = datetime.now(timezone.utc)
                guest_data["updated_at"] = datetime.now(timezone.utc)
                
                guest = Guest(**guest_data)
                db.add(guest)
                db.flush()  # Flush to get ID but don't commit yet
                
                return AtomicOperationResult(
                    entity_type="guest",
                    entity_id=operation.id,
                    status="created",
                    data=guest_to_dict(guest)
                )
                
            elif operation.operation == "update":
                guest = db.query(Guest).filter(Guest.id == operation.id).first()
                if not guest:
                    raise ValueError(f"Guest {operation.id} not found")
                
                # Store old values for atomic table operations
                old_table_id = guest.table_id
                old_status = guest.status
                
                # Update guest fields
                for field, value in operation.data.items():
                    if hasattr(guest, field):
                        setattr(guest, field, value)
                
                guest.updated_at = datetime.now(timezone.utc)
                
                # Handle automatic table clearing for status changes
                if "status" in operation.data:
                    new_status = operation.data["status"]
                    
                    # If guest status changes to finished/cancelled/no-show, clear table
                    if new_status in ["Finished", "Cancelled", "No Show"] and old_table_id:
                        table = db.query(RestaurantTable).filter(RestaurantTable.id == old_table_id).first()
                        if table:
                            table.status = "available"
                            table.current_guest_id = None
                            table.updated_at = datetime.now(timezone.utc)
                        
                        guest.table_id = None
                        
                        # Set finished time
                        if new_status == "Finished":
                            guest.finished_time = datetime.now(timezone.utc)
                
                # Handle table assignment changes
                if "table_id" in operation.data:
                    new_table_id = operation.data["table_id"]
                    
                    # Clear old table
                    if old_table_id and old_table_id != new_table_id:
                        old_table = db.query(RestaurantTable).filter(RestaurantTable.id == old_table_id).first()
                        if old_table:
                            old_table.status = "available"
                            old_table.current_guest_id = None
                            old_table.updated_at = datetime.now(timezone.utc)
                    
                    # Assign new table
                    if new_table_id:
                        new_table = db.query(RestaurantTable).filter(RestaurantTable.id == new_table_id).first()
                        if new_table:
                            new_table.status = "occupied"
                            new_table.current_guest_id = operation.id
                            new_table.updated_at = datetime.now(timezone.utc)
                            
                            # Update guest status to seated if assigning table
                            if guest.status not in ["Seated"]:
                                guest.status = "Seated"
                                guest.seated_time = datetime.now(timezone.utc)
                
                return AtomicOperationResult(
                    entity_type="guest",
                    entity_id=operation.id,
                    status="updated",
                    data=guest_to_dict(guest)
                )
                
            elif operation.operation == "delete":
                guest = db.query(Guest).filter(Guest.id == operation.id).first()
                if not guest:
                    raise ValueError(f"Guest {operation.id} not found")
                
                # Clear table assignment if any
                if guest.table_id:
                    table = db.query(RestaurantTable).filter(RestaurantTable.id == guest.table_id).first()
                    if table:
                        table.status = "available"
                        table.current_guest_id = None
                        table.updated_at = datetime.now(timezone.utc)
                
                db.delete(guest)
                
                return AtomicOperationResult(
                    entity_type="guest",
                    entity_id=operation.id,
                    status="deleted"
                )
                
        except Exception as e:
            return AtomicOperationResult(
                entity_type="guest",
                entity_id=operation.id,
                status="error",
                error=str(e)
            )

    @staticmethod
    def execute_table_operation(db: Session, operation: AtomicTableOperation) -> AtomicOperationResult:
        """Execute a single table operation"""
        try:
            if operation.operation == "create":
                # Create new table
                table_data = operation.data.copy()
                table_data["id"] = operation.id
                table_data["created_at"] = datetime.now(timezone.utc)
                table_data["updated_at"] = datetime.now(timezone.utc)
                
                table = RestaurantTable(**table_data)
                db.add(table)
                db.flush()
                
                return AtomicOperationResult(
                    entity_type="table",
                    entity_id=operation.id,
                    status="created",
                    data=table_to_dict(table)
                )
                
            elif operation.operation == "update":
                table = db.query(RestaurantTable).filter(RestaurantTable.id == operation.id).first()
                if not table:
                    raise ValueError(f"Table {operation.id} not found")
                
                # Update table fields
                for field, value in operation.data.items():
                    if hasattr(table, field):
                        setattr(table, field, value)
                
                table.updated_at = datetime.now(timezone.utc)
                
                return AtomicOperationResult(
                    entity_type="table",
                    entity_id=operation.id,
                    status="updated",
                    data=table_to_dict(table)
                )
                
            elif operation.operation == "delete":
                table = db.query(RestaurantTable).filter(RestaurantTable.id == operation.id).first()
                if not table:
                    raise ValueError(f"Table {operation.id} not found")
                
                db.delete(table)
                
                return AtomicOperationResult(
                    entity_type="table",
                    entity_id=operation.id,
                    status="deleted"
                )
                
        except Exception as e:
            return AtomicOperationResult(
                entity_type="table",
                entity_id=operation.id,
                status="error",
                error=str(e)
            )

def guest_to_dict(guest: Guest) -> dict:
    """Convert Guest model to dictionary"""
    return {
        "id": str(guest.id),
        "name": f"{guest.first_name or ''} {guest.last_name or ''}".strip() or "Unknown Guest",
        "first_name": guest.first_name,
        "last_name": guest.last_name,
        "party_size": guest.party_size,
        "status": guest.status,
        "table_id": str(guest.table_id) if guest.table_id else None,
        "phone": guest.phone,
        "email": guest.email,
        "notes": guest.notes,
        "check_in_time": guest.check_in_time.isoformat() if guest.check_in_time else None,
        "seated_time": guest.seated_time.isoformat() if guest.seated_time else None,
        "finished_time": guest.finished_time.isoformat() if guest.finished_time else None,
        "restaurant_id": str(guest.restaurant_id)
    }

def table_to_dict(table: RestaurantTable) -> dict:
    """Convert RestaurantTable model to dictionary"""
    return {
        "id": str(table.id),
        "table_number": table.table_number,
        "capacity": table.capacity,
        "status": table.status,
        "current_guest_id": str(table.current_guest_id) if table.current_guest_id else None,
        "position_x": float(table.position_x or 0.0),
        "position_y": float(table.position_y or 0.0),
        "restaurant_id": str(table.restaurant_id)
    }

@router.post("/batch", response_model=AtomicBatchResponse)
async def execute_atomic_batch(
    request: AtomicBatchRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Execute atomic batch operations with full ACID compliance
    
    Implements enterprise-grade atomic transactions for restaurant operations.
    Either ALL operations succeed or ALL are rolled back.
    """
    transaction_id = request.transaction_id
    logger.info(f"Starting atomic transaction {transaction_id} with {len(request.guests)} guest ops and {len(request.tables)} table ops")
    
    try:
        # Start database transaction
        with db.begin():
            # Validate all operations before executing any
            AtomicTransactionService.validate_transaction(db, request)
            
            results = []
            
            # Execute guest operations
            for guest_op in request.guests:
                result = AtomicTransactionService.execute_guest_operation(db, guest_op)
                results.append(result)
                
                # If any operation failed, raise exception to trigger rollback
                if result.status == "error":
                    raise ValueError(f"Guest operation failed: {result.error}")
            
            # Execute table operations
            for table_op in request.tables:
                result = AtomicTransactionService.execute_table_operation(db, table_op)
                results.append(result)
                
                # If any operation failed, raise exception to trigger rollback
                if result.status == "error":
                    raise ValueError(f"Table operation failed: {result.error}")
            
            # All operations succeeded, commit will happen automatically
            response = AtomicBatchResponse(
                success=True,
                transaction_id=transaction_id,
                processed_at=datetime.now(timezone.utc).isoformat(),
                results=results
            )
            
            # Broadcast atomic transaction completion to all clients
            try:
                changes = []
                for result in results:
                    if result.status != "error":
                        changes.append({
                            "entity_type": result.entity_type,
                            "entity_id": result.entity_id,
                            "action": result.status,  # "created", "updated", "deleted"
                            "data": result.data
                        })
                
                # Broadcast to all connected iOS devices
                await broadcast_atomic_transaction_complete(transaction_id, changes)
                
            except Exception as e:
                logger.warning(f"Failed to broadcast atomic transaction completion: {e}")
            
            logger.info(f"Atomic transaction {transaction_id} completed successfully with {len(results)} operations")
            return response
            
    except Exception as e:
        # Transaction automatically rolled back due to exception
        logger.error(f"Atomic transaction {transaction_id} failed and rolled back: {e}")
        
        return AtomicBatchResponse(
            success=False,
            transaction_id=transaction_id,
            processed_at=datetime.now(timezone.utc).isoformat(),
            results=[],
            error=str(e),
            rolled_back=True
        )

@router.get("/health")
async def atomic_health_check():
    """Health check endpoint for atomic operations service"""
    return {
        "status": "healthy",
        "service": "atomic_operations",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "features": [
            "atomic_batch_operations",
            "acid_compliance", 
            "automatic_rollback",
            "real_time_broadcasting",
            "concurrent_transaction_support"
        ]
    }
