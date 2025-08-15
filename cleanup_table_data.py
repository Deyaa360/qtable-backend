#!/usr/bin/env python3
"""
Database cleanup script to fix corrupted table data
"""

import sqlite3
from datetime import datetime

def main():
    conn = sqlite3.connect('qtable.db')
    cursor = conn.cursor()
    
    print("🔍 Checking for corrupted table data...")
    
    # Check for corrupted data
    cursor.execute("""
        SELECT table_number, status, current_guest_id, updated_at 
        FROM restaurant_tables 
        WHERE status IN ('available', 'reserved', 'outOfService') 
        AND current_guest_id IS NOT NULL
    """)
    
    corrupted_tables = cursor.fetchall()
    
    if corrupted_tables:
        print(f"🚨 Found {len(corrupted_tables)} corrupted tables:")
        for row in corrupted_tables:
            print(f"   Table {row[0]}: status='{row[1]}', currentGuestId='{row[2]}'")
        
        print("\n🧹 Cleaning up corrupted data...")
        
        # Fix corrupted data
        cursor.execute("""
            UPDATE restaurant_tables 
            SET current_guest_id = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE status IN ('available', 'reserved', 'outOfService') 
            AND current_guest_id IS NOT NULL
        """)
        
        rows_updated = cursor.rowcount
        conn.commit()
        
        print(f"✅ Cleaned up {rows_updated} corrupted table records")
        
        # Verify the fix
        cursor.execute("""
            SELECT COUNT(*) 
            FROM restaurant_tables 
            WHERE status IN ('available', 'reserved', 'outOfService') 
            AND current_guest_id IS NOT NULL
        """)
        
        remaining_corrupted = cursor.fetchone()[0]
        if remaining_corrupted == 0:
            print("✅ All table data is now consistent!")
        else:
            print(f"⚠️  Still {remaining_corrupted} corrupted records remaining")
    else:
        print("✅ No corrupted table data found")
    
    # Show current table state
    print("\n📊 Current table status:")
    cursor.execute("""
        SELECT table_number, status, current_guest_id 
        FROM restaurant_tables 
        ORDER BY table_number
    """)
    
    all_tables = cursor.fetchall()
    for row in all_tables:
        guest_id = row[2] if row[2] else "NULL"
        print(f"   Table {row[0]}: status='{row[1]}', currentGuestId={guest_id}")
    
    conn.close()

if __name__ == "__main__":
    main()
