import sqlite3

def add_guests_directly():
    conn = sqlite3.connect('qtable.db')
    cursor = conn.cursor()
    
    # Create the guests if they don't exist
    guests = [
        ('63067C72-D36A-4261-B4B2-921BEBAF33DF', 'John', 'Doe', 'john.doe@example.com', '+1234567890', 'Birthday celebration', 0),
        ('3D66189F-C51D-405A-8E47-D3962DE78121', 'Jane', 'Smith', 'jane.smith@example.com', '+1987654321', 'Anniversary dinner', 0)
    ]
    
    for guest in guests:
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO guests (id, first_name, last_name, email, phone, notes, total_visits, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            ''', guest)
            print(f"✅ Added guest: {guest[1]} {guest[2]} ({guest[0]})")
        except Exception as e:
            print(f"❌ Error adding guest {guest[1]} {guest[2]}: {e}")
    
    conn.commit()
    conn.close()
    print("✅ Guest data added successfully!")

if __name__ == "__main__":
    add_guests_directly()
