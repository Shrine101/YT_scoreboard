"""
dart_processor_around_the_clock.py

This is a dart processor for the Around the Clock game mode.
In this game, players must hit numbers in sequence from 1 to 20,
followed by bullseye to win.
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
        
        # Initialize timestamp to current local time
        self.last_throw_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"Around The Clock dart processor initialized. Only processing throws after: {self.last_throw_timestamp}")
        
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

    def set_animation_state(self, animation_type, turn_number, player_id, throw_number, next_turn=None, next_player=None, target_hit=False):
        """
        Set the animation state in the database
        
        Args:
            animation_type: Type of animation ('third_throw', 'win', etc.)
            turn_number: Current turn number
            player_id: Current player ID
            throw_number: Throw number (1-3)
            next_turn: Next turn number if advancing
            next_player: Next player ID if advancing
            target_hit: Whether this throw hit the player's target (for Around the Clock)
        """
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # First add a column to the animation_state table if it doesn't exist yet
            try:
                cursor.execute("SELECT target_hit FROM animation_state LIMIT 1")
            except sqlite3.OperationalError:
                # Column doesn't exist, add it
                cursor.execute("ALTER TABLE animation_state ADD COLUMN target_hit INTEGER DEFAULT 0")
            
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
                    target_hit = ?
                WHERE id = 1
            ''', (animation_type, turn_number, player_id, throw_number, current_time, next_turn, next_player, 1 if target_hit else 0))
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

    def get_player_progress(self, player_id):
        """Get a player's current progress in the Around the Clock game"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT current_number, completed FROM around_clock_progress WHERE player_id = ?',
                (player_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return {
                    'current_number': row['current_number'],
                    'completed': row['completed'] == 1
                }
            else:
                # Default to starting at number 1, not completed
                return {
                    'current_number': 1,
                    'completed': False
                }
    
    def update_player_progress(self, player_id, current_number, completed=False):
        """Update a player's progress in the Around the Clock game"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE around_clock_progress
                SET current_number = ?, completed = ?, last_update = ?
                WHERE player_id = ?
            ''', (current_number, 1 if completed else 0, current_time, player_id))
            
            # Update player's total_score to reflect current_number - 1
            # This makes the UI display current_number as the target
            cursor.execute('UPDATE players SET total_score = ? WHERE id = ?', 
                        (current_number - 1, player_id))
            
            conn.commit()
    
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
            # MODIFIED: Set score and multiplier to NULL instead of 0
            cursor.execute('UPDATE current_throws SET points = 0, score = NULL, multiplier = NULL')
            
            conn.commit()
            
            print(f"Advanced to Player {next_player}, Turn {next_turn}")
            return next_player, next_turn

    def check_for_winner(self):
        """Check if any player has completed the game (hit all numbers and bullseye)"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # Find players who have completed all numbers
            cursor.execute('SELECT player_id FROM around_clock_progress WHERE completed = 1')
            winners = cursor.fetchall()
            
            if winners:
                # Get the first winner (if there are multiple, take the first one)
                winner_id = winners[0]['player_id']
                
                # Get the winner's name
                cursor.execute('SELECT name FROM players WHERE id = ?', (winner_id,))
                winner_name = cursor.fetchone()['name']
                
                # Set game_over flag
                cursor.execute('UPDATE game_state SET game_over = 1 WHERE id = 1')
                conn.commit()
                
                print(f"Player {winner_name} (ID: {winner_id}) has won the game!")
                return winner_id
            
            return None

    def save_throw_details_to_turn_scores(self, turn_number, player_id, current_throws):
        """Store throw details in the turn_scores table for animation handling"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # Make sure the turn exists
            cursor.execute('SELECT 1 FROM turns WHERE turn_number = ?', (turn_number,))
            if not cursor.fetchone():
                cursor.execute('INSERT INTO turns (turn_number) VALUES (?)', (turn_number,))
            
            # Get player's current target for this turn
            player_progress = self.get_player_progress(player_id)
            current_target = player_progress['current_number']
            
            # Map throws to their respective columns
            throw_columns = {}
            for throw in current_throws:
                throw_num = throw['throw_number']
                throw_columns[f'throw{throw_num}'] = throw['score']
                throw_columns[f'throw{throw_num}_multiplier'] = throw['multiplier']
                throw_columns[f'throw{throw_num}_points'] = throw['points']
            
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
                        current_target,  # For Around the Clock, points represent the current target
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
                        turn_number, player_id, current_target,  # For Around the Clock, points represent the current target
                        throw_columns.get('throw1', 0), throw_columns.get('throw1_multiplier', 0), throw_columns.get('throw1_points', 0),
                        throw_columns.get('throw2', 0), throw_columns.get('throw2_multiplier', 0), throw_columns.get('throw2_points', 0),
                        throw_columns.get('throw3', 0), throw_columns.get('throw3_multiplier', 0), throw_columns.get('throw3_points', 0)
                    )
                )
            
            conn.commit()
            
            print(f"Saved throw details to turn_scores for player {player_id}, turn {turn_number}")

    def process_throw(self, throw):
        """Process a single throw for Around the Clock game mode"""
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
        # MODIFIED: Check for NULL score instead of points == 0
        throw_position = 1
        for t in current_throws:
            if t['score'] is None:
                throw_position = t['throw_number']
                break
        
        # Write to LEDs database
        self.add_throw_to_leds_db(score, multiplier, position_x, position_y)
        
        # Update the current throw with score, multiplier, and points
        self.update_current_throw(throw_position, score, multiplier, points)
        
        # Update the last throw record
        self.update_last_throw(score, multiplier, points, current_player)
        
        # Get player's current progress
        player_progress = self.get_player_progress(current_player)
        current_number = player_progress['current_number']
        completed = player_progress['completed']
        
        # Check if this throw hit the player's current target number
        hit_target = False
        if not completed:
            if current_number <= 20:
                # Regular number (1-20)
                hit_target = (score == current_number)
            else:
                # Bullseye (current_number = 21)
                hit_target = (score == 25)  # 25 is bullseye
        
        # If player hit their target, advance to next number
        if hit_target:
            print(f"Player {current_player} hit their target: {score}")
            
            if current_number == 20:
                # After 20, they need bullseye
                current_number = 21  # Use 21 to represent bullseye
                self.update_player_progress(current_player, current_number)
                print(f"Player {current_player} advanced to bullseye")
            elif current_number == 21:
                # They hit bullseye - they've won!
                self.update_player_progress(current_player, current_number, completed=True)
                print(f"Player {current_player} hit bullseye and completed the game!")
                
                # Set game over
                with self.get_game_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('UPDATE game_state SET game_over = 1 WHERE id = 1')
                    conn.commit()
                
                # Set the animation state for a win
                self.set_animation_state(
                    animation_type="win",
                    turn_number=current_turn,
                    player_id=current_player,
                    throw_number=throw_position,
                    next_turn=None,
                    next_player=None
                )
                return
            else:
                # Advance to next number
                current_number += 1
                self.update_player_progress(current_player, current_number)
                print(f"Player {current_player} advanced to number {current_number}")
            
            # Set target hit animation without advancing turn
            if throw_position < 3:  # Only if not the third throw
                self.set_animation_state(
                    animation_type="target_hit",
                    turn_number=current_turn,
                    player_id=current_player,
                    throw_number=throw_position,
                    next_turn=None,
                    next_player=None
                )
        
        # Process game logic when player has used their three throws
        if throw_position == 3:
            # CRITICAL FIX: Explicitly refresh current_throws to include the latest throw
            refreshed_current_throws = []
            with self.get_game_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT throw_number, points, score, multiplier FROM current_throws ORDER BY throw_number')
                refreshed_current_throws = [dict(t) for t in cursor.fetchall()]
            
            # Save throw details to turn_scores for third throw animation
            self.save_throw_details_to_turn_scores(current_turn, current_player, refreshed_current_throws)
            
            # KEY FIX: Always use third_throw animation type for third throws, regardless of target hit
            animation_type = "third_throw"
            print(f"{animation_type.upper()} detected! Processing game logic...")
            
            # Calculate next player and turn
            with self.get_game_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) as count FROM players')
                player_count = cursor.fetchone()['count']
            
            next_player = current_player % player_count + 1  # Cycle to next player (1-based)
            next_turn = current_turn + (1 if next_player == 1 else 0)  # Increment turn if we wrapped around
            
            # Get player's current progress to record
            player_progress = self.get_player_progress(current_player)
            current_target = player_progress['current_number']
            
            # Record the player's current target
            self.record_player_target(current_turn, current_player, current_target)
            
            # Set animation state BEFORE advancing game state
            # IMPORTANT: Pass the hit_target flag to allow the frontend to show target hit notification
            self.set_animation_state(
                animation_type=animation_type,
                turn_number=current_turn,
                player_id=current_player,
                throw_number=throw_position,
                next_turn=next_turn,
                next_player=next_player,
                target_hit=hit_target
            )
            
            # Advance to next player
            self.advance_to_next_player()
            
            print(f"Game state advanced. Animation state set for: {animation_type}")
        else:
            # If not a third throw, continue with normal play
            print(f"Processed throw: {score}x{multiplier}={points} points "
                f"(Player {current_player}, Turn {current_turn}, Throw {throw_position})")

    def run(self):
        """Main processing loop"""
        print("Around The Clock dart processor running, press Ctrl+C to stop...")
        
        try:
            while True:
                # Check if we need to clear any expired animations
                self.check_and_clear_animations()
                
                # Get new throws from CV database
                new_throws = self.get_new_throws()
                
                # Process each new throw
                for throw in new_throws:
                    self.process_throw(throw)
                    
                # Sleep for a bit before next poll
                time.sleep(self.poll_interval)
                
        except KeyboardInterrupt:
            print("\nAround The Clock dart processor stopped.")

    def record_player_target(self, turn_number, player_id, target_number):
        """
        Record a player's current target number in the turn_scores table.
        This allows displaying progress history in the UI.
        """
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # Check if this turn exists
            cursor.execute('SELECT 1 FROM turns WHERE turn_number = ?', (turn_number,))
            if not cursor.fetchone():
                cursor.execute('INSERT INTO turns (turn_number) VALUES (?)', (turn_number,))
            
            # Check if player already has a score for this turn
            cursor.execute(
                'SELECT 1 FROM turn_scores WHERE turn_number = ? AND player_id = ?',
                (turn_number, player_id)
            )
            
            if cursor.fetchone():
                # Update existing record
                cursor.execute(
                    'UPDATE turn_scores SET points = ? WHERE turn_number = ? AND player_id = ?',
                    (target_number, turn_number, player_id)
                )
            else:
                # Insert new record
                cursor.execute(
                    'INSERT INTO turn_scores (turn_number, player_id, points) VALUES (?, ?, ?)',
                    (turn_number, player_id, target_number)
                )
            
            conn.commit()

def main():
    processor = DartProcessor()
    processor.run()

if __name__ == "__main__":
    main()