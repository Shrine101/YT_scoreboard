"""
dart_processor_american_cricket.py

This is a dart processor for the American Cricket game mode.
In this game, players aim to hit numbers 15-20 and bullseye,
marking each three times to "close" it. Points are scored on
open numbers until everyone has closed them.
"""

import sqlite3
import time
from datetime import datetime
from contextlib import contextmanager

class DartProcessor:
    def __init__(self, cv_db_path='simulation/cv_data.db', game_db_path='game.db', 
                 leds_db_path='leds/LEDs.db', poll_interval=1.0, animation_duration=3.0):
        self.cv_db_path = cv_db_path
        self.game_db_path = game_db_path
        self.leds_db_path = leds_db_path
        self.poll_interval = poll_interval
        self.animation_duration = animation_duration
        
        # Cricket game specific settings
        self.cricket_numbers = [15, 16, 17, 18, 19, 20, 25]  # 25 is bullseye
        
        # Initialize timestamp to current local time
        self.last_throw_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Add pending player change tracking
        self.pending_player_change = None
        
        print(f"American Cricket dart processor initialized. Only processing throws after: {self.last_throw_timestamp}")
        
        # Reset any lingering animation state
        self.reset_animation_state()

    @contextmanager
    def get_cv_connection(self):
        """Get a connection to the CV database"""
        conn = sqlite3.connect(self.cv_db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def get_game_connection(self):
        """Get a connection to the game database"""
        conn = sqlite3.connect(self.game_db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
            
    @contextmanager
    def get_leds_connection(self):
        """Get a connection to the LEDs database"""
        conn = sqlite3.connect(self.leds_db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def reset_animation_state(self):
        """Reset the animation state in the database"""
        with self.get_game_connection() as conn:
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

    def set_animation_state(self, animation_type, turn_number, player_id, throw_number, next_turn=None, next_player=None, cricket_event=None):
        """
        Set the animation state in the database
        
        Args:
            animation_type: Type of animation ('third_throw', 'win', etc.)
            turn_number: Current turn number
            player_id: Current player ID
            throw_number: Throw number (1-3)
            next_turn: Next turn number if advancing
            next_player: Next player ID if advancing
            cricket_event: Type of cricket event ('cricket_closed', 'cricket_marks', 'cricket_points')
        """
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # First add a column to the animation_state table if it doesn't exist yet
            try:
                cursor.execute("SELECT cricket_event FROM animation_state LIMIT 1")
            except sqlite3.OperationalError:
                # Column doesn't exist, add it
                cursor.execute("ALTER TABLE animation_state ADD COLUMN cricket_event TEXT DEFAULT NULL")
            
            cursor.execute('''
                UPDATE animation_state 
                SET animating = 1, 
                    animation_type = ?, 
                    turn_number = ?, 
                    player_id = ?, 
                    throw_number = ?, 
                    timestamp = ?,
                    next_turn = ?,
                    next_player = ?,
                    cricket_event = ?
                WHERE id = 1
            ''', (animation_type, turn_number, player_id, throw_number, current_time, next_turn, next_player, cricket_event))
            conn.commit()

    def check_and_clear_animations(self):
        """Check if any animations have expired and clear them"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT animating, timestamp FROM animation_state WHERE id = 1')
            animation_state = cursor.fetchone()
            
            if animation_state and animation_state['animating']:
                # Check if animation has expired
                animation_time = datetime.strptime(animation_state['timestamp'], '%Y-%m-%d %H:%M:%S')
                current_time = datetime.now()
                elapsed_seconds = (current_time - animation_time).total_seconds()
                
                if elapsed_seconds >= self.animation_duration:
                    print("Animation completed. Clearing animation state.")
                    self.reset_animation_state()
                    return True  # Animation was cleared
            
            return False  # No animation or not cleared

    def get_new_throws(self):
        """Get new throws from CV database that are newer than last_throw_timestamp"""
        with self.get_cv_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM throws WHERE timestamp > ? ORDER BY timestamp ASC',
                (self.last_throw_timestamp,)
            )
            return cursor.fetchall()

    def get_current_game_state(self):
        """Get the current game state from game database"""
        with self.get_game_connection() as conn:
            # Get current turn, player, and game_over flag
            cursor = conn.cursor()
            cursor.execute('SELECT current_turn, current_player, game_over FROM game_state WHERE id = 1')
            state = cursor.fetchone()
            
            # Get current throws
            cursor.execute('SELECT throw_number, points, score, multiplier FROM current_throws ORDER BY throw_number')
            throws = [dict(throw) for throw in cursor.fetchall()]
            
            return {
                'current_turn': state['current_turn'],
                'current_player': state['current_player'],
                'game_over': state['game_over'],
                'current_throws': throws
            }

    def get_cricket_scores(self):
        """Get all cricket scores for all players"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT cs.player_id, cs.number, cs.marks, cs.points, cs.closed, p.name
                FROM cricket_scores cs
                JOIN players p ON cs.player_id = p.id
                ORDER BY cs.player_id, cs.number
            ''')
            
            # Organize by player
            scores_by_player = {}
            for row in cursor.fetchall():
                player_id = row['player_id']
                if player_id not in scores_by_player:
                    scores_by_player[player_id] = {
                        'name': row['name'],
                        'scores': {},
                        'total_points': 0,
                        'closed_count': 0
                    }
                
                # Add the number's details
                scores_by_player[player_id]['scores'][row['number']] = {
                    'marks': row['marks'],
                    'points': row['points'],
                    'closed': row['closed'] == 1
                }
                
                # Update total points and closed count
                scores_by_player[player_id]['total_points'] += row['points']
                if row['closed'] == 1:
                    scores_by_player[player_id]['closed_count'] += 1
            
            return scores_by_player

    def is_number_open_for_player(self, number, player_id):
        """Check if a number is open for a player to score points on"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # A number is open if the player hasn't closed it yet (marks < 3)
            cursor.execute('''
                SELECT marks FROM cricket_scores
                WHERE player_id = ? AND number = ?
            ''', (player_id, number))
            
            row = cursor.fetchone()
            if row:
                return row['marks'] < 3
            return False  # Default to closed if number not found

    def is_number_closed_by_all(self, number):
        """Check if a number has been closed by all players"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # First count all active players
            cursor.execute('SELECT COUNT(*) as player_count FROM players')
            player_count = cursor.fetchone()['player_count']
            
            # Then count players who have closed this number
            cursor.execute('''
                SELECT COUNT(*) as closed_count FROM cricket_scores
                WHERE number = ? AND closed = 1
            ''', (number,))
            
            closed_count = cursor.fetchone()['closed_count']
            
            # Number is closed by all if the counts match
            return closed_count >= player_count

    def update_cricket_score(self, player_id, number, marks_to_add, score_to_add=0):
        """Update a player's cricket score for a specific number"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # Get current marks and closed status
            cursor.execute('''
                SELECT marks, closed, points FROM cricket_scores
                WHERE player_id = ? AND number = ?
            ''', (player_id, number))
            
            row = cursor.fetchone()
            if row:
                current_marks = row['marks']
                current_closed = row['closed'] == 1
                current_points = row['points']
                
                # Calculate new marks, ensuring we don't exceed 3
                new_marks = min(current_marks + marks_to_add, 3)
                
                # Update closed status if marks reached 3
                new_closed = 1 if new_marks >= 3 else 0
                
                # Update points
                new_points = current_points + score_to_add
                
                # Update the record
                cursor.execute('''
                    UPDATE cricket_scores
                    SET marks = ?, closed = ?, points = ?
                    WHERE player_id = ? AND number = ?
                ''', (new_marks, new_closed, new_points, player_id, number))
                
                # If this was newly closed, check if all players have closed it
                newly_closed = new_closed == 1 and current_closed == False
                
                # Calculate marks actually added (for logging)
                marks_added = new_marks - current_marks
                
                # Update player's total score in players table
                self.update_player_total_score(conn, player_id)
                
                conn.commit()
                
                return {
                    'new_marks': new_marks,
                    'marks_added': marks_added,
                    'new_closed': new_closed == 1,
                    'newly_closed': newly_closed,
                    'new_points': new_points,
                    'points_added': score_to_add
                }
            else:
                print(f"Error: No cricket score record found for player {player_id}, number {number}")
                return None

    def update_player_total_score(self, conn, player_id):
        """Update a player's total score in the players table based on cricket scores"""
        cursor = conn.cursor()
        
        # Sum all points from cricket_scores
        cursor.execute('''
            SELECT SUM(points) as total_points FROM cricket_scores
            WHERE player_id = ?
        ''', (player_id,))
        
        row = cursor.fetchone()
        if row:
            total_points = row['total_points'] or 0
            
            # Update the players table
            cursor.execute('''
                UPDATE players
                SET total_score = ?
                WHERE id = ?
            ''', (total_points, player_id))

    def update_current_throw(self, throw_number, score, multiplier, points):
        """Update a specific throw in the current_throws table with score, multiplier and points"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE current_throws SET score = ?, multiplier = ?, points = ? WHERE throw_number = ?',
                (score, multiplier, points, throw_number)
            )
            conn.commit()

    def update_last_throw(self, score, multiplier, points, player_id):
        """Update the last throw table with the most recent throw"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE last_throw
                SET score = ?, multiplier = ?, points = ?, player_id = ?
                WHERE id = 1
            ''', (score, multiplier, points, player_id))
            conn.commit()

    def add_throw_to_leds_db(self, score, multiplier, position_x, position_y):
        """Add a throw to the LEDs database with the appropriate segment type"""
        # Determine segment type based on multiplier and position
        segment_type = None
        
        if score == 25:
            segment_type = "bullseye"
        elif multiplier == 2:
            segment_type = "double"
        elif multiplier == 3:
            segment_type = "triple"
        elif multiplier == 1:
            # Inner vs outer single determination based on r value
            # Note: position_x is actually r in polar coordinates
            r = position_x
            if r < 103:
                segment_type = "inner_single"
            else:
                segment_type = "outer_single"
        
        if segment_type:
            # Add to LEDs database
            with self.get_leds_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO dart_events (score, multiplier, segment_type, processed, timestamp)
                    VALUES (?, ?, ?, 0, CURRENT_TIMESTAMP)
                ''', (score, multiplier, segment_type))
                conn.commit()
                print(f"Added throw to LEDs database: Score={score}, Multiplier={multiplier}, Segment={segment_type}")
        else:
            print(f"WARNING: Could not determine segment type for throw: Score={score}, Multiplier={multiplier}")

    def advance_to_next_player(self):
        """Move to the next player, and possibly next turn"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # Get current state and player count
            cursor.execute('SELECT current_turn, current_player, game_over FROM game_state WHERE id = 1')
            state = cursor.fetchone()
            
            # If game is over, don't advance
            if state['game_over']:
                print("Game is over, not advancing to next player")
                return None, None
            
            # Get player count from the players table
            cursor.execute('SELECT COUNT(*) as count FROM players')
            player_count = cursor.fetchone()['count']
            
            if player_count == 0:
                print("No players found in database, cannot advance")
                return None, None
            
            # Calculate next player and turn
            current_player = state['current_player']
            current_turn = state['current_turn']
            
            next_player = current_player % player_count + 1  # Cycle to next player (1-based)
            next_turn = current_turn + (1 if next_player == 1 else 0)  # Increment turn if we wrapped around
            
            # Update game state
            cursor.execute(
                'UPDATE game_state SET current_player = ?, current_turn = ? WHERE id = 1',
                (next_player, next_turn)
            )
            
            # Reset current throws
            cursor.execute('UPDATE current_throws SET points = 0, score = 0, multiplier = 0')
            
            conn.commit()
            
            print(f"Advanced to Player {next_player}, Turn {next_turn}")
            
            # Store this player change as pending for LEDs.db
            # Check if there's an active animation
            cursor.execute('SELECT animating FROM animation_state WHERE id = 1')
            animation_state = cursor.fetchone()
            if animation_state and animation_state['animating'] == 1:
                # Store as pending change
                self.pending_player_change = next_player
                print(f"Animation in progress - storing pending player change: {next_player}")
            else:
                # No animation, apply immediately
                self.pending_player_change = None
                
            return next_player, next_turn

    def check_for_winner(self):
        """Check if a player has won the game (closed all numbers and has highest or tied score)"""
        cricket_scores = self.get_cricket_scores()
        potential_winners = []
        highest_score = -1
        highest_score_players = []
        
        # Find players who have closed all numbers
        for player_id, player_data in cricket_scores.items():
            # If player has closed all numbers (7 numbers in cricket)
            if player_data['closed_count'] == len(self.cricket_numbers):
                potential_winners.append(player_id)
            
            # Track highest score
            if player_data['total_points'] > highest_score:
                highest_score = player_data['total_points']
                highest_score_players = [player_id]
            elif player_data['total_points'] == highest_score:
                highest_score_players.append(player_id)
        
        # If any player has closed all numbers
        if potential_winners:
            # If player with all closed numbers also has highest score
            for winner_id in potential_winners:
                if winner_id in highest_score_players:
                    # This player wins
                    with self.get_game_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('UPDATE game_state SET game_over = 1 WHERE id = 1')
                        conn.commit()
                    
                    # Get the winner's name
                    player_name = cricket_scores[winner_id]['name']
                    print(f"Player {player_name} (ID: {winner_id}) has won the game by closing all numbers with highest score!")
                    return winner_id
        
        # No winner yet
        return None

    def save_throw_details_to_turn_scores(self, turn_number, player_id, current_throws):
        """Store throw details in the turn_scores table for animation handling"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # Make sure the turn exists
            cursor.execute('SELECT 1 FROM turns WHERE turn_number = ?', (turn_number,))
            if not cursor.fetchone():
                cursor.execute('INSERT INTO turns (turn_number) VALUES (?)', (turn_number,))
            
            # Map throws to their respective columns
            throw_columns = {}
            for throw in current_throws:
                throw_num = throw['throw_number']
                throw_columns[f'throw{throw_num}'] = throw['score']
                throw_columns[f'throw{throw_num}_multiplier'] = throw['multiplier']
                throw_columns[f'throw{throw_num}_points'] = throw['points']
            
            # Calculate total points for these throws
            total_points = sum(throw['points'] for throw in current_throws)
            
            # Check if player already has a score for this turn
            cursor.execute(
                'SELECT points FROM turn_scores WHERE turn_number = ? AND player_id = ?',
                (turn_number, player_id)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing score with individual throw details
                update_query = '''
                UPDATE turn_scores 
                SET points = ?, 
                    throw1 = ?, throw1_multiplier = ?, throw1_points = ?,
                    throw2 = ?, throw2_multiplier = ?, throw2_points = ?,
                    throw3 = ?, throw3_multiplier = ?, throw3_points = ?,
                    bust = 0
                WHERE turn_number = ? AND player_id = ?
                '''
                cursor.execute(
                    update_query,
                    (
                        total_points,
                        throw_columns.get('throw1', 0), throw_columns.get('throw1_multiplier', 0), throw_columns.get('throw1_points', 0),
                        throw_columns.get('throw2', 0), throw_columns.get('throw2_multiplier', 0), throw_columns.get('throw2_points', 0),
                        throw_columns.get('throw3', 0), throw_columns.get('throw3_multiplier', 0), throw_columns.get('throw3_points', 0),
                        turn_number, player_id
                    )
                )
            else:
                # Insert new score with individual throw details
                insert_query = '''
                INSERT INTO turn_scores (
                    turn_number, player_id, points,
                    throw1, throw1_multiplier, throw1_points,
                    throw2, throw2_multiplier, throw2_points,
                    throw3, throw3_multiplier, throw3_points,
                    bust
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                '''
                cursor.execute(
                    insert_query,
                    (
                        turn_number, player_id, total_points,
                        throw_columns.get('throw1', 0), throw_columns.get('throw1_multiplier', 0), throw_columns.get('throw1_points', 0),
                        throw_columns.get('throw2', 0), throw_columns.get('throw2_multiplier', 0), throw_columns.get('throw2_points', 0),
                        throw_columns.get('throw3', 0), throw_columns.get('throw3_multiplier', 0), throw_columns.get('throw3_points', 0)
                    )
                )
            
            conn.commit()
            
            print(f"Saved throw details to turn_scores for player {player_id}, turn {turn_number}")

    def apply_pending_player_change(self):
        """Check if animation has completed and apply any pending player change to LEDs.db."""
        if self.pending_player_change is None:
            return
            
        # Check if animation is still active
        is_animating = False
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT animating FROM animation_state WHERE id = 1')
            animation_state = cursor.fetchone()
            if animation_state and animation_state['animating'] == 1:
                is_animating = True
                
        # If animation has completed, update the LEDs.db with the pending player change
        if not is_animating:
            try:
                with self.get_leds_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE player_state 
                        SET current_player = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = 1
                    """, (self.pending_player_change,))
                    conn.commit()
                    
                print(f"Animation completed - Updated current player in LEDs.db to {self.pending_player_change}")
                
                # Clear the pending player change
                self.pending_player_change = None
            except sqlite3.Error as e:
                print(f"Error applying pending player change to LEDs DB: {e}")
            except Exception as e:
                print(f"Unexpected error applying pending player change: {e}")

    def process_throw(self, throw):
        """Process a single throw for American Cricket game mode"""
        # Calculate points (score * multiplier)
        score = throw['score']
        multiplier = throw['multiplier']
        points = score * multiplier
        
        # Safely access position coordinates from sqlite3.Row
        try:
            position_x = throw['position_x']  # This is actually r in polar coordinates
        except (IndexError, KeyError):
            position_x = 0
            
        try:
            position_y = throw['position_y']  # This is actually theta in polar coordinates
        except (IndexError, KeyError):
            position_y = 0
        
        # Get current game state
        game_state = self.get_current_game_state()
        current_turn = game_state['current_turn']
        current_player = game_state['current_player']
        current_throws = game_state['current_throws']
        game_over = game_state['game_over']
        
        # Always update timestamp to avoid reprocessing this throw
        self.last_throw_timestamp = throw['timestamp']
        
        # Skip processing if the game is over
        if game_over:
            print(f"Game is over. Skipping throw processing: {score}x{multiplier}={points} points")
            return
        
        # Find the next empty throw position (or the first if all are used)
        throw_position = 1
        for t in current_throws:
            if t['points'] == 0:
                throw_position = t['throw_number']
                break
        
        # Write to LEDs database
        self.add_throw_to_leds_db(score, multiplier, position_x, position_y)
        
        # Update the current throw with score, multiplier, and points
        self.update_current_throw(throw_position, score, multiplier, points)
        
        # Update the last throw record
        self.update_last_throw(score, multiplier, points, current_player)
        
        # Process the cricket game logic
        # First, check if this is a cricket number (15-20 or bullseye)
        is_cricket_number = score in self.cricket_numbers
        cricket_event_type = None
        
        if is_cricket_number:
            print(f"Player {current_player} hit cricket number {score} with multiplier {multiplier}")
            
            # Check if this number is closed by all players
            all_closed = self.is_number_closed_by_all(score)
            
            if not all_closed:
                # Get marks to add based on multiplier (1, 2, or 3)
                marks_to_add = multiplier
                
                # Check if player already has this number closed
                player_closed = not self.is_number_open_for_player(score, current_player)
                
                if player_closed:
                    print(f"Player {current_player} already closed number {score}")
                    
                    # Calculate points to add if other players haven't closed this number
                    points_to_add = 0
                    if not all_closed:
                        points_to_add = score * multiplier
                        print(f"Player {current_player} scores {points_to_add} points on {score}")
                    
                    # Update score (marks won't increase since already closed)
                    update_result = self.update_cricket_score(current_player, score, 0, points_to_add)
                    
                    # Sync cricket state to LEDs database after updating scores
                    self.sync_cricket_state_to_leds()
                    
                    if points_to_add > 0:
                        cricket_event_type = "cricket_points"
                else:
                    # Player hasn't closed this number yet
                    # Calculate how many marks can be applied before closing (max 3 total)
                    with self.get_game_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT marks FROM cricket_scores
                            WHERE player_id = ? AND number = ?
                        ''', (current_player, score))
                        
                        row = cursor.fetchone()
                        current_marks = row['marks'] if row else 0
                        
                    marks_to_apply = min(marks_to_add, 3 - current_marks)
                    remaining_marks = marks_to_add - marks_to_apply
                    
                    # Apply the marks first
                    update_result = self.update_cricket_score(current_player, score, marks_to_apply)
                    
                    # Sync cricket state to LEDs database after updating marks
                    self.sync_cricket_state_to_leds()
                    
                    # If there are remaining marks and the number is not closed by all,
                    # those count as points
                    if remaining_marks > 0 and not all_closed:
                        points_to_add = score * remaining_marks
                        print(f"Player {current_player} scores {points_to_add} points on {score} (extra marks)")
                        
                        # Update again to add points
                        update_result = self.update_cricket_score(current_player, score, 0, points_to_add)
                        
                        # Sync cricket state to LEDs database after updating points
                        self.sync_cricket_state_to_leds()
                    
                    if update_result and update_result['newly_closed']:
                        print(f"Player {current_player} closed number {score}!")
                        cricket_event_type = "cricket_closed"
                    else:
                        print(f"Player {current_player} added {marks_to_apply} marks to number {score}")
                        cricket_event_type = "cricket_marks"
            else:
                print(f"Number {score} is already closed by all players. No points scored.")
        else:
            print(f"Player {current_player} hit non-cricket number {score}. No points or marks added.")
        
        # Check if any player has won
        winner_id = self.check_for_winner()
        if winner_id:
            # Set the animation state for a win
            self.set_animation_state(
                animation_type="win",
                turn_number=current_turn,
                player_id=winner_id,
                throw_number=throw_position,
                next_turn=None,
                next_player=None
            )
            
            # Sync cricket state to LEDs database after winner is determined
            self.sync_cricket_state_to_leds()
            return
        
        # Process game logic when player has used their three throws
        if throw_position == 3:
            print(f"Third throw detected! Processing game logic...")
            
            # CRITICAL FIX: Explicitly refresh current_throws to include the latest throw
            refreshed_current_throws = []
            with self.get_game_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT throw_number, points, score, multiplier FROM current_throws ORDER BY throw_number')
                refreshed_current_throws = [dict(t) for t in cursor.fetchall()]
            
            # Save throw details to turn_scores for third throw animation
            self.save_throw_details_to_turn_scores(current_turn, current_player, refreshed_current_throws)
            
            # Calculate next player and turn
            with self.get_game_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) as count FROM players')
                player_count = cursor.fetchone()['count']
            
            next_player = current_player % player_count + 1  # Cycle to next player (1-based)
            next_turn = current_turn + (1 if next_player == 1 else 0)  # Increment turn if we wrapped around
            
            # KEY FIX: Always use third_throw animation type for third throws,
            # but pass the cricket_event_type so the frontend can also show the cricket notification
            animation_type = "third_throw"
            
            # Set animation state BEFORE advancing game state
            self.set_animation_state(
                animation_type=animation_type,
                turn_number=current_turn,
                player_id=current_player,
                throw_number=throw_position,
                next_turn=next_turn,
                next_player=next_player,
                cricket_event=cricket_event_type
            )
            
            # Advance to next player
            self.advance_to_next_player()
            
            # Sync cricket state to LEDs database after advancing to next player
            self.sync_cricket_state_to_leds()
            
            print(f"Game state advanced. Animation state set for: {animation_type}")
        else:
            # If not a third throw, continue with normal play
            # Set appropriate animation type for cricket events if one was determined
            if cricket_event_type:
                self.set_animation_state(
                    animation_type=cricket_event_type,
                    turn_number=current_turn,
                    player_id=current_player,
                    throw_number=throw_position,
                    next_turn=None,
                    next_player=None
                )
            
            print(f"Processed throw: {score}x{multiplier}={points} points "
                f"(Player {current_player}, Turn {current_turn}, Throw {throw_position})")

    def sync_cricket_state_to_leds(self):
        """Sync the cricket state from game.db to LEDs.db for the LED controller."""
        try:
            # First check if there's an active animation
            is_animating = False
            with self.get_game_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT animating FROM animation_state WHERE id = 1')
                animation_state = cursor.fetchone()
                if animation_state and animation_state['animating'] == 1:
                    is_animating = True
            
            # First get the cricket scores from game.db
            cricket_scores = self.get_cricket_scores()
            
            # Get current game state
            game_state = self.get_current_game_state()
            
            # Open connection to LEDs.db
            leds_conn = sqlite3.connect('leds/LEDs.db')
            leds_cursor = leds_conn.cursor()
            
            # Update player_state - BUT ONLY IF NOT ANIMATING or there's no pending player change
            if not is_animating or self.pending_player_change is None:
                leds_cursor.execute("""
                    UPDATE player_state 
                    SET current_player = ?, player_count = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                """, (game_state['current_player'], len(cricket_scores)))
            else:
                # If animating, only update player_count but not current_player
                leds_cursor.execute("""
                    UPDATE player_state 
                    SET player_count = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                """, (len(cricket_scores),))
                print(f"Animation in progress - delaying player update to LEDs.db. Current: {game_state['current_player']}, Pending: {self.pending_player_change}")
            
            # Update cricket state for each segment
            for segment in [15, 16, 17, 18, 19, 20, 25]:  # Cricket segments
                player_closed_values = {}
                all_closed = True
                
                # Check for each player if they've closed this segment
                for player_id, player_data in cricket_scores.items():
                    player_id = int(player_id)  # Convert from string key
                    has_closed = False
                    
                    # Check segment closed status for this player
                    if 'scores' in player_data and segment in player_data['scores']:
                        has_closed = player_data['scores'][segment]['closed']
                    
                    # Update player_closed for this segment
                    player_closed_values[player_id] = has_closed
                    
                    # If any player hasn't closed, it's not all closed
                    if not has_closed:
                        all_closed = False
                
                # Prepare update query with player values
                update_query = """
                    UPDATE cricket_state 
                    SET all_closed = ?, updated_at = CURRENT_TIMESTAMP
                """
                
                # Add player closed values to the query based on how many exist
                params = [1 if all_closed else 0]
                
                # Add each player's closed status up to player count
                for i in range(1, 9):  # Support up to 8 players
                    if i in player_closed_values:
                        update_query += f", player{i}_closed = ?"
                        params.append(1 if player_closed_values[i] else 0)
                    else:
                        update_query += f", player{i}_closed = 0"  # Set to 0 for non-existent players
                
                # Complete the query with WHERE clause
                update_query += " WHERE segment = ?"
                params.append(segment)
                
                # Execute the update
                leds_cursor.execute(update_query, params)
            
            # Update the game mode
            leds_cursor.execute("""
                UPDATE game_mode 
                SET mode = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
            """, ('cricket',))
            
            # Commit and close
            leds_conn.commit()
            leds_conn.close()
            
            print("Cricket state synchronized to LEDs database")
            
        except sqlite3.Error as e:
            print(f"Error syncing cricket state to LEDs DB: {e}")
        except Exception as e:
            print(f"Unexpected error syncing cricket state: {e}")

    def run(self):
        """Main processing loop"""
        print("American Cricket dart processor running, press Ctrl+C to stop...")
        
        try:
            while True:
                # Check if we need to clear any expired animations
                animation_cleared = self.check_and_clear_animations()
                
                # If animation was cleared, also check if there are pending player changes to apply
                if animation_cleared:
                    self.apply_pending_player_change()
                
                # Get new throws from CV database
                new_throws = self.get_new_throws()
                
                # Process each new throw
                for throw in new_throws:
                    self.process_throw(throw)
                
                # Even if no animation was cleared, periodically check for pending player changes
                # This handles cases where we might have missed the animation clearing
                if not animation_cleared:
                    self.apply_pending_player_change()
                    
                # Sleep for a bit before next poll
                time.sleep(self.poll_interval)
                
        except KeyboardInterrupt:
            print("\nAmerican Cricket dart processor stopped.")

def main():
    processor = DartProcessor()
    processor.run()

if __name__ == "__main__":
    main()