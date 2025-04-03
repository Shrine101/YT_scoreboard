import sqlite3
import os

def initialize_leds_database():
    """Initialize the LEDs database by creating necessary tables."""
    print("Initializing LEDs database...")
    
    # Check if database file already exists and remove it if it exists
    if os.path.exists('LEDs.db'):
        os.remove('LEDs.db')
        print("Deleted existing LEDs.db file")
    
    # Connect to the database (creates it if it doesn't exist)
    conn = sqlite3.connect('LEDs.db')
    cursor = conn.cursor()
    
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
    
    # Create cricket_state table to track cricket game state
    cursor.execute('''
    CREATE TABLE cricket_state (
        segment INTEGER PRIMARY KEY,  -- 15-20 and 25 for bullseye
        player1_closed BOOLEAN DEFAULT 0,
        player2_closed BOOLEAN DEFAULT 0,
        player3_closed BOOLEAN DEFAULT 0,
        player4_closed BOOLEAN DEFAULT 0,
        player5_closed BOOLEAN DEFAULT 0,
        player6_closed BOOLEAN DEFAULT 0,
        player7_closed BOOLEAN DEFAULT 0,
        player8_closed BOOLEAN DEFAULT 0,
        all_closed BOOLEAN DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Create player_state table to track current player
    cursor.execute('''
    CREATE TABLE player_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        current_player INTEGER DEFAULT 1,
        player_count INTEGER DEFAULT 4,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Insert default game mode (neutral)
    cursor.execute('''
    INSERT INTO game_mode (id, mode, updated_at)
    VALUES (1, 'neutral', CURRENT_TIMESTAMP)
    ''')
    
    # Insert default player state
    cursor.execute('''
    INSERT INTO player_state (id, current_player, player_count)
    VALUES (1, 1, 4)
    ''')
    
    # Insert default cricket segments
    for segment in [15, 16, 17, 18, 19, 20, 25]:
        cursor.execute('''
        INSERT INTO cricket_state (segment, all_closed, updated_at)
        VALUES (?, 0, CURRENT_TIMESTAMP)
        ''', (segment,))
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    
    print("LEDs database initialization complete!")

if __name__ == "__main__":
    initialize_leds_database()