import sqlite3
import time
from datetime import datetime
from contextlib import contextmanager

class DartProcessor:
    def __init__(self, cv_db_path='real_life/cv_data.db', game_db_path='game.db', 
                 leds_db_path='leds/LEDs.db', poll_interval=1.0, animation_duration=3.0):
        self.cv_db_path = cv_db_path
        self.game_db_path = game_db_path
        self.leds_db_path = leds_db_path  # Add LEDs database path
        self.poll_interval = poll_interval
        self.animation_duration = animation_duration  # Animation duration in seconds
        
        # Initialize timestamp to current local time
        self.last_throw_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"Dart processor initialized. Only processing throws after: {self.last_throw_timestamp}")
        
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

    def draw_dartboard_score(self, dart_positions: list[tuple[float, float]] = None,score=None,
        save_path: str = '../static/dartboard_scoring.png'):

        """Visualize dartboard with optional dart positions."""
        plt.figure(figsize=(12, 12))

        double_bull_radius = 6.35
        bull_radius = 16
        triple_inner_radius = 99
        triple_outer_radius = 107
        double_inner_radius = 162
        double_outer_radius = 170
        segments = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17,
                         3, 19, 7, 16, 8, 11, 14, 9, 12, 5]

        
        # Draw circles for different scoring regions
        circles = [
            (double_outer_radius, 'black', 'Double Ring'),
            (double_inner_radius, 'black', 'Double inner Ring'),
            (triple_outer_radius, 'black', 'Triple Ring'),
            (triple_inner_radius, 'black', 'Triple inner ring'),
            (bull_radius, 'green', 'Bull'),
            (double_bull_radius, 'red', 'Double Bull')
        ]
        
        for radius, color, label in circles:
            circle = plt.Circle((0, 0), radius, fill=False, color=color,
                              label=label if label else None)
            plt.gca().add_artist(circle)
        
        # Draw segment lines and numbers with 9 degree offset
        for i in range(20):
            angle = np.radians(i * 18 - 9)  # 18 degrees per segment, -9 for correct orientation
            dx = np.sin(angle) * double_outer_radius
            dy = np.cos(angle) * double_outer_radius
            plt.plot([0, dx], [0, dy], 'k-', linewidth=0.5)
            
            # Add segment numbers
            text_radius = triple_inner_radius  # Place numbers between triple and double
            text_x = np.sin(angle + np.radians(9)) * text_radius  # +9 degrees for center of segment
            text_y = np.cos(angle + np.radians(9)) * text_radius
            plt.text(text_x, text_y, str(segments[i]), 
                    ha='center', va='center')
        
        # Plot dart positions if provided 
        plt.plot(dart_positions[0], dart_positions[1], 'ro', markersize=10, label=f'Dart: {score}')
        
        plt.axis('equal')
        plt.grid(True)
        plt.title('Dartboard Scoring Regions')
        plt.xlabel('X Position (mm)')
        plt.ylabel('Y Position (mm)')
        
        # Set axis limits to show full board with some padding
        limit = self.double_outer_radius * 1.1

        plt.legend()
        plt.show()


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

    def set_animation_state(self, animation_type, turn_number, player_id, throw_number, next_turn=None, next_player=None):
        """Set the animation state in the database"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE animation_state 
                SET animating = 1, 
                    animation_type = ?, 
                    turn_number = ?, 
                    player_id = ?, 
                    throw_number = ?, 
                    timestamp = ?,
                    next_turn = ?,
                    next_player = ?
                WHERE id = 1
            ''', (animation_type, turn_number, player_id, throw_number, current_time, next_turn, next_player))
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
            
            # Get game mode (301 or 501)
            cursor.execute('SELECT game_mode FROM game_config WHERE id = 1')
            config = cursor.fetchone()
            game_mode = config['game_mode'] if config and config['game_mode'] else "301"
            
            # Try to convert game_mode to integer if possible
            try:
                starting_score = int(game_mode)
            except (ValueError, TypeError):
                starting_score = 301  # Default to 301 if not a valid integer
            
            return {
                'current_turn': state['current_turn'],
                'current_player': state['current_player'],
                'game_over': state['game_over'],
                'current_throws': throws,
                'starting_score': starting_score
            }

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
    
    def get_player_score_before_turn(self, player_id, turn_number):
        """Get a player's score before a specific turn"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # Get starting score from game_config
            cursor.execute('SELECT game_mode FROM game_config WHERE id = 1')
            config = cursor.fetchone()
            starting_score = 301  # Default to 301
            
            if config and config['game_mode']:
                try:
                    starting_score = int(config['game_mode'])
                except (ValueError, TypeError):
                    # If not a valid number, check for mode strings
                    if config['game_mode'] == '501':
                        starting_score = 501
                    else:
                        starting_score = 301  # Default
            
            # Get the total points scored by this player before this turn
            cursor.execute(
                'SELECT SUM(points) as total_points FROM turn_scores WHERE player_id = ? AND turn_number < ? AND bust = 0',
                (player_id, turn_number)
            )
            
            total_previous_points = cursor.fetchone()['total_points'] or 0
            
            # Calculate the score before this turn (starting_score - previous points)
            score_before_turn = starting_score - total_previous_points
            
            return score_before_turn

    def add_score_to_turn(self, turn_number, player_id, total_points, current_throws):
        """Add or update a player's score for a specific turn with individual throw details"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # Check if this turn exists
            cursor.execute('SELECT 1 FROM turns WHERE turn_number = ?', (turn_number,))
            if not cursor.fetchone():
                cursor.execute('INSERT INTO turns (turn_number) VALUES (?)', (turn_number,))
            
            # Get player's score before this turn
            score_before_turn = self.get_player_score_before_turn(player_id, turn_number)
            
            # Check if this turn would result in a bust (score < 0)
            new_score = score_before_turn - total_points
            is_bust = (new_score < 0)
            
            # If it's a bust, set the points to 0 since none of the throws count
            points_to_record = 0 if is_bust else total_points
            
            # Map throws to their respective columns
            throw_columns = {}
            for throw in current_throws:
                throw_num = throw['throw_number']
                throw_columns[f'throw{throw_num}'] = throw['score']
                throw_columns[f'throw{throw_num}_multiplier'] = throw['multiplier']
                throw_columns[f'throw{throw_num}_points'] = throw['points']
            
            # Check if player already has a score for this turn
            cursor.execute(
                'SELECT points, bust FROM turn_scores WHERE turn_number = ? AND player_id = ?',
                (turn_number, player_id)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing score with individual throw details and bust flag
                update_query = '''
                UPDATE turn_scores 
                SET points = ?, 
                    throw1 = ?, throw1_multiplier = ?, throw1_points = ?,
                    throw2 = ?, throw2_multiplier = ?, throw2_points = ?,
                    throw3 = ?, throw3_multiplier = ?, throw3_points = ?,
                    bust = ?
                WHERE turn_number = ? AND player_id = ?
                '''
                cursor.execute(
                    update_query,
                    (
                        points_to_record,
                        throw_columns.get('throw1', 0), throw_columns.get('throw1_multiplier', 0), throw_columns.get('throw1_points', 0),
                        throw_columns.get('throw2', 0), throw_columns.get('throw2_multiplier', 0), throw_columns.get('throw2_points', 0),
                        throw_columns.get('throw3', 0), throw_columns.get('throw3_multiplier', 0), throw_columns.get('throw3_points', 0),
                        1 if is_bust else 0,
                        turn_number, player_id
                    )
                )
            else:
                # Insert new score with individual throw details and bust flag
                insert_query = '''
                INSERT INTO turn_scores (
                    turn_number, player_id, points,
                    throw1, throw1_multiplier, throw1_points,
                    throw2, throw2_multiplier, throw2_points,
                    throw3, throw3_multiplier, throw3_points,
                    bust
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
                cursor.execute(
                    insert_query,
                    (
                        turn_number, player_id, points_to_record,
                        throw_columns.get('throw1', 0), throw_columns.get('throw1_multiplier', 0), throw_columns.get('throw1_points', 0),
                        throw_columns.get('throw2', 0), throw_columns.get('throw2_multiplier', 0), throw_columns.get('throw2_points', 0),
                        throw_columns.get('throw3', 0), throw_columns.get('throw3_multiplier', 0), throw_columns.get('throw3_points', 0),
                        1 if is_bust else 0
                    )
                )
            
            # Get starting score from game_config
            cursor.execute('SELECT game_mode FROM game_config WHERE id = 1')
            config = cursor.fetchone()
            starting_score = 301  # Default to 301
            
            if config and config['game_mode']:
                try:
                    starting_score = int(config['game_mode'])
                except (ValueError, TypeError):
                    # If not a valid number, check for mode strings
                    if config['game_mode'] == '501':
                        starting_score = 501
                    else:
                        starting_score = 301  # Default
            
            # Update player's total score based on game mode
            # Get sum of all points scored by this player from non-busted turns
            cursor.execute(
                'SELECT SUM(points) as total_points FROM turn_scores WHERE player_id = ? AND bust = 0',
                (player_id,)
            )
            total_player_points = cursor.fetchone()['total_points'] or 0
            
            # Subtract from starting score to get current score
            new_score = starting_score - total_player_points
            
            # Update player's total score
            cursor.execute(
                'UPDATE players SET total_score = ? WHERE id = ?',
                (new_score, player_id)
            )
            
            # Check if the player has won (score exactly 0)
            if new_score == 0:
                print(f"Player {player_id} has won the game with score of 0!")
                cursor.execute('UPDATE game_state SET game_over = 1 WHERE id = 1')
            
            # Log the result
            if is_bust:
                print(f"BUST! Turn {turn_number}, Player {player_id} busted (score would be {score_before_turn - total_points})")
                print(f"No points will be counted for this turn.")
            
            conn.commit()
            
            return is_bust

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

    def convert_to_cart(self,r,theta_deg):
        r = position_x
        theta_deg = position_y
        theta_rad = np.radians(theta_deg)
        x = r * np.cos(theta_rad)
        y = r * np.sin(theta_rad)
        dart_position = [(x, y)]

    def process_throw(self, throw):
        """Process a single throw and update game state"""
        # Calculate points (score * multiplier)
        score = throw['score']
        multiplier = throw['multiplier']
        points = score * multiplier
        
        # Safely access position coordinates from sqlite3.Row
        # Fix for the AttributeError: 'sqlite3.Row' object has no attribute 'get'
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
        
        # Write to LEDs database - Add this new functionality
        self.add_throw_to_leds_db(score, multiplier, position_x, position_y)
        
        # Update the current throw with score, multiplier, and points
        self.update_current_throw(throw_position, score, multiplier, points)
        
        # Update the last throw record
        self.update_last_throw(score, multiplier, points, current_player)

        # NEW: Draw scoring visualization
        #dart_position = [(real_position_x, real_position_y)]  # Must be list of tuples
        #self.draw_dartboard_score(dart_positions=dart_position, score=points)
        
        # Calculate total points for current throws
        total_current_points = sum(t['points'] for t in current_throws if t['throw_number'] != throw_position and t['score'] is not None) + points
        
        # Check if this would result in a bust
        player_score_before_turn = self.get_player_score_before_turn(current_player, current_turn)
        new_score = player_score_before_turn - total_current_points
        is_bust = (new_score < 0)

        # Check if this would result in a win (score exactly 0)
        if new_score == 0:
            print(f"WIN detected! Player {current_player} has won with a perfect score of 0!")
            
            # Explicitly refresh current_throws to include the latest throw
            current_throws = []
            with self.get_game_connection() as conn:
                cursor = conn.cursor()
                # Get the updated current_throws after our update above
                cursor.execute('SELECT throw_number, points, score, multiplier FROM current_throws ORDER BY throw_number')
                current_throws = [dict(t) for t in cursor.fetchall()]
            
            # Record the score in the database
            self.add_score_to_turn(current_turn, current_player, total_current_points, current_throws)
            
            # Set game_over to 1
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
            
            print(f"Game over! Animation state set for: win")
            return  # Stop processing further
        
        # Process game logic immediately
        if is_bust or throw_position == 3:
            animation_type = "bust" if is_bust else "third_throw"
            print(f"{animation_type.upper()} detected! Processing game logic...")
            
            # **** CRITICAL FIX: Explicitly refresh current_throws to include the latest throw ****
            current_throws = []
            with self.get_game_connection() as conn:
                cursor = conn.cursor()
                # Get the updated current_throws after our update above
                cursor.execute('SELECT throw_number, points, score, multiplier FROM current_throws ORDER BY throw_number')
                current_throws = [dict(t) for t in cursor.fetchall()]
            
            # Record the score in the database
            self.add_score_to_turn(current_turn, current_player, total_current_points, current_throws)
            
            # Only advance if game isn't over
            with self.get_game_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT game_over FROM game_state WHERE id = 1')
                game_over = cursor.fetchone()['game_over']
            
            if not game_over:
                # Calculate next player and turn
                with self.get_game_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT COUNT(*) as count FROM players')
                    player_count = cursor.fetchone()['count']
                
                next_player = current_player % player_count + 1  # Cycle to next player (1-based)
                next_turn = current_turn + (1 if next_player == 1 else 0)  # Increment turn if we wrapped around
                
                # **** IMPORTANT: Set animation state BEFORE advancing game state ****
                self.set_animation_state(
                    animation_type=animation_type,
                    turn_number=current_turn,
                    player_id=current_player,
                    throw_number=throw_position,
                    next_turn=next_turn,
                    next_player=next_player
                )
                
                # Advance to next player
                self.advance_to_next_player()
                
                print(f"Game state advanced. Animation state set for: {animation_type}")
        else:
            # If not a bust or third throw, continue with normal play
            print(f"Processed throw: {score}x{multiplier}={points} points "
                  f"(Player {current_player}, Turn {current_turn}, Throw {throw_position})")

    def run(self):
        """Main processing loop"""
        print("Dart processor running, press Ctrl+C to stop...")
        
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
            print("\nDart processor stopped.")

def main():
    processor = DartProcessor()
    processor.run()

if __name__ == "__main__":
    main()