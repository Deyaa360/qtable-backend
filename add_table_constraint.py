#!/usr/bin/env python3
"""
Add database constraint to prevent future data corruption
"""

import sqlite3

def main():
    conn = sqlite3.connect('qtable.db')
    cursor = conn.cursor()
    
    print("🔧 Adding database constraint to prevent future corruption...")
    
    try:
        # Note: SQLite doesn't support adding CHECK constraints to existing tables
        # So we'll create a trigger instead to enforce the business rule
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS enforce_table_guest_consistency
            BEFORE UPDATE OF status, current_guest_id ON restaurant_tables
            FOR EACH ROW
            WHEN (
                (NEW.status != 'occupied' AND NEW.current_guest_id IS NOT NULL) OR
                (NEW.status = 'occupied' AND NEW.current_guest_id IS NULL)
            )
            BEGIN
                SELECT RAISE(ABORT, 'Business rule violation: Only occupied tables can have currentGuestId');
            END;
        """)
        
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS enforce_table_guest_consistency_insert
            BEFORE INSERT ON restaurant_tables
            FOR EACH ROW
            WHEN (
                (NEW.status != 'occupied' AND NEW.current_guest_id IS NOT NULL) OR
                (NEW.status = 'occupied' AND NEW.current_guest_id IS NULL)
            )
            BEGIN
                SELECT RAISE(ABORT, 'Business rule violation: Only occupied tables can have currentGuestId');
            END;
        """)
        
        conn.commit()
        print("✅ Database triggers created successfully!")
        
        # Test the constraint
        print("\n🧪 Testing constraint...")
        try:
            cursor.execute("UPDATE restaurant_tables SET current_guest_id = 'test-guest' WHERE table_number = '1' AND status = 'available'")
            print("❌ Constraint failed to prevent invalid data!")
        except sqlite3.Error as e:
            print(f"✅ Constraint working: {e}")
            
    except sqlite3.Error as e:
        print(f"❌ Error creating constraint: {e}")
    
    conn.close()

if __name__ == "__main__":
    main()
