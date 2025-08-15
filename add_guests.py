import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import Guest

def add_missing_guests():
    db = SessionLocal()
    try:
        # Add the specific guest UUIDs that the iPad is looking for
        guests_data = [
            {
                "id": "63067C72-D36A-4261-B4B2-921BEBAF33DF",
                "restaurant_id": "test-restaurant-1",
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone": "+1234567890",
                "notes": "Birthday celebration"
            },
            {
                "id": "3D66189F-C51D-405A-8E47-D3962DE78121",
                "restaurant_id": "test-restaurant-1",
                "first_name": "Jane", 
                "last_name": "Smith",
                "email": "jane.smith@example.com",
                "phone": "+1987654321",
                "notes": "Anniversary dinner"
            }
        ]
        
        for guest_data in guests_data:
            existing = db.query(Guest).filter(Guest.id == guest_data["id"]).first()
            if not existing:
                guest = Guest(
                    id=guest_data["id"],
                    first_name=guest_data["first_name"],
                    last_name=guest_data["last_name"],
                    email=guest_data["email"],
                    phone=guest_data["phone"],
                    notes=guest_data["notes"],
                    total_visits=0,
                    dietary_restrictions=[]
                )
                db.add(guest)
                print(f"✅ Created guest: {guest.first_name} {guest.last_name} ({guest.id})")
            else:
                print(f"ℹ️  Guest {guest_data['first_name']} {guest_data['last_name']} already exists")
        
        db.commit()
        print("✅ Guest data created successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_missing_guests()
