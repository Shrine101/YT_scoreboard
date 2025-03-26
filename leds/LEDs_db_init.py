import sqlite3
import os

def initialize_leds_database():
    """Initialize the LEDs database by creating necessary tables."""
    print("Initializing LEDs database...")
    
    # Check if database file already exists
    db_exists = os.path.exists('LEDs.db')
    
    # Connect to the database (creates it if it doesn't exist)
    conn = sqlite3.connect('LEDs.db')
    cursor = conn.cursor()
    
    # If database exists, clear existing data
    if db_exists:
        print("Clearing existing data...")
        cursor.execute("DELETE FROM game_mode")
        cursor.execute("DELETE FROM dart_events")
    else:
        print("Creating tables...")
        # Create game_mode table
        cursor.execute('''
        CREATE TABLE game_mode (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            mode TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create dart_events table
        cursor.execute('''
        CREATE TABLE dart_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            score INTEGER NOT NULL,
            multiplier INTEGER NOT NULL,
            segment_type TEXT NOT NULL,
            processed BOOLEAN DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
    
    # Insert default game mode (classic)
    cursor.execute('''
    INSERT OR REPLACE INTO game_mode (id, mode, updated_at)
    VALUES (1, 'classic', CURRENT_TIMESTAMP)
    ''')
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    
    print("LEDs database initialization complete!")

if __name__ == "__main__":
    initialize_leds_database()