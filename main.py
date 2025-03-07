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
        
        # Get current game state
        game_state = cursor.execute('SELECT current_turn, current_player, game_over FROM game_state WHERE id = 1').fetchone()
        current_turn = game_state['current_turn']
        current_player = game_state['current_player']
        game_over = game_state['game_over']
        
        # Make sure the turn exists
        cursor.execute('SELECT 1 FROM turns WHERE turn_number = ?', (turn_number,))
        if not cursor.fetchone():
            cursor.execute('INSERT INTO turns (turn_number) VALUES (?)', (turn_number,))
        
        # Check if this is a current turn override or past turn modification
        is_current_turn_override = (turn_number == current_turn and player_id == current_player and not game_over)
        
        # Different handling based on whether this is for the current turn or a past turn
        if is_current_turn_override:
            # This is the current player's current turn
            # Update the throw in current_throws
            cursor.execute(
                'UPDATE current_throws SET score = ?, multiplier = ?, points = ? WHERE throw_number = ?',
                (score, multiplier, points, throw_number)
            )
            
            # Calculate total points for current throws
            cursor.execute('SELECT SUM(points) as total_points FROM current_throws')
            total_current_points = cursor.fetchone()['total_points'] or 0
            
            # Check if there's an existing score for this turn/player
            cursor.execute(
                'SELECT 1 FROM turn_scores WHERE turn_number = ? AND player_id = ?',
                (turn_number, player_id)
            )
            
            if cursor.fetchone():
                # Get current throw details
                cursor.execute(
                    '''SELECT 
                        throw_number, score, multiplier, points 
                    FROM current_throws 
                    ORDER BY throw_number'''
                )
                throw_details = cursor.fetchall()
                
                # Update existing score with all throw details
                cursor.execute(
                    '''UPDATE turn_scores 
                    SET points = ?,
                        throw1 = ?, throw1_multiplier = ?, throw1_points = ?,
                        throw2 = ?, throw2_multiplier = ?, throw2_points = ?,
                        throw3 = ?, throw3_multiplier = ?, throw3_points = ?
                    WHERE turn_number = ? AND player_id = ?''',
                    (
                        total_current_points,
                        throw_details[0]['score'], throw_details[0]['multiplier'], throw_details[0]['points'],
                        throw_details[1]['score'], throw_details[1]['multiplier'], throw_details[1]['points'],
                        throw_details[2]['score'], throw_details[2]['multiplier'], throw_details[2]['points'],
                        turn_number, player_id
                    )
                )
            else:
                # Get current throw details
                cursor.execute(
                    '''SELECT 
                        throw_number, score, multiplier, points 
                    FROM current_throws 
                    ORDER BY throw_number'''
                )
                throw_details = cursor.fetchall()
                
                # Insert new score entry with all throw details
                cursor.execute(
                    '''INSERT INTO turn_scores (
                        turn_number, player_id, points,
                        throw1, throw1_multiplier, throw1_points,
                        throw2, throw2_multiplier, throw2_points,
                        throw3, throw3_multiplier, throw3_points
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        turn_number, player_id, total_current_points,
                        throw_details[0]['score'], throw_details[0]['multiplier'], throw_details[0]['points'],
                        throw_details[1]['score'], throw_details[1]['multiplier'], throw_details[1]['points'],
                        throw_details[2]['score'], throw_details[2]['multiplier'], throw_details[2]['points'],
                        
                    )
                )
                
            # Check if we need to advance to the next turn/player
            if throw_number == 3:
                # If we're manually entering the 3rd throw, advance to the next player
                player_count = cursor.execute('SELECT COUNT(*) as count FROM players').fetchone()['count']
                
                # Calculate next player and turn
                next_player = current_player % player_count + 1  # Cycle to next player (1-based)
                next_turn = current_turn + (1 if next_player == 1 else 0)  # Increment turn if we wrapped around
                
                # Update game state
                cursor.execute(
                    'UPDATE game_state SET current_player = ?, current_turn = ? WHERE id = 1',
                    (next_player, next_turn)
                )
                
                # Reset current throws
                cursor.execute('UPDATE current_throws SET points = 0, score = 0, multiplier = 0')
                
                print(f"Manual override: Advanced to Player {next_player}, Turn {next_turn}")
                
        else:
            # This is a past turn or different player
            # Get existing turn data
            cursor.execute(
                '''SELECT 
                    throw1, throw1_multiplier, throw1_points,
                    throw2, throw2_multiplier, throw2_points,
                    throw3, throw3_multiplier, throw3_points,
                    points
                FROM turn_scores 
                WHERE turn_number = ? AND player_id = ?''',
                (turn_number, player_id)
            )
            
            row = cursor.fetchone()
            
            if row:
                # Update the specific throw while keeping other throws the same
                throw_column = f'throw{throw_number}'
                multiplier_column = f'throw{throw_number}_multiplier'
                points_column = f'throw{throw_number}_points'
                
                # Calculate new total points
                old_throw_points = row[points_column]
                new_total_points = row['points'] - old_throw_points + points
                
                # Update query with specific throw fields
                update_query = f'''
                UPDATE turn_scores 
                SET {throw_column} = ?, 
                    {multiplier_column} = ?, 
                    {points_column} = ?,
                    points = ?
                WHERE turn_number = ? AND player_id = ?
                '''
                
                cursor.execute(
                    update_query,
                    (score, multiplier, points, new_total_points, turn_number, player_id)
                )
            else:
                # Create a new record with just this throw
                throw1 = 0
                throw1_multiplier = 0
                throw1_points = 0
                throw2 = 0
                throw2_multiplier = 0
                throw2_points = 0
                throw3 = 0
                throw3_multiplier = 0
                throw3_points = 0
                
                # Set the appropriate throw values
                if throw_number == 1:
                    throw1 = score
                    throw1_multiplier = multiplier
                    throw1_points = points
                elif throw_number == 2:
                    throw2 = score
                    throw2_multiplier = multiplier
                    throw2_points = points
                elif throw_number == 3:
                    throw3 = score
                    throw3_multiplier = multiplier
                    throw3_points = points
                
                cursor.execute(
                    '''INSERT INTO turn_scores (
                        turn_number, player_id, points,
                        throw1, throw1_multiplier, throw1_points,
                        throw2, throw2_multiplier, throw2_points,
                        throw3, throw3_multiplier, throw3_points
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        turn_number, player_id, points,
                        throw1, throw1_multiplier, throw1_points,
                        throw2, throw2_multiplier, throw2_points,
                        throw3, throw3_multiplier, throw3_points
                    )
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
        
        # Return success response with additional info for UI update
        response_data = {
            'message': f'Throw updated successfully! Points: {points}',
            'points': points,
            'new_total': new_score
        }
        
        # Add info about turn advancement if applicable
        if is_current_turn_override and throw_number == 3:
            response_data['advanced_turn'] = True
            response_data['next_player'] = current_player % cursor.execute('SELECT COUNT(*) FROM players').fetchone()[0] + 1
        
        return jsonify(response_data)
        
    except Exception as e:
        # Log the error
        print(f"Error updating throw: {e}")
        
        # Return error response
        return jsonify({'error': str(e)}), 500
    

@app.route('/get_throw_details', methods=['GET'])
def get_throw_details():
    """Get details of individual throws for a specific turn and player"""
    try:
        turn_number = request.args.get('turn_number')
        player_id = request.args.get('player_id')
        
        if not turn_number or not player_id:
            return jsonify({'error': 'Missing turn number or player ID'}), 400
            
        # Parse as integers
        turn_number = int(turn_number)
        player_id = int(player_id)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if this is the current turn for the current player
        cursor.execute('SELECT current_turn, current_player FROM game_state WHERE id = 1')
        game_state = cursor.fetchone()
        is_current = (turn_number == game_state['current_turn'] and player_id == game_state['current_player'])
        
        throws = []
        
        if is_current:
            # For current turn, get data from current_throws
            cursor.execute('SELECT throw_number, score, multiplier, points FROM current_throws ORDER BY throw_number')
            throws = [dict(row) for row in cursor.fetchall()]
        else:
            # For past turns, get from turn_scores
            cursor.execute('''
                SELECT 
                    throw1 as score1, throw1_multiplier as multiplier1, throw1_points as points1,
                    throw2 as score2, throw2_multiplier as multiplier2, throw2_points as points2,
                    throw3 as score3, throw3_multiplier as multiplier3, throw3_points as points3
                FROM turn_scores 
                WHERE turn_number = ? AND player_id = ?
            ''', (turn_number, player_id))
            
            row = cursor.fetchone()
            
            if row:
                # Convert row data to throw objects
                throws = [
                    {"throw_number": 1, "score": row['score1'], "multiplier": row['multiplier1'], "points": row['points1']},
                    {"throw_number": 2, "score": row['score2'], "multiplier": row['multiplier2'], "points": row['points2']},
                    {"throw_number": 3, "score": row['score3'], "multiplier": row['multiplier3'], "points": row['points3']}
                ]
            else:
                # No data found, return empty throws
                throws = [
                    {"throw_number": 1, "score": 0, "multiplier": 0, "points": 0},
                    {"throw_number": 2, "score": 0, "multiplier": 0, "points": 0},
                    {"throw_number": 3, "score": 0, "multiplier": 0, "points": 0}
                ]
        
        conn.close()
        return jsonify(throws)
        
    except Exception as e:
        print(f"Error getting throw details: {e}")
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