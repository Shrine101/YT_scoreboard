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
                    FOREIGN KEY (current_turn) REFERENCES turns(turn_number),
                    FOREIGN KEY (current_player) REFERENCES players(id)
                )
                ''')

                cursor.execute('''
                CREATE TABLE current_throws (
                    throw_number INTEGER PRIMARY KEY,
                    points INTEGER NOT NULL
                )
                ''')
                
                print("Tables created successfully.")
            
            # Insert initial data
            print("Inserting initial data...")
            
            # Insert players
            cursor.executemany('INSERT INTO players (id, name, total_score) VALUES (?, ?, ?)', [
                (1, 'Player 1', 301),
                (2, 'Player 2', 301),
                (3, 'Player 3', 301),
                (4, 'Player 4', 301)
            ])
            
            # Insert first turn
            cursor.execute('INSERT INTO turns (turn_number) VALUES (?)', (1,))
            
            # Insert game state
            cursor.execute('INSERT INTO game_state (id, current_turn, current_player) VALUES (1, 1, 1)')
            
            # Insert current throws
            cursor.executemany('INSERT INTO current_throws (throw_number, points) VALUES (?, ?)', [
                (1, 0),
                (2, 0),
                (3, 0)
            ])
            
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