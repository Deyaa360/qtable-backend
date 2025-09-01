#!/usr/bin/env python3
"""
One-time script to convert existing table coordinates from pixels to normalized (0.0-1.0)
Run this after deploying the coordinate normalization fix
"""
import sys
import os
import logging

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models.table import RestaurantTable

# Canvas size constants (same as in API)
CANVAS_WIDTH = 800.0
CANVAS_HEIGHT = 600.0

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_table_coordinates():
    """Convert existing table coordinates from pixels to normalized"""
    db = SessionLocal()
    
    try:
        # Get all tables
        tables = db.query(RestaurantTable).all()
        logger.info(f"Found {len(tables)} tables to potentially convert")
        
        converted_count = 0
        
        for table in tables:
            # Check if coordinates need conversion (> 1.0 means pixel coordinates)
            if table.position_x > 1.0 or table.position_y > 1.0:
                logger.info(f"Converting table {table.table_number}: ({table.position_x}, {table.position_y}) -> ", end="")
                
                # Convert to normalized coordinates
                new_x = table.position_x / CANVAS_WIDTH if table.position_x > 1.0 else table.position_x
                new_y = table.position_y / CANVAS_HEIGHT if table.position_y > 1.0 else table.position_y
                
                # Ensure within bounds
                new_x = max(0.0, min(1.0, new_x))
                new_y = max(0.0, min(1.0, new_y))
                
                # Update the table
                table.position_x = new_x
                table.position_y = new_y
                
                logger.info(f"({new_x:.3f}, {new_y:.3f})")
                converted_count += 1
            else:
                logger.info(f"Table {table.table_number} already has normalized coordinates: ({table.position_x:.3f}, {table.position_y:.3f})")
        
        # Commit changes
        if converted_count > 0:
            db.commit()
            logger.info(f"✅ Successfully converted {converted_count} tables to normalized coordinates")
        else:
            logger.info("✅ All tables already have normalized coordinates")
            
    except Exception as e:
        logger.error(f"❌ Error converting coordinates: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    convert_table_coordinates()
