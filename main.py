from flask import Flask
from flask import render_template, jsonify
import sqlite3

app = Flask(__name__)

def get_db_connection():
    """Create a connection to the SQLite database"""
    conn = sqlite3.connect('game.db')
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn

@app.route('/data_json')
def data_json():
    # Create a connection to the database
    conn = get_db_connection()
    
    # Build game_data dictionary from database queries
    game_data = {}
    
    # Get players
    players = []
    for row in conn.execute('SELECT id, name, total_score FROM players ORDER BY id'):
        players.append({
            "id": row['id'],
            "name": row['name'],
            "total_score": row['total_score']
        })
    game_data["players"] = players
    
    # Get turns and scores
    turns = []
    for turn_row in conn.execute('SELECT turn_number FROM turns ORDER BY turn_number'):
        turn_number = turn_row['turn_number']
        
        # Get scores for this turn
        scores = []
        for score_row in conn.execute('SELECT player_id, points FROM turn_scores WHERE turn_number = ? ORDER BY player_id', (turn_number,)):
            scores.append({
                "player_id": score_row['player_id'],
                "points": score_row['points']
            })
        
        turns.append({
            "turn_number": turn_number,
            "scores": scores
        })
    game_data["turns"] = turns
    
    # Get current game state
    state_row = conn.execute('SELECT current_turn, current_player FROM game_state WHERE id = 1').fetchone()
    game_data["current_turn"] = state_row['current_turn']
    game_data["current_player"] = state_row['current_player']
    
    # Get current throws
    current_throws = []
    for throw_row in conn.execute('SELECT throw_number, points FROM current_throws ORDER BY throw_number'):
        current_throws.append({
            "throw_number": throw_row['throw_number'],
            "points": throw_row['points']
        })
    game_data["current_throws"] = current_throws
    
    # Close the connection
    conn.close()
    
    return jsonify(game_data)
    

@app.route('/')
def index():
    game_data = data_json()

    return render_template(
        'index.html',
        game_data = game_data.json
        
    )