# This is the corrected broadcast section for batch.py

# Broadcast individual guest updates (iOS requires these!)
for guest in updated_guests:
    try:
        logger.error(f"🔥 [BATCH v2] About to broadcast guest_updated for guest {guest.id}")
        logger.error(f"🔥 [BATCH v2] Guest data: name={guest.firstName} {guest.lastName}, status={guest.status}")
        
        guest_data = {
            "guestName": f"{guest.firstName or ''} {guest.lastName or ''}".strip() or "Unknown Guest",
            "firstName": guest.firstName or '',
            "lastName": guest.lastName or '',
            "partySize": guest.partySize or 1,
            "status": guest.status,
            "table_id": str(guest.tableId) if guest.tableId else None,
            "email": guest.email or '',
            "phone": guest.phone or '',
            "notes": guest.notes or ''
        }
        
        logger.error(f"🔥 [BATCH v2] Calling broadcast_guest_updated with data: {guest_data}")
        
        await realtime_broadcaster.broadcast_guest_updated(
            restaurant_id=restaurant_id,
            guest_id=str(guest.id),
            action="status_changed",
            guest_data=guest_data
        )
        logger.error(f"🔥 [BATCH v2] ✅ Successfully broadcasted guest_updated for guest {guest.id}")
        
    except Exception as e:
        logger.error(f"🔥 [BATCH v2] ❌ FAILED to broadcast guest_updated for guest {guest.id}: {e}")
        import traceback
        logger.error(f"🔥 [BATCH v2] ❌ Full traceback: {traceback.format_exc()}")

# Broadcast individual table updates
for table in updated_tables:
    try:
        logger.error(f"🔥 [BATCH v2] About to broadcast table_updated for table {table.id}")
        logger.error(f"🔥 [BATCH v2] Table data: number={table.tableNumber}, status={table.status}")
        
        table_data = {
            "id": str(table.id),
            "table_number": table.tableNumber,
            "status": table.status,
            "current_guest_id": str(table.currentGuestId) if table.currentGuestId else None,
            "capacity": table.capacity,
            "x": table.position.get("x", 0.0) if table.position else 0.0,
            "y": table.position.get("y", 0.0) if table.position else 0.0,
            "shape": table.shape or "rectangle",
            "section": table.section or ""
        }
        
        logger.error(f"🔥 [BATCH v2] Calling broadcast_table_updated with data: {table_data}")
        
        await realtime_broadcaster.broadcast_table_updated(
            restaurant_id=restaurant_id,
            table_id=str(table.id),
            action="status_changed",
            table_data=table_data
        )
        logger.error(f"🔥 [BATCH v2] ✅ Successfully broadcasted table_updated for table {table.id}")
        
    except Exception as e:
        logger.error(f"🔥 [BATCH v2] ❌ FAILED to broadcast table_updated for table {table.id}: {e}")
        import traceback
        logger.error(f"🔥 [BATCH v2] ❌ Full traceback: {traceback.format_exc()}")
