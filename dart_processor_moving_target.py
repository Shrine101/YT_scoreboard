"""
dart_processor_moving_target.py

This is a dart processor for the Moving Target game mode.
In this game, a target segment (or group of segments) moves around the dartboard.
Players score a point when they hit the current active target.
The first player to reach 5 points wins.
"""

import sqlite3
import time
from datetime import datetime
from contextlib import contextmanager

class DartProcessor:
    def __init__(self, cv_db_path='real_life/cv_data.db', game_db_path='game.db', 
                 leds_db_path='leds/LEDs.db', moving_target_db_path='leds/moving_target.db',
                 poll_interval=1.0, animation_duration=3.0):
        self.cv_db_path = cv_db_path
        self.game_db_path = game_db_path
        self.leds_db_path = leds_db_path
        self.moving_target_db_path = moving_target_db_path
        self.poll_interval = poll_interval
        self.animation_duration = animation_duration
        
        # Initialize timestamp to current local time
        self.last_throw_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"Moving Target dart processor initialized. Only processing throws after: {self.last_throw_timestamp}")
        
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
            
    @contextmanager
    def get_moving_target_connection(self):
        """Get a connection to the Moving Target database"""
        conn = sqlite3.connect(self.moving_target_db_path)
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
            animation_type: Type of animation ('target_hit', 'target_miss', 'win', etc.)
            turn_number: Current turn number
            player_id: Current player ID
            throw_number: Throw number (1-3)
            next_turn: Next turn number if advancing
            next_player: Next player ID if advancing
            target_hit: Whether the target was hit (for special animations)
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

    def get_active_target_segments(self):
        """Get the currently active target segments from the moving_target database"""
        try:
            with self.get_moving_target_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT segment_number, segment_type FROM active_segments WHERE active = 1')
                segments = cursor.fetchall()
                
                # Convert to a list of tuples (segment_number, segment_type)
                active_segments = [(seg['segment_number'], seg['segment_type']) for seg in segments]
                
                return active_segments
        except Exception as e:
            print(f"Error getting active target segments: {e}")
            return []  # Return empty list on error

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

    def add_throw_to_leds_db(self, score, multiplier, position_x, position_y, hit_target=False):
        """
        Add a throw to the LEDs database with the appropriate segment type.
        Includes a flag for whether this throw hit the target.
        """
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
                
                # For Moving Target mode, we set the segment type depending on whether it hit the target
                # This will be used by the LED controller to determine whether to blink green or red
                animation_type = "target_hit" if hit_target else "target_miss"
                
                cursor.execute('''
                    INSERT INTO dart_events (score, multiplier, segment_type, processed, timestamp)
                    VALUES (?, ?, ?, 0, CURRENT_TIMESTAMP)
                ''', (score, multiplier, segment_type))
                
                # Get the ID of the inserted event
                event_id = cursor.lastrowid
                
                # Update the segment type to include hit or miss information
                cursor.execute('''
                    UPDATE dart_events
                    SET segment_type = ?
                    WHERE id = ?
                ''', (f"{segment_type}_{animation_type}", event_id))
                
                conn.commit()
                
                hit_status = "HIT" if hit_target else "MISS"
                print(f"Added throw to LEDs database: Score={score}, Multiplier={multiplier}, Segment={segment_type}, Target {hit_status}")
        else:
            print(f"WARNING: Could not determine segment type for throw: Score={score}, Multiplier={multiplier}")

    def check_if_hit_target(self, score, segment_type):
        """Check if the throw hit the current active target"""
        active_segments = self.get_active_target_segments()
        
        # Check if the thrown dart matches any active segment
        is_hit = (score, segment_type) in active_segments
        
        print(f"Target check: {score} {segment_type} - {'HIT' if is_hit else 'MISS'}")
        return is_hit

    def update_player_score(self, player_id, points_to_add=1):
        """Update a player's score in the Moving Target game (1 point per hit)"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # Get current score
            cursor.execute('SELECT total_score FROM players WHERE id = ?', (player_id,))
            row = cursor.fetchone()
            if not row:
                print(f"Error: Player {player_id} not found")
                return
                
            current_score = row['total_score']
            new_score = current_score + points_to_add
            
            # Update the score
            cursor.execute('UPDATE players SET total_score = ? WHERE id = ?', (new_score, player_id))
            
            # Check for win condition (first to 5 points)
            if new_score >= 5:
                cursor.execute('UPDATE game_state SET game_over = 1 WHERE id = 1')
                print(f"Player {player_id} has won with {new_score} points!")
            
            conn.commit()
            
            return new_score

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
            cursor.execute('UPDATE current_throws SET points = 0, score = NULL, multiplier = NULL')
            
            conn.commit()
            
            print(f"Advanced to Player {next_player}, Turn {next_turn}")
            return next_player, next_turn

    def save_throw_details_to_turn_scores(self, turn_number, player_id, current_throws, hit_target=False):
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
            
            # Calculate points - In Moving Target, points field is used to track cumulative hits
            # If this throw hit the target, add 1 point
            points_to_add = 1 if hit_target else 0
            
            # Check if player already has a score for this turn
            cursor.execute(
                'SELECT points FROM turn_scores WHERE turn_number = ? AND player_id = ?',
                (turn_number, player_id)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing score with individual throw details
                # In Moving Target, we add to the existing points if a hit
                points = existing['points'] + points_to_add
                
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
                        points,
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
                        turn_number, player_id, points_to_add,
                        throw_columns.get('throw1', 0), throw_columns.get('throw1_multiplier', 0), throw_columns.get('throw1_points', 0),
                        throw_columns.get('throw2', 0), throw_columns.get('throw2_multiplier', 0), throw_columns.get('throw2_points', 0),
                        throw_columns.get('throw3', 0), throw_columns.get('throw3_multiplier', 0), throw_columns.get('throw3_points', 0)
                    )
                )
            
            conn.commit()
            
            print(f"Saved throw details to turn_scores for player {player_id}, turn {turn_number}, hit_target={hit_target}")

    def process_throw(self, throw):
        """Process a single throw for Moving Target game mode"""
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
            if t['score'] is None:
                throw_position = t['throw_number']
                break
        
        # Determine segment type for checking against target
        segment_type = None
        if score == 25:
            segment_type = "bullseye"
        elif multiplier == 2:
            segment_type = "double"
        elif multiplier == 3:
            segment_type = "triple"
        elif multiplier == 1:
            # Inner vs outer single determination based on r value
            r = position_x
            if r < 103:
                segment_type = "inner_single"
            else:
                segment_type = "outer_single"
        
        # Check if this throw hit the target
        hit_target = False
        if segment_type:
            hit_target = self.check_if_hit_target(score, segment_type)
        
        # Add to LEDs database with hit/miss information
        self.add_throw_to_leds_db(score, multiplier, position_x, position_y, hit_target)
        
        # Update the current throw with score, multiplier, and points
        self.update_current_throw(throw_position, score, multiplier, points)
        
        # Update the last throw record
        self.update_last_throw(score, multiplier, points, current_player)
        
        # Handle target hit
        if hit_target:
            print(f"Player {current_player} hit the target! Adding 1 point.")
            
            # Update player's score (add 1 point for hitting target)
            new_score = self.update_player_score(current_player, 1)
            
            # Check if player has won (reached 5 points)
            if new_score >= 5:
                # Save the throw details
                self.save_throw_details_to_turn_scores(current_turn, current_player, current_throws, hit_target)
                
                # Set the animation state for a win
                self.set_animation_state(
                    animation_type="win",
                    turn_number=current_turn,
                    player_id=current_player,
                    throw_number=throw_position,
                    next_turn=None,
                    next_player=None,
                    target_hit=True
                )
                
                print(f"Game over! Player {current_player} wins with {new_score} points!")
                return
        
        # Process game logic immediately when third throw happens
        if throw_position == 3:
            print(f"Third throw detected! Processing game logic...")
            
            # Explicitly refresh current_throws to include the latest throw
            current_throws = []
            with self.get_game_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT throw_number, points, score, multiplier FROM current_throws ORDER BY throw_number')
                current_throws = [dict(t) for t in cursor.fetchall()]
            
            # Save throw details to turn_scores
            self.save_throw_details_to_turn_scores(current_turn, current_player, current_throws, hit_target)
            
            # Calculate next player and turn
            with self.get_game_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) as count FROM players')
                player_count = cursor.fetchone()['count']
            
            next_player = current_player % player_count + 1
            next_turn = current_turn + (1 if next_player == 1 else 0)
            
            # Set animation state based on whether target was hit
            animation_type = "target_hit" if hit_target else "third_throw"
            
            # Set animation state BEFORE advancing game state
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
            # If not the third throw, set animation state without advancing player
            if hit_target:
                # Save throw details to turn_scores (partial update)
                self.save_throw_details_to_turn_scores(current_turn, current_player, current_throws, hit_target)
                
                # Set animation for target hit
                self.set_animation_state(
                    animation_type="target_hit",
                    turn_number=current_turn,
                    player_id=current_player,
                    throw_number=throw_position,
                    target_hit=True
                )
            else:
                # Set animation for target miss
                self.set_animation_state(
                    animation_type="target_miss",
                    turn_number=current_turn,
                    player_id=current_player,
                    throw_number=throw_position,
                    target_hit=False
                )
            
            print(f"Processed throw: {score}x{multiplier}={points} points "
                  f"(Player {current_player}, Turn {current_turn}, Throw {throw_position}, Hit Target: {hit_target})")

    def run(self):
        """Main processing loop"""
        print("Moving Target dart processor running, press Ctrl+C to stop...")
        
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
            print("\nMoving Target dart processor stopped.")

def main():
    processor = DartProcessor()
    processor.run()

if __name__ == "__main__":
    main()
