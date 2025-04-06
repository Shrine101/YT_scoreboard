import sqlite3
import os

def initialize_moving_target_database():
    """Initialize the Moving Target database by creating necessary tables."""
    print("Initializing Moving Target database...")
    
    # Define the database path
    db_path = 'leds/moving_target.db'
    
    # Check if database file already exists and remove it if it exists
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Deleted existing {db_path} file")
    
    # Connect to the database (creates it if it doesn't exist)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Creating tables...")
    
    # Create active_segments table to track which segments are currently active
    cursor.execute('''
    CREATE TABLE active_segments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        segment_number INTEGER NOT NULL,   -- Dartboard number (1-20, 25 for bullseye)
        segment_type TEXT NOT NULL,        -- Type of segment (double, triple, inner_single, outer_single, bullseye)
        active BOOLEAN DEFAULT 1,          -- Whether this segment is currently active
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create target_state table to track overall target state
    cursor.execute('''
    CREATE TABLE target_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        current_target INTEGER DEFAULT 20,  -- Current target number (starting with 20)
        move_interval INTEGER DEFAULT 3000, -- Interval in milliseconds to move target (3 seconds)
        last_moved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Insert initial target state (start with 20)
    cursor.execute('''
    INSERT INTO target_state (id, current_target, move_interval, last_moved_at)
    VALUES (1, 20, 3000, CURRENT_TIMESTAMP)
    ''')
    
    # Insert initial active segments (all segments for number 20)
    cursor.execute('''
    INSERT INTO active_segments (segment_number, segment_type)
    VALUES 
        (20, 'double'),
        (20, 'triple'),
        (20, 'inner_single'),
        (20, 'outer_single')
    ''')
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    
    print("Moving Target database initialization complete!")

if __name__ == "__main__":
    initialize_moving_target_database()