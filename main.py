from flask import Flask, render_template, jsonify, request
import sqlite3
import subprocess
import threading
import os
import signal 
import atexit
from initialize_db import initialize_database

app = Flask(__name__)
dart_processor = None  # Define the global variable

def start_dart_processor():
    """Start the dart processor as a separate process"""
    global dart_processor
    print("Starting dart processor...")
    dart_processor = subprocess.Popen(['python', 'dart_processor.py'])
    print(f"Dart processor started with PID {dart_processor.pid}")

def stop_dart_processor():
    """Clean up dart processor when app shuts down"""
    global dart_processor
    if dart_processor is not None:
        print(f"Stopping dart processor (PID {dart_processor.pid})...")
        try:
            # Try to terminate gracefully first
            dart_processor.terminate()
            dart_processor.wait(timeout=3)  # Wait up to 3 seconds for termination
        except subprocess.TimeoutExpired:
            # Force kill if it doesn't terminate within timeout
            print("Dart processor didn't terminate, forcing kill...")
            dart_processor.kill()
        print("Dart processor stopped")

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
    state_row = conn.execute('SELECT current_turn, current_player, game_over FROM game_state WHERE id = 1').fetchone()
    game_data["current_turn"] = state_row['current_turn']
    game_data["current_player"] = state_row['current_player']
    game_data["game_over"] = state_row['game_over']
    
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

@app.route('/update_throw', methods=['POST'])
def update_throw():
    """Update a specific throw for a player in a turn"""
    try:
        # Get the data from the request
        data = request.json
        turn_number = data.get('turn_number')
        player_id = data.get('player_id')
        throw_number = data.get('throw_number')
        score = data.get('score')
        multiplier = data.get('multiplier')
        
        # Validate inputs
        if not all([turn_number, player_id, throw_number, score, multiplier]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Calculate points
        points = score * multiplier
        
        # Get connection to database
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Different handling based on whether this is for the current turn or a past turn
        game_state = cursor.execute('SELECT current_turn, current_player FROM game_state WHERE id = 1').fetchone()
        current_turn = game_state['current_turn']
        current_player = game_state['current_player']
        
        if turn_number == current_turn and player_id == current_player:
            # This is the current player's current turn
            # Update the throw in current_throws
            cursor.execute(
                'UPDATE current_throws SET points = ? WHERE throw_number = ?',
                (points, throw_number)
            )
            
            # Get all current throws to calculate total
            cursor.execute('SELECT SUM(points) as total_points FROM current_throws')
            total_current_points = cursor.fetchone()['total_points'] or 0
            
            # Check if there's an existing score for this turn/player
            cursor.execute(
                'SELECT points FROM turn_scores WHERE turn_number = ? AND player_id = ?',
                (turn_number, player_id)
            )
            existing_score = cursor.fetchone()
            
            if existing_score:
                # Update existing score
                cursor.execute(
                    'UPDATE turn_scores SET points = ? WHERE turn_number = ? AND player_id = ?',
                    (total_current_points, turn_number, player_id)
                )
            else:
                # Create new score entry
                cursor.execute(
                    'INSERT INTO turn_scores (turn_number, player_id, points) VALUES (?, ?, ?)',
                    (turn_number, player_id, total_current_points)
                )
                
        else:
            # This is a past turn or different player
            # For past turns, we need a different approach since we don't store individual throws
            
            # First, retrieve any existing turn data
            cursor.execute(
                'SELECT points FROM turn_scores WHERE turn_number = ? AND player_id = ?',
                (turn_number, player_id)
            )
            existing_turn = cursor.fetchone()
            
            # If this is a completely new turn entry, just insert the points for one throw
            if not existing_turn:
                # Make sure the turn exists in the turns table
                cursor.execute('SELECT 1 FROM turns WHERE turn_number = ?', (turn_number,))
                if not cursor.fetchone():
                    cursor.execute('INSERT INTO turns (turn_number) VALUES (?)', (turn_number,))
                
                # Insert the new score with just this throw's points
                cursor.execute(
                    'INSERT INTO turn_scores (turn_number, player_id, points) VALUES (?, ?, ?)',
                    (turn_number, player_id, points)
                )
            else:
                # We need to retrieve the old throw value and replace it with the new one
                
                # First, get the current total points for this turn
                current_total = existing_turn['points']
                
                # We need to determine what portion of the total to replace
                # Get all three throw values from temporary storage or from the user
                
                # For this implementation, we'll temporarily store individual throw values 
                # in a new table called throw_details
                
                # Check if we already have throw details for this turn/player
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS throw_details (
                        turn_number INTEGER,
                        player_id INTEGER,
                        throw_number INTEGER,
                        points INTEGER,
                        PRIMARY KEY (turn_number, player_id, throw_number)
                    )
                ''')
                
                # Check if this specific throw already exists in our details table
                cursor.execute(
                    'SELECT points FROM throw_details WHERE turn_number = ? AND player_id = ? AND throw_number = ?',
                    (turn_number, player_id, throw_number)
                )
                existing_throw = cursor.fetchone()
                
                if existing_throw:
                    # Calculate the adjustment to the total
                    old_points = existing_throw['points']
                    point_difference = points - old_points
                    
                    # Update the total score with the difference
                    new_total = current_total + point_difference
                    
                    # Update the throw details
                    cursor.execute(
                        'UPDATE throw_details SET points = ? WHERE turn_number = ? AND player_id = ? AND throw_number = ?',
                        (points, turn_number, player_id, throw_number)
                    )
                    
                    # Update the turn_scores with the new total
                    cursor.execute(
                        'UPDATE turn_scores SET points = ? WHERE turn_number = ? AND player_id = ?',
                        (new_total, turn_number, player_id)
                    )
                else:
                    # We don't have details for this throw yet
                    # Need to determine if we have other throws for this turn
                    cursor.execute(
                        'SELECT COUNT(*) as count FROM throw_details WHERE turn_number = ? AND player_id = ?',
                        (turn_number, player_id)
                    )
                    throw_count = cursor.fetchone()['count']
                    
                    if throw_count == 0:
                        # First throw we're tracking for this turn
                        # Create entries for all three throws
                        # Estimate points per throw (divide total by 3)
                        points_per_throw = current_total // 3
                        
                        # Insert all three with default values
                        for t in range(1, 4):
                            default_points = points if t == int(throw_number) else points_per_throw
                            cursor.execute(
                                'INSERT INTO throw_details (turn_number, player_id, throw_number, points) VALUES (?, ?, ?, ?)',
                                (turn_number, player_id, t, default_points)
                            )
                        
                        # Calculate new total (replacing one of the thirds with the actual score)
                        new_total = current_total - points_per_throw + points
                        
                        # Update the turn_scores with the new total
                        cursor.execute(
                            'UPDATE turn_scores SET points = ? WHERE turn_number = ? AND player_id = ?',
                            (new_total, turn_number, player_id)
                        )
                    else:
                        # We have some throws but not this one
                        # Insert this throw
                        cursor.execute(
                            'INSERT INTO throw_details (turn_number, player_id, throw_number, points) VALUES (?, ?, ?, ?)',
                            (turn_number, player_id, throw_number, points)
                        )
                        
                        # Get sum of all throws we know about
                        cursor.execute(
                            'SELECT SUM(points) as known_total FROM throw_details WHERE turn_number = ? AND player_id = ?',
                            (turn_number, player_id)
                        )
                        known_total = cursor.fetchone()['known_total']
                        
                        # Update the turn_scores with the new total
                        cursor.execute(
                            'UPDATE turn_scores SET points = ? WHERE turn_number = ? AND player_id = ?',
                            (known_total, turn_number, player_id)
                        )
        
        # Recalculate player's total score (301 - sum of all points)
        cursor.execute(
            'SELECT SUM(points) as total_points FROM turn_scores WHERE player_id = ?',
            (player_id,)
        )
        total_points = cursor.fetchone()['total_points'] or 0
        
        # Update the player's total score
        new_score = 301 - total_points
        cursor.execute(
            'UPDATE players SET total_score = ? WHERE id = ?',
            (new_score, player_id)
        )
        
        # Check if player has won (score exactly 0)
        if new_score == 0:
            cursor.execute('UPDATE game_state SET game_over = 1 WHERE id = 1')
        
        # Commit changes
        conn.commit()
        
        # Close connection
        conn.close()
        
        return jsonify({
            'message': f'Throw updated successfully! Points: {points}',
            'points': points,
            'new_total': new_score
        })
        
    except Exception as e:
        # Log the error
        print(f"Error updating throw: {e}")
        
        # Return error response
        return jsonify({'error': str(e)}), 500
    

@app.route('/')
def index():
    response = data_json()
    # Fix: get the actual JSON data from the response
    game_data = response.get_json()

    return render_template(
        'index.html',
        game_data = game_data
    )

if __name__ == '__main__':
    try:
        # Initialize database before starting the app
        initialize_database()
        
        # Start the dart processor when the app starts
        start_dart_processor()
        
        # Run the Flask app
        app.run(debug=False)
    finally:
        # Make sure to clean up the dart processor when the app exits
        stop_dart_processor()