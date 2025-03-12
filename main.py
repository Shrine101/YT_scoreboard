from flask import Flask, render_template, jsonify, request
import sqlite3
import subprocess
import threading
import os
import signal 
import atexit
from initialize_db import initialize_database
from datetime import datetime

app = Flask(__name__)
dart_processor = None  # Define the global variable
ANIMATION_DURATION = 3.0  # Animation duration in seconds

def start_dart_processor():
    """Start the dart processor as a separate process"""
    global dart_processor
    print("Starting dart processor...")
    dart_processor = subprocess.Popen(['./YT_boardvenv/bin/python3', 'dart_processor.py'])
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

def get_player_score_before_turn(conn, player_id, turn_number):
    """Get a player's score before a specific turn"""
    cursor = conn.cursor()
    
    # Get the total points scored by this player before this turn (excluding busted turns)
    cursor.execute(
        'SELECT SUM(points) as total_points FROM turn_scores WHERE player_id = ? AND turn_number < ? AND bust = 0',
        (player_id, turn_number)
    )
    
    total_previous_points = cursor.fetchone()['total_points'] or 0
    
    # Calculate the score before this turn (301 - previous points)
    score_before_turn = 301 - total_previous_points
    
    return score_before_turn

def get_animation_state(conn):
    """Get the current animation state"""
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM animation_state WHERE id = 1')
    state = cursor.fetchone()
    
    # Check if animation is active and not expired
    if state and state['animating'] == 1 and state['timestamp']:
        # Check if animation has expired
        animation_time = datetime.strptime(state['timestamp'], '%Y-%m-%d %H:%M:%S')
        current_time = datetime.now()
        elapsed_seconds = (current_time - animation_time).total_seconds()
        
        if elapsed_seconds < ANIMATION_DURATION:
            # Animation is still active
            return dict(state)  # Convert from sqlite Row to dict
    
    # No active animation or expired
    return None

def reset_animation_state(conn):
    """Reset the animation state in the database"""
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE animation_state 
        SET animating = 0, 
            animation_type = NULL, 
            turn_number = NULL, 
            player_id = NULL, 
            throw_number = NULL, 
            timestamp = NULL,
            next_turn = NULL,
            next_player = NULL
        WHERE id = 1
    ''')
    conn.commit()

def recalculate_player_scores(conn):
    """Recalculate all player scores based on turn_scores data"""
    cursor = conn.cursor()
    
    # Get all players
    cursor.execute('SELECT id FROM players')
    players = cursor.fetchall()
    
    for player in players:
        player_id = player['id']
        
        # Calculate total points from non-busted turns only
        cursor.execute(
            'SELECT SUM(points) as total_points FROM turn_scores WHERE player_id = ? AND bust = 0',
            (player_id,)
        )
        total_points = cursor.fetchone()['total_points'] or 0
        
        # Update player's score (301 - total points)
        new_score = 301 - total_points
        cursor.execute(
            'UPDATE players SET total_score = ? WHERE id = ?',
            (new_score, player_id)
        )
        
        # Check if player has won (score exactly 0)
        if new_score == 0:
            cursor.execute('UPDATE game_state SET game_over = 1 WHERE id = 1')

@app.route('/data_json')
def data_json():
    # Create a connection to the database
    conn = get_db_connection()
    
    # Get current animation state (if any)
    animation_state = get_animation_state(conn)
    
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
    
    # Get current game state
    state_row = conn.execute('SELECT current_turn, current_player, game_over FROM game_state WHERE id = 1').fetchone()
    
    # Handle animation state for UI - modify the returned game state if animating
    if animation_state and animation_state['animating'] == 1:
        animation_type = animation_state['animation_type']
        
        if animation_type in ['bust', 'third_throw']:
            # For third throw animations, we want to show the throw but not advance player yet
            anim_turn = animation_state['turn_number']
            anim_player = animation_state['player_id']
            
            # Update game_data to reflect animation state
            game_data["animating"] = True
            game_data["animation_type"] = animation_type
            
            # During animation, we show the current player still (not advanced yet)
            game_data["current_turn"] = anim_turn
            game_data["current_player"] = anim_player
            
            # Also include the next player/turn info for UI transitions
            game_data["next_turn"] = animation_state['next_turn']
            game_data["next_player"] = animation_state['next_player']
        else:
            # No special animation handling needed
            game_data["current_turn"] = state_row['current_turn']
            game_data["current_player"] = state_row['current_player']
    else:
        # Normal state (no animation)
        game_data["current_turn"] = state_row['current_turn']
        game_data["current_player"] = state_row['current_player']
    
    # Always pass along game over state
    game_data["game_over"] = state_row['game_over']
    
    # Get current throws - Special handling for animation state
    current_throws = []
    
    if animation_state and animation_state['animating'] == 1 and animation_state['animation_type'] == 'third_throw':
        # IMPORTANT: For third throw animation, we need to get the throw data from turn_scores
        # This ensures the third throw is visible during animation
        anim_turn = animation_state['turn_number']
        anim_player = animation_state['player_id']
        
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                throw1, throw1_multiplier, throw1_points,
                throw2, throw2_multiplier, throw2_points,
                throw3, throw3_multiplier, throw3_points
            FROM turn_scores
            WHERE turn_number = ? AND player_id = ?
        ''', (anim_turn, anim_player))
        
        row = cursor.fetchone()
        if row:
            # Create throw objects from turn_scores data
            current_throws = [
                {"throw_number": 1, "score": row['throw1'], "multiplier": row['throw1_multiplier'], "points": row['throw1_points']},
                {"throw_number": 2, "score": row['throw2'], "multiplier": row['throw2_multiplier'], "points": row['throw2_points']},
                {"throw_number": 3, "score": row['throw3'], "multiplier": row['throw3_multiplier'], "points": row['throw3_points']}
            ]
        else:
            # Fall back to current_throws if no turn_scores data
            for throw_row in conn.execute('SELECT throw_number, points, score, multiplier FROM current_throws ORDER BY throw_number'):
                current_throws.append({
                    "throw_number": throw_row['throw_number'],
                    "points": throw_row['points'],
                    "score": throw_row['score'],
                    "multiplier": throw_row['multiplier']
                })
    else:
        # Normal case - just get current_throws
        for throw_row in conn.execute('SELECT throw_number, points, score, multiplier FROM current_throws ORDER BY throw_number'):
            current_throws.append({
                "throw_number": throw_row['throw_number'],
                "points": throw_row['points'],
                "score": throw_row['score'],
                "multiplier": throw_row['multiplier']
            })
    
    game_data["current_throws"] = current_throws
    
    # Get turns and scores
    turns = []
    for turn_row in conn.execute('SELECT turn_number FROM turns ORDER BY turn_number'):
        turn_number = turn_row['turn_number']
        
        # Get scores for this turn
        scores = []
        for score_row in conn.execute('SELECT player_id, points, bust FROM turn_scores WHERE turn_number = ? ORDER BY player_id', (turn_number,)):
            scores.append({
                "player_id": score_row['player_id'],
                "points": score_row['points'],
                "bust": score_row['bust']
            })
        
        turns.append({
            "turn_number": turn_number,
            "scores": scores
        })
    game_data["turns"] = turns
    
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
        
        # First, clear any active animations since we're manually overriding
        reset_animation_state(conn)
        
        # Make sure the turn exists
        cursor.execute('SELECT 1 FROM turns WHERE turn_number = ?', (turn_number,))
        if not cursor.fetchone():
            cursor.execute('INSERT INTO turns (turn_number) VALUES (?)', (turn_number,))
        
        # Check if this is a current turn override or past turn modification
        is_current_turn_override = (turn_number == current_turn and player_id == current_player and not game_over)
        
        # Store original bust status if modifying existing turn
        was_previously_bust = False
        score_before_turn = get_player_score_before_turn(conn, player_id, turn_number)
        
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
                'SELECT bust FROM turn_scores WHERE turn_number = ? AND player_id = ?',
                (turn_number, player_id)
            )
            existing_score = cursor.fetchone()
            
            if existing_score:
                was_previously_bust = existing_score['bust']
                
                # Get current throw details
                cursor.execute(
                    '''SELECT 
                        throw_number, score, multiplier, points 
                    FROM current_throws 
                    ORDER BY throw_number'''
                )
                throw_details = cursor.fetchall()
                
                # Check if this would result in a bust
                new_score = score_before_turn - total_current_points
                is_bust = (new_score < 0)
                
                # If it's a bust, the points for the turn should be 0
                points_to_record = 0 if is_bust else total_current_points
                
                # Update existing score with all throw details
                cursor.execute(
                    '''UPDATE turn_scores 
                    SET points = ?,
                        throw1 = ?, throw1_multiplier = ?, throw1_points = ?,
                        throw2 = ?, throw2_multiplier = ?, throw2_points = ?,
                        throw3 = ?, throw3_multiplier = ?, throw3_points = ?,
                        bust = ?
                    WHERE turn_number = ? AND player_id = ?''',
                    (
                        points_to_record,  # 0 if bust, otherwise the actual points
                        throw_details[0]['score'], throw_details[0]['multiplier'], throw_details[0]['points'],
                        throw_details[1]['score'], throw_details[1]['multiplier'], throw_details[1]['points'],
                        throw_details[2]['score'], throw_details[2]['multiplier'], throw_details[2]['points'],
                        1 if is_bust else 0,
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
                
                # Check if this would result in a bust
                new_score = score_before_turn - total_current_points
                is_bust = (new_score < 0)
                
                # If it's a bust, the points for the turn should be 0
                points_to_record = 0 if is_bust else total_current_points
                
                # Insert new score entry with all throw details
                cursor.execute(
                    '''INSERT INTO turn_scores (
                        turn_number, player_id, points,
                        throw1, throw1_multiplier, throw1_points,
                        throw2, throw2_multiplier, throw2_points,
                        throw3, throw3_multiplier, throw3_points,
                        bust
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        turn_number, player_id, points_to_record,  # 0 if bust, otherwise the actual points
                        throw_details[0]['score'], throw_details[0]['multiplier'], throw_details[0]['points'],
                        throw_details[1]['score'], throw_details[1]['multiplier'], throw_details[1]['points'],
                        throw_details[2]['score'], throw_details[2]['multiplier'], throw_details[2]['points'],
                        1 if is_bust else 0
                    )
                )
                
            # Handle bust status change
            bust_status_changed = (was_previously_bust != is_bust)
            
            # Handle "rewind" if a bust is corrected and it wasn't the third throw
            if bust_status_changed and was_previously_bust and not is_bust and throw_number < 3:
                # We corrected a bust, and it's not the third throw, so player can continue their turn
                
                # We don't need to change anything - player is already the current player
                # Just indicate in the response that the turn should continue
                continue_turn = True
                
                print(f"Bust corrected via manual override! Player {player_id} can continue their turn.")
            else:
                continue_turn = False
                
                # Check if we need to advance to the next turn/player
                should_advance = False
                
                if is_bust:
                    # If it's a bust, always advance IMMEDIATELY regardless of throw number
                    should_advance = True
                    print(f"Bust detected via manual override! Immediately advancing to next player.")
                elif throw_number == 3:
                    # If it's the third throw and not a bust, advance
                    should_advance = True
                    print(f"Third throw via manual override. Advancing to next player.")
                
                if should_advance:
                    # Calculate next player and turn
                    player_count = cursor.execute('SELECT COUNT(*) as count FROM players').fetchone()['count']
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
            # Get existing turn data and check if it was previously a bust
            cursor.execute(
                'SELECT bust, throw1_points, throw2_points, throw3_points FROM turn_scores WHERE turn_number = ? AND player_id = ?',
                (turn_number, player_id)
            )
            existing_turn = cursor.fetchone()
            if existing_turn:
                was_previously_bust = existing_turn['bust']
            
            # Get existing turn data
            cursor.execute(
                '''SELECT 
                    throw1, throw1_multiplier, throw1_points,
                    throw2, throw2_multiplier, throw2_points,
                    throw3, throw3_multiplier, throw3_points,
                    points, bust
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
                
                # Calculate the new total points directly from all throws
                # First, get current throw details
                throw1_points = row['throw1_points']
                throw2_points = row['throw2_points']
                throw3_points = row['throw3_points']
                
                # Replace the specified throw with new points
                if throw_number == 1:
                    new_total_points = points + throw2_points + throw3_points
                elif throw_number == 2:
                    new_total_points = throw1_points + points + throw3_points
                else:  # throw_number == 3
                    new_total_points = throw1_points + throw2_points + points
                
                # Check if this update would cause a bust
                new_score = score_before_turn - new_total_points
                is_bust = (new_score < 0)
                
                # If busted, set recorded points to 0, otherwise use the calculated sum
                points_to_record = 0 if is_bust else new_total_points
                
                # Update query with specific throw fields
                update_query = f'''
                UPDATE turn_scores 
                SET {throw_column} = ?, 
                    {multiplier_column} = ?, 
                    {points_column} = ?,
                    points = ?,
                    bust = ?
                WHERE turn_number = ? AND player_id = ?
                '''
                
                cursor.execute(
                    update_query,
                    (score, multiplier, points, points_to_record, 1 if is_bust else 0, turn_number, player_id)
                )
                
                # Special handling for correcting a past bust
                if was_previously_bust and not is_bust:
                    print(f"Corrected bust for player {player_id}, turn {turn_number}")
                    
                    # If this wasn't the third throw, and it's the previous turn, we might need to "rewind"
                    # Check if this is the turn right before the current turn
                    if (throw_number < 3 and 
                        ((turn_number == current_turn - 1) or 
                         (turn_number == current_turn and player_id < current_player))):
                        
                        print(f"This was a recent bust correction. Allowing player {player_id} to continue their turn.")
                        
                        # We need to rewind the game state to allow this player to continue their turn
                        cursor.execute(
                            'UPDATE game_state SET current_turn = ?, current_player = ? WHERE id = 1',
                            (turn_number, player_id)
                        )
                        
                        # Re-query the database to get the UPDATED throw data
                        cursor.execute(
                            '''SELECT 
                                throw1, throw1_multiplier, throw1_points,
                                throw2, throw2_multiplier, throw2_points,
                                throw3, throw3_multiplier, throw3_points
                            FROM turn_scores 
                            WHERE turn_number = ? AND player_id = ?''',
                            (turn_number, player_id)
                        )
                        updated_row = cursor.fetchone()
                        
                        # Update current_throws to reflect the UPDATED throws
                        cursor.execute('DELETE FROM current_throws')
                        cursor.execute('INSERT INTO current_throws (throw_number, points, score, multiplier) VALUES (1, ?, ?, ?)', 
                                      (updated_row['throw1_points'], updated_row['throw1'], updated_row['throw1_multiplier']))
                        cursor.execute('INSERT INTO current_throws (throw_number, points, score, multiplier) VALUES (2, ?, ?, ?)', 
                                      (updated_row['throw2_points'], updated_row['throw2'], updated_row['throw2_multiplier']))
                        cursor.execute('INSERT INTO current_throws (throw_number, points, score, multiplier) VALUES (3, ?, ?, ?)', 
                                      (updated_row['throw3_points'], updated_row['throw3'], updated_row['throw3_multiplier']))
                        
                        # Set response flag to indicate turn was rewound
                        rewound_turn = True
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
                
                # Check if this would result in a bust
                new_score = score_before_turn - points
                is_bust = (new_score < 0)
                
                # Set points to 0 if busted
                points_to_record = 0 if is_bust else points
                
                cursor.execute(
                    '''INSERT INTO turn_scores (
                        turn_number, player_id, points,
                        throw1, throw1_multiplier, throw1_points,
                        throw2, throw2_multiplier, throw2_points,
                        throw3, throw3_multiplier, throw3_points,
                        bust
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        turn_number, player_id, points_to_record,
                        throw1, throw1_multiplier, throw1_points,
                        throw2, throw2_multiplier, throw2_points,
                        throw3, throw3_multiplier, throw3_points,
                        1 if is_bust else 0
                    )
                )
            
            # Recalculate all player scores after modifying past turn
            recalculate_player_scores(conn)
        
        # Commit changes
        conn.commit()
        
        # Check for game over after all updates
        cursor.execute('SELECT total_score FROM players WHERE id = ?', (player_id,))
        player_score = cursor.fetchone()['total_score']
        
        # Check if player has won (score exactly 0)
        if player_score == 0:
            cursor.execute('UPDATE game_state SET game_over = 1 WHERE id = 1')
            conn.commit()
        
        # Close connection
        conn.close()
        
        # Return success response with additional info for UI update
        response_data = {
            'message': f'Throw updated successfully! Points: {points}',
            'points': points,
            'new_total': player_score,
            'is_bust': is_bust,
            'was_previously_bust': was_previously_bust,
            'bust_status_changed': (was_previously_bust != is_bust)
        }
        
        # Add info about turn advancement if applicable
        if is_current_turn_override:
            if is_bust or throw_number == 3:
                response_data['advanced_turn'] = True
                response_data['next_player'] = (current_player % cursor.execute('SELECT COUNT(*) FROM players').fetchone()[0]) + 1
            elif 'continue_turn' in locals() and continue_turn:
                response_data['continue_turn'] = True
        elif 'rewound_turn' in locals() and rewound_turn:
            # This is for correcting a previous player's bust
            response_data['rewound_turn'] = True
            response_data['current_turn'] = turn_number
            response_data['current_player'] = player_id
        
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
        bust = 0
        
        if is_current:
            # For current turn, get data from current_throws
            cursor.execute('SELECT throw_number, score, multiplier, points FROM current_throws ORDER BY throw_number')
            throws = [dict(row) for row in cursor.fetchall()]
            
            # Check if there's a bust for the current turn/player
            cursor.execute(
                'SELECT bust FROM turn_scores WHERE turn_number = ? AND player_id = ?',
                (turn_number, player_id)
            )
            row = cursor.fetchone()
            if row:
                bust = row['bust']
        else:
            # For past turns, get from turn_scores
            cursor.execute('''
                SELECT 
                    throw1 as score1, throw1_multiplier as multiplier1, throw1_points as points1,
                    throw2 as score2, throw2_multiplier as multiplier2, throw2_points as points2,
                    throw3 as score3, throw3_multiplier as multiplier3, throw3_points as points3,
                    bust
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
                bust = row['bust']
            else:
                # No data found, return empty throws
                throws = [
                    {"throw_number": 1, "score": 0, "multiplier": 0, "points": 0},
                    {"throw_number": 2, "score": 0, "multiplier": 0, "points": 0},
                    {"throw_number": 3, "score": 0, "multiplier": 0, "points": 0}
                ]
        
        conn.close()
        
        response = {
            'throws': throws,
            'bust': bust
        }
        
        return jsonify(response)
        
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