#!/usr/bin/env python3
"""
Script to add missing table assignment fields to the guests table
"""
import sqlite3
import sys
import os

# Add the project root to the path so we can import modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def add_guest_table_assignment_fields():
    """Add the missing table assignment fields to the guests table"""
    
    # Connect to the database
    db_path = "qtable.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List of new fields to add
    new_fields = [
        ("party_size", "INTEGER"),
        ("status", "VARCHAR(20) DEFAULT 'waitlist'"),
        ("table_id", "VARCHAR"),
        ("reservation_time", "DATETIME"),
        ("check_in_time", "DATETIME"),
        ("seated_time", "DATETIME"),
        ("finished_time", "DATETIME")
    ]
    
    # Check which fields already exist
    cursor.execute("PRAGMA table_info(guests)")
    existing_columns = [column[1] for column in cursor.fetchall()]
    print(f"Existing columns: {existing_columns}")
    
    # Add missing fields
    for field_name, field_type in new_fields:
        if field_name not in existing_columns:
            try:
                sql = f"ALTER TABLE guests ADD COLUMN {field_name} {field_type}"
                print(f"Adding column: {sql}")
                cursor.execute(sql)
                print(f"✅ Added column: {field_name}")
            except sqlite3.Error as e:
                print(f"❌ Error adding column {field_name}: {e}")
        else:
            print(f"⏭️  Column {field_name} already exists")
    
    # Commit changes
    conn.commit()
    
    # Verify the new structure
    cursor.execute("PRAGMA table_info(guests)")
    all_columns = [column[1] for column in cursor.fetchall()]
    print(f"Final columns: {all_columns}")
    
    conn.close()
    print("✅ Database update complete!")

if __name__ == "__main__":
    add_guest_table_assignment_fields()
