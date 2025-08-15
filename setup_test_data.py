"""Setup test data for iPad app integration"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import Restaurant, User, RestaurantTable, Reservation
from app.utils.security import get_password_hash

def create_test_data():
    db = SessionLocal()
    try:
        print("Creating test data...")
        
        # Create restaurant
        existing = db.query(Restaurant).filter(Restaurant.id == 'test-restaurant-1').first()
        if not existing:
            restaurant = Restaurant(
                id='test-restaurant-1',
                name='Test Restaurant',
                slug='test-restaurant-1',
                email='restaurant@test.com'
            )
            db.add(restaurant)
            print("Created restaurant")
        
        # Create user
        existing_user = db.query(User).filter(User.email == 'test@restaurant.com').first()
        if not existing_user:
            user = User(
                restaurant_id='test-restaurant-1',
                email='test@restaurant.com',
                password_hash=get_password_hash('password123'),
                first_name='Test',
                last_name='User',
                role='owner'
            )
            db.add(user)
            print("Created user: test@restaurant.com / password123")
        
        # Create tables
        tables = [
            {'id': 'table-1', 'number': '1', 'capacity': 4, 'x': 0.2, 'y': 0.3},
            {'id': 'table-2', 'number': '2', 'capacity': 6, 'x': 0.6, 'y': 0.2},
            {'id': 'table-3', 'number': '3', 'capacity': 2, 'x': 0.1, 'y': 0.7}
        ]
        
        for t in tables:
            existing_table = db.query(RestaurantTable).filter(RestaurantTable.id == t['id']).first()
            if not existing_table:
                table = RestaurantTable(
                    id=t['id'],
                    restaurant_id='test-restaurant-1',
                    table_number=t['number'],
                    capacity=t['capacity'],
                    position_x=t['x'],
                    position_y=t['y'],
                    shape='round',
                    status='available'
                )
                db.add(table)
        print("Created tables")
        
        # Create reservations
        reservations = [
            {'id': 'res-1', 'name': 'John Doe', 'size': 2, 'status': 'waitlist'},
            {'id': 'res-2', 'name': 'Jane Smith', 'size': 4, 'status': 'seated'},
            {'id': 'res-3', 'name': 'Bob Johnson', 'size': 6, 'status': 'arrived'}
        ]
        
        for r in reservations:
            existing_res = db.query(Reservation).filter(Reservation.id == r['id']).first()
            if not existing_res:
                reservation = Reservation(
                    id=r['id'],
                    restaurant_id='test-restaurant-1',
                    guest_name=r['name'],
                    party_size=r['size'],
                    status=r['status']
                )
                db.add(reservation)
        print("Created reservations")
        
        db.commit()
        print("\n✅ SUCCESS! Test data created!")
        print("📱 iPad can now authenticate with:")
        print("   Email: test@restaurant.com")
        print("   Password: password123")
        print("   Restaurant ID: test-restaurant-1")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_test_data()
