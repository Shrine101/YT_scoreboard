import sqlite3
import os
import time

def initialize_database():
    """Initialize the game database by clearing existing tables and inserting new data."""
    print("Initializing database...")
    
    # Try to connect to the database, with retry logic
    max_retries = 5
    for attempt in range(max_retries):
        try:
            # Connect to the database (creates it if it doesn't exist)
            conn = sqlite3.connect('game.db')
            cursor = conn.cursor()
            
            # Check if tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='players'")
            tables_exist = cursor.fetchone() is not None
            
            if tables_exist:
                print("Clearing existing data...")
                # Clear existing data instead of removing the database
                cursor.execute("DELETE FROM turn_scores")
                cursor.execute("DELETE FROM current_throws")
                cursor.execute("DELETE FROM game_state")
                cursor.execute("DELETE FROM turns")
                cursor.execute("DELETE FROM players")
                cursor.execute("DELETE FROM animation_state")  # New table
                cursor.execute("DELETE FROM last_throw")  # Clear the last throw table
            else:
                print("Creating tables...")
                # Create tables
                cursor.execute('''
                CREATE TABLE players (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    total_score INTEGER DEFAULT 0
                )
                ''')

                cursor.execute('''
                CREATE TABLE turns (
                    turn_number INTEGER PRIMARY KEY
                )
                ''')

                cursor.execute('''
                CREATE TABLE turn_scores (
                    turn_number INTEGER,
                    player_id INTEGER,
                    points INTEGER NOT NULL,
                    throw1 INTEGER DEFAULT 0,
                    throw2 INTEGER DEFAULT 0,
                    throw3 INTEGER DEFAULT 0,
                    throw1_multiplier INTEGER DEFAULT 0,
                    throw2_multiplier INTEGER DEFAULT 0,
                    throw3_multiplier INTEGER DEFAULT 0,
                    throw1_points INTEGER DEFAULT 0,
                    throw2_points INTEGER DEFAULT 0,
                    throw3_points INTEGER DEFAULT 0,
                    bust BOOLEAN DEFAULT 0,
                    PRIMARY KEY (turn_number, player_id),
                    FOREIGN KEY (turn_number) REFERENCES turns(turn_number),
                    FOREIGN KEY (player_id) REFERENCES players(id)
                )
                ''')

                cursor.execute('''
                CREATE TABLE game_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    current_turn INTEGER NOT NULL,
                    current_player INTEGER NOT NULL,
                    game_over BOOLEAN NOT NULL DEFAULT 0,
                    FOREIGN KEY (current_turn) REFERENCES turns(turn_number),
                    FOREIGN KEY (current_player) REFERENCES players(id)
                )
                ''')

                cursor.execute('''
                CREATE TABLE current_throws (
                    throw_number INTEGER PRIMARY KEY,
                    points INTEGER NOT NULL,
                    score INTEGER DEFAULT 0,
                    multiplier INTEGER DEFAULT 0
                )
                ''')
                
                # New table for tracking animation state
                cursor.execute('''
                CREATE TABLE animation_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    animating BOOLEAN DEFAULT 0,
                    animation_type TEXT,
                    turn_number INTEGER,
                    player_id INTEGER,
                    throw_number INTEGER,
                    timestamp DATETIME,
                    next_turn INTEGER,
                    next_player INTEGER
                )
                ''')
                
                # New table for tracking the last throw
                cursor.execute('''
                CREATE TABLE last_throw (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    score INTEGER DEFAULT 0,
                    multiplier INTEGER DEFAULT 0,
                    points INTEGER DEFAULT 0,
                    player_id INTEGER
                )
                ''')
                
                print("Tables created successfully.")
            
            # Insert initial data
            print("Inserting initial data...")
            
            # Insert players
            players_to_insert = []
            for i in range(1, 5):  # Default to 4 players initially
                players_to_insert.append((i, f'Player {i}', 301))
            cursor.executemany('INSERT INTO players (id, name, total_score) VALUES (?, ?, ?)', players_to_insert)
            
            # Insert first turn
            cursor.execute('INSERT INTO turns (turn_number) VALUES (?)', (1,))
            
            # Insert game state with game_over set to 0 (false)
            cursor.execute('INSERT INTO game_state (id, current_turn, current_player, game_over) VALUES (1, 1, 1, 0)')
            
            # Insert current throws
            cursor.executemany('INSERT INTO current_throws (throw_number, points, score, multiplier) VALUES (?, ?, ?, ?)', [
                (1, 0, 0, 0),
                (2, 0, 0, 0),
                (3, 0, 0, 0)
            ])
            
            # Insert animation state
            cursor.execute('''
                INSERT INTO animation_state 
                (id, animating, animation_type, turn_number, player_id, throw_number, timestamp, next_turn, next_player) 
                VALUES (1, 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
            ''')
            
            # Insert initial last throw data (empty)
            cursor.execute('''
                INSERT INTO last_throw
                (id, score, multiplier, points, player_id)
                VALUES (1, 0, 0, 0, NULL)
            ''')
            
            # Commit changes and close connection
            conn.commit()
            conn.close()
            
            print("Database initialization complete!")
            return  # Successfully initialized
            
        except sqlite3.OperationalError as e:
            if "disk I/O error" in str(e) or "database is locked" in str(e):
                print(f"Database is busy, retrying... (Attempt {attempt+1}/{max_retries})")
                time.sleep(1)  # Wait a bit before retrying
            else:
                print(f"Error initializing database: {e}")
                raise  # Re-raise the exception if it's not a locking issue
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise

if __name__ == "__main__":
    initialize_database()