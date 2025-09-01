#!/usr/bin/env python3
"""
Database initialization script for Railway deployment
Creates tables and admin user with proper error handling
"""
import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    """Initialize database tables and admin user"""
    try:
        # Add current directory to path
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        logger.info("🔧 Starting database initialization...")
        
        # Import after path setup
        from app.database import engine, get_db
        from app.models import Base, User, Restaurant
        from app.utils.security import get_password_hash
        from sqlalchemy.orm import sessionmaker
        
        # Create all tables
        logger.info("📊 Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully")
        
        # Create session
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            # Check if admin user exists
            admin_email = "test@restaurant.com"
            existing_admin = db.query(User).filter(User.email == admin_email).first()
            
            if not existing_admin:
                logger.info("🏪 Creating restaurant...")
                
                # Create restaurant
                restaurant = Restaurant(
                    name="QTable Restaurant",
                    slug="qtable-restaurant",
                    address="123 Restaurant Street, City, State",
                    is_active=True
                )
                db.add(restaurant)
                db.flush()  # Get the restaurant ID
                
                logger.info(f"✅ Restaurant created: {restaurant.name} (ID: {restaurant.id})")
                
                # Create admin user
                logger.info("👤 Creating admin user...")
                admin_user = User(
                    email=admin_email,
                    hashed_password=get_password_hash("password123"),
                    full_name="Restaurant Admin",
                    role="admin",
                    restaurant_id=restaurant.id,
                    is_active=True
                )
                db.add(admin_user)
                db.commit()
                
                logger.info(f"✅ Admin user created: {admin_email}")
                logger.info("🎉 Database initialization complete!")
                
            else:
                logger.info(f"✅ Admin user already exists: {admin_email}")
                logger.info("🎉 Database already initialized!")
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    init_database()
