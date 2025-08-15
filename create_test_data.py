#!/usr/bin/env python3
"""
Test data setup script for QTable Backend API
Creates test restaurant, user, tables, and guests for iPad app testing
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app.database import SessionLocal, engine, Base
from app.models import Restaurant, User, RestaurantTable, Guest, Reservation
from app.utils.security import get_password_hash
import uuid

def create_test_data():
    """Create test data for iPad app testing"""
    
    # Create database session
    db = SessionLocal()
    
    try:
        print("🗄️  Creating test data for QTable API...")
        
        # Create test restaurant
        restaurant = Restaurant(
            id="test-restaurant-1",  # Fixed ID for testing
            name="Test Restaurant",
            slug="test-restaurant-1",
            email="test@restaurant.com",
            subscription_tier="pro",
            subscription_status="active",
            is_active=True
        )
        
        # Check if restaurant already exists
        existing_restaurant = db.query(Restaurant).filter(Restaurant.id == "test-restaurant-1").first()
        if not existing_restaurant:
            db.add(restaurant)
            db.flush()
            print(f"✅ Created restaurant: {restaurant.name} (ID: {restaurant.id})")
        else:
            restaurant = existing_restaurant
            print(f"ℹ️  Restaurant already exists: {restaurant.name}")
        
        # Create test user
        user = User(
            id=str(uuid.uuid4()),
            restaurant_id="test-restaurant-1",
            email="test@restaurant.com",
            password_hash=get_password_hash("password123"),
            first_name="Test",
            last_name="User",
            role="owner",
            is_active=True
        )
        
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == "test@restaurant.com").first()
        if not existing_user:
            db.add(user)
            db.flush()
            print(f"✅ Created user: {user.email} (Password: password123)")
        else:
            user = existing_user
            print(f"ℹ️  User already exists: {user.email}")
        
        # Create test tables
        tables_data = [
            {
                "id": "table-1",
                "table_number": "1",
                "capacity": 4,
                "position_x": 0.2,  # 100px at 500px width = 0.2
                "position_y": 0.2,  # 100px at 500px height = 0.2
                "shape": "round",
                "section": "Main Dining",
                "status": "available"
            },
            {
                "id": "table-2", 
                "table_number": "2",
                "capacity": 6,
                "position_x": 0.4,  # 200px at 500px width = 0.4
                "position_y": 0.3,  # 150px at 500px height = 0.3
                "shape": "rectangle",
                "section": "Main Dining", 
                "status": "occupied"
            },
            {
                "id": "table-3",
                "table_number": "3", 
                "capacity": 2,
                "position_x": 0.6,
                "position_y": 0.5,
                "shape": "round",
                "section": "Bar",
                "status": "available"
            },
            {
                "id": "table-4",
                "table_number": "4",
                "capacity": 8,
                "position_x": 0.3,
                "position_y": 0.7,
                "shape": "rectangle", 
                "section": "Main Dining",
                "status": "reserved"
            }
        ]
        
        for table_data in tables_data:
            existing_table = db.query(RestaurantTable).filter(
                RestaurantTable.id == table_data["id"]
            ).first()
            
            if not existing_table:
                table = RestaurantTable(
                    id=table_data["id"],
                    restaurant_id="test-restaurant-1",
                    table_number=table_data["table_number"],
                    capacity=table_data["capacity"],
                    position_x=table_data["position_x"],
                    position_y=table_data["position_y"],
                    shape=table_data["shape"],
                    section=table_data["section"],
                    status=table_data["status"]
                )
                db.add(table)
                print(f"✅ Created table: Table {table.table_number} ({table.capacity} seats, {table.status})")
            else:
                print(f"ℹ️  Table {table_data['table_number']} already exists")
        
        # Create test guests/reservations
        # First create guest profiles that the iPad app expects
        guests_data = [
            {
                "id": "63067C72-D36A-4261-B4B2-921BEBAF33DF",  # The UUID iPad is trying to access
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone": "+1234567890",
                "notes": "Birthday celebration"
            },
            {
                "id": "3D66189F-C51D-405A-8E47-D3962DE78121",  # Another UUID iPad is trying to access
                "first_name": "Jane", 
                "last_name": "Smith",
                "email": "jane.smith@example.com",
                "phone": "+1987654321",
                "notes": "Anniversary dinner"
            },
            {
                "id": "guest-3",
                "first_name": "Bob",
                "last_name": "Wilson",
                "email": "bob.wilson@example.com", 
                "phone": "+1555123456",
                "notes": "Business meeting"
            },
            {
                "id": "guest-4",
                "first_name": "Alice",
                "last_name": "Johnson",
                "email": "alice.johnson@example.com",
                "phone": "+1444987654",
                "notes": "Family dinner"
            }
        ]
        
        for guest_data in guests_data:
            existing_guest = db.query(Guest).filter(Guest.id == guest_data["id"]).first()
            
            if not existing_guest:
                guest = Guest(
                    id=guest_data["id"],
                    restaurant_id="test-restaurant-1",  # CRITICAL: Multi-tenant isolation
                    first_name=guest_data["first_name"],
                    last_name=guest_data["last_name"],
                    email=guest_data["email"],
                    phone=guest_data["phone"],
                    notes=guest_data["notes"],
                    total_visits=0,
                    dietary_restrictions=[]
                )
                db.add(guest)
                db.flush()
                print(f"✅ Created guest: {guest.first_name} {guest.last_name} ({guest.email})")
            else:
                print(f"ℹ️  Guest {guest_data['first_name']} {guest_data['last_name']} already exists")
        
        # Now create reservations linked to guests
        reservations_data = [
            {
                "id": "res-1",
                "guest_id": "63067C72-D36A-4261-B4B2-921BEBAF33DF",
                "guest_name": "John Doe",
                "party_size": 2,
                "status": "waitlist",
                "guest_phone": "+1234567890",
                "notes": "Birthday celebration"
            },
            {
                "id": "res-2", 
                "guest_id": "3D66189F-C51D-405A-8E47-D3962DE78121",
                "guest_name": "Jane Smith",
                "party_size": 4,
                "status": "seated",
                "table_id": "table-2",
                "guest_phone": "+1987654321",
                "notes": "Anniversary dinner"
            },
            {
                "id": "res-3",
                "guest_id": "guest-3",
                "guest_name": "Bob Wilson", 
                "party_size": 6,
                "status": "arrived",
                "guest_phone": "+1555123456",
                "notes": "Business meeting"
            },
            {
                "id": "res-4",
                "guest_id": "guest-4",
                "guest_name": "Alice Johnson",
                "party_size": 3,
                "status": "confirmed",
                "guest_phone": "+1444987654",
                "notes": "Family dinner"
            }
        ]
        
        for res_data in reservations_data:
            existing_reservation = db.query(Reservation).filter(
                Reservation.id == res_data["id"]
            ).first()
            
            if not existing_reservation:
                reservation = Reservation(
                    id=res_data["id"],
                    restaurant_id="test-restaurant-1",
                    guest_id=res_data["guest_id"],
                    guest_name=res_data["guest_name"],
                    party_size=res_data["party_size"],
                    status=res_data["status"],
                    guest_phone=res_data["guest_phone"],
                    notes=res_data["notes"],
                    table_id=res_data.get("table_id")
                )
                db.add(reservation)
                
                # Update table status if guest is seated
                if res_data["status"] == "seated" and res_data.get("table_id"):
                    table = db.query(RestaurantTable).filter(
                        RestaurantTable.id == res_data["table_id"]
                    ).first()
                    if table:
                        table.current_guest_id = res_data["id"]
                        table.status = "occupied"
                
                print(f"✅ Created reservation: {reservation.guest_name} (Party of {reservation.party_size}, {reservation.status})")
            else:
                print(f"ℹ️  Reservation for {res_data['guest_name']} already exists")
        
        # Commit all changes
        db.commit()
        
        print("\n🎉 Test data created successfully!")
        print("\n📋 Test Credentials:")
        print("   Email: test@restaurant.com")
        print("   Password: password123")
        print("   Restaurant ID: test-restaurant-1")
        
        print("\n📊 Test Data Summary:")
        print(f"   🏪 Restaurant: Test Restaurant")
        print(f"   👤 User: test@restaurant.com (owner)")
        print(f"   🪑 Tables: {len(tables_data)} tables with various statuses")
        print(f"   👥 Reservations: {len(reservations_data)} guests with different statuses")
        
        print("\n🔗 API Endpoints to test:")
        print("   POST http://10.0.0.152:8000/auth/login")
        print("   GET  http://10.0.0.152:8000/restaurants/test-restaurant-1/tables")
        print("   GET  http://10.0.0.152:8000/restaurants/test-restaurant-1/reservations")
        
    except Exception as e:
        print(f"❌ Error creating test data: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_test_data()
