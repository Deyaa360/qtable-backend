#!/usr/bin/env python3
"""
Debug script to test the dashboard endpoint and compare with individual endpoints
"""
import sys
import os
import json

# Add the project root to the path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_db
from app.models import Guest, RestaurantTable
from app.api.dashboard import guest_to_minimal_response, table_to_minimal_response
from app.api.guests import guest_to_response

def debug_dashboard_data():
    """Debug the dashboard endpoint data conversion"""
    
    print("🔍 Debugging Dashboard Data Endpoint...")
    
    # Get a database session
    db = next(get_db())
    
    try:
        # Get guests (same query as individual endpoint)
        guests = db.query(Guest).order_by(Guest.created_at.desc()).all()
        print(f"📊 Found {len(guests)} guests in database")
        
        if guests:
            print("\n--- INDIVIDUAL GUEST ENDPOINT FORMAT ---")
            guest = guests[0]
            individual_response = guest_to_response(guest)
            print(f"Guest ID: {individual_response.id}")
            print(f"Name: {individual_response.name}")
            print(f"Status: {individual_response.status}")
            print(f"Table ID: {individual_response.tableId}")
            print(f"Party Size: {individual_response.partySize}")
            
            print("\n--- DASHBOARD MINIMAL FORMAT ---")
            minimal_response = guest_to_minimal_response(guest)
            print(f"Guest ID: {minimal_response.id}")
            print(f"Name: {minimal_response.name}")
            print(f"Status: {minimal_response.status}")
            print(f"Table ID: {minimal_response.tableId}")
            print(f"Party Size: {minimal_response.partySize}")
            
            print("\n--- RAW GUEST DATA ---")
            print(f"Raw guest.id: {guest.id}")
            print(f"Raw guest.first_name: {guest.first_name}")
            print(f"Raw guest.last_name: {guest.last_name}")
            print(f"Raw guest.status: {guest.status}")
            print(f"Raw guest.table_id: {guest.table_id}")
            print(f"Raw guest.party_size: {guest.party_size}")
            print(f"Raw guest.updated_at: {guest.updated_at}")
        
        # Get tables
        tables = db.query(RestaurantTable).filter(
            RestaurantTable.is_active == True
        ).order_by(RestaurantTable.table_number).all()
        print(f"\n📊 Found {len(tables)} tables in database")
        
        if tables:
            print("\n--- TABLE MINIMAL FORMAT ---")
            table = tables[0]
            table_response = table_to_minimal_response(table)
            print(f"Table ID: {table_response.id}")
            print(f"Table Number: {table_response.tableNumber}")
            print(f"Status: {table_response.status}")
            print(f"Current Guest ID: {table_response.currentGuestId}")
            
            print("\n--- RAW TABLE DATA ---")
            print(f"Raw table.id: {table.id}")
            print(f"Raw table.table_number: {table.table_number}")
            print(f"Raw table.status: {table.status}")
            print(f"Raw table.current_guest_id: {table.current_guest_id}")
            print(f"Raw table.updated_at: {table.updated_at}")
        
        print("\n✅ Debug complete!")
        
    except Exception as e:
        print(f"❌ Error debugging dashboard data: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()

if __name__ == "__main__":
    debug_dashboard_data()
