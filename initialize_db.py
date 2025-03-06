import sqlite3
import os

def initialize_database():
    """Initialize the game database by dropping existing tables and creating new ones."""
    print("Initializing database...")
    
    # Check if the database file exists and remove it
    if os.path.exists('game.db'):
        print("Removing existing database...")
        os.remove('game.db')
        print("Database file removed.")
    
    # Create a new connection
    conn = sqlite3.connect('game.db')
    cursor = conn.cursor()
    
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
        (1, 'Player 1', 0),
        (2, 'Player 2', 0),
        (3, 'Player 3', 0),
        (4, 'Player 4', 0)
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

if __name__ == "__main__":
    initialize_database()