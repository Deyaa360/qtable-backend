#!/usr/bin/env python3
"""
Production setup script - Run ONCE after deployment
Creates initial admin user and restaurant
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, User, Restaurant
from app.utils.security import get_password_hash
from app.config import settings

def create_admin_user():
    """Create initial admin user for production"""
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Check if admin already exists
        existing_admin = db.query(User).filter(User.email == "admin@yourrestaurant.com").first()
        if existing_admin:
            print("❌ Admin user already exists!")
            return
        
        # Create restaurant
        restaurant = Restaurant(
            name="Your Restaurant Name",
            slug="your-restaurant",
            address="123 Main St, City, State"
        )
        db.add(restaurant)
        db.flush()  # Get the restaurant ID
        
        # Create admin user
        admin_user = User(
            email="admin@yourrestaurant.com",
            hashed_password=get_password_hash("admin123"),  # CHANGE THIS PASSWORD!
            full_name="Restaurant Admin",
            role="admin",
            restaurant_id=restaurant.id
        )
        db.add(admin_user)
        db.commit()
        
        print("✅ Production setup complete!")
        print("📧 Admin Email: admin@yourrestaurant.com")
        print("🔑 Admin Password: admin123")
        print("⚠️  IMPORTANT: Change this password immediately after first login!")
        print(f"🏪 Restaurant ID: {restaurant.id}")
        
    except Exception as e:
        print(f"❌ Setup failed: {str(e)}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_admin_user()
