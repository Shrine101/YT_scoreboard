import sqlite3

# Create a new SQLite database
conn = sqlite3.connect('game.db')
cursor = conn.cursor()

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

# Insert sample data matching your current game_data
# Players
cursor.executemany('INSERT INTO players (id, name, total_score) VALUES (?, ?, ?)', [
    (1, 'Player 1', 190),
    (2, 'Player 2', 275),
    (3, 'Player 3', 305),
    (4, 'Player 4', 350)
])

# Turns
cursor.executemany('INSERT INTO turns (turn_number) VALUES (?)', [(1,), (2,)])

# Turn scores
turn_scores = [
    (1, 1, 180), (1, 2, 140), (1, 3, 120), (1, 4, 100),
    (2, 1, 140), (2, 2, 95), (2, 3, 85), (2, 4, 60)
]
cursor.executemany('INSERT INTO turn_scores (turn_number, player_id, points) VALUES (?, ?, ?)', turn_scores)

# Game state
cursor.execute('INSERT INTO game_state (id, current_turn, current_player) VALUES (1, 2, 4)')

# Current throws
current_throws = [(1, 10), (2, 30), (3, 20)]
cursor.executemany('INSERT INTO current_throws (throw_number, points) VALUES (?, ?)', current_throws)

# Commit changes and close connection
conn.commit()
conn.close()

print("Database created successfully!")