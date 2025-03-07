import sqlite3
import time
from datetime import datetime
from contextlib import contextmanager

class DartProcessor:
    def __init__(self, cv_db_path='simulation/cv_data.db', game_db_path='game.db', poll_interval=1.0):
        self.cv_db_path = cv_db_path
        self.game_db_path = game_db_path
        self.poll_interval = poll_interval
        
        # Initialize timestamp to current local time
        self.last_throw_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # Track if we're waiting after a third throw
        self.waiting_after_third_throw = False
        self.third_throw_time = None
        self.third_throw_data = None
        
        print(f"Dart processor initialized. Only processing throws after: {self.last_throw_timestamp}")

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
            cursor.execute('SELECT throw_number, points FROM current_throws ORDER BY throw_number')
            throws = [dict(throw) for throw in cursor.fetchall()]
            
            return {
                'current_turn': state['current_turn'],
                'current_player': state['current_player'],
                'game_over': state['game_over'],
                'current_throws': throws
            }

    def update_current_throw(self, throw_number, points):
        """Update a specific throw in the current_throws table"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE current_throws SET points = ? WHERE throw_number = ?',
                (points, throw_number)
            )
            conn.commit()

    def add_score_to_turn(self, turn_number, player_id, points):
        """Add or update a player's score for a specific turn"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # Check if this turn exists
            cursor.execute('SELECT 1 FROM turns WHERE turn_number = ?', (turn_number,))
            if not cursor.fetchone():
                cursor.execute('INSERT INTO turns (turn_number) VALUES (?)', (turn_number,))
            
            # Check if player already has a score for this turn
            cursor.execute(
                'SELECT points FROM turn_scores WHERE turn_number = ? AND player_id = ?',
                (turn_number, player_id)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update existing score
                cursor.execute(
                    'UPDATE turn_scores SET points = ? WHERE turn_number = ? AND player_id = ?',
                    (points, turn_number, player_id)
                )
            else:
                # Insert new score
                cursor.execute(
                    'INSERT INTO turn_scores (turn_number, player_id, points) VALUES (?, ?, ?)',
                    (turn_number, player_id, points)
                )
            
            # Update player's total score - MODIFIED for 301 game
            # Get sum of all points scored by this player
            cursor.execute(
                'SELECT SUM(points) as total_points FROM turn_scores WHERE player_id = ?',
                (player_id,)
            )
            total_points = cursor.fetchone()['total_points'] or 0
            
            # Subtract from 301 to get current score
            new_score = 301 - total_points
            
            # Update player's total score
            cursor.execute(
                'UPDATE players SET total_score = ? WHERE id = ?',
                (new_score, player_id)
            )
            
            # Check if the player has won (score exactly 0)
            if new_score == 0:
                print(f"Player {player_id} has won the game with score of 0!")
                cursor.execute('UPDATE game_state SET game_over = 1 WHERE id = 1')
            
            conn.commit()

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
            
            cursor.execute('SELECT COUNT(*) as count FROM players')
            player_count = cursor.fetchone()['count']
            
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
            cursor.execute('UPDATE current_throws SET points = 0')
            
            conn.commit()
            
            return next_player, next_turn

    def process_throw(self, throw):
        """Process a single throw and update game state"""
        # Calculate points (score * multiplier)
        score = throw['score']
        multiplier = throw['multiplier']
        points = score * multiplier
        
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
        
        # Update the current throw
        self.update_current_throw(throw_position, points)
        
        # Check if this completes a set of 3 throws
        if throw_position == 3 or all(t['points'] > 0 for t in current_throws):
            # For third throw, we need to set the delayed processing
            if not self.waiting_after_third_throw:
                self.waiting_after_third_throw = True
                self.third_throw_time = datetime.now()
                
                # Save the data needed for later processing
                total_points = sum(t['points'] for t in current_throws) 
                # Add the current throw's points (not yet in current_throws)
                if throw_position == 3:
                    total_points += points
                
                self.third_throw_data = {
                    'current_turn': current_turn,
                    'current_player': current_player,
                    'total_points': total_points
                }
                
                print(f"Third throw detected! Will process after delay: {score}x{multiplier}={points} points")
            else:
                # This shouldn't happen in normal operation
                print("Warning: Got a new throw while waiting to process the previous third throw")
        
        print(f"Processed throw: {score}x{multiplier}={points} points "
              f"(Player {current_player}, Turn {current_turn}, Throw {throw_position})")

    def process_third_throw_completion(self):
        """Complete the processing of a third throw after delay"""
        if self.waiting_after_third_throw:
            # Check if enough time has passed (3 seconds)
            elapsed = (datetime.now() - self.third_throw_time).total_seconds()
            if elapsed >= 3.0:
                print(f"Completing third throw processing after {elapsed:.1f}s delay")
                
                # Add score to turn_scores
                self.add_score_to_turn(
                    self.third_throw_data['current_turn'],
                    self.third_throw_data['current_player'],
                    self.third_throw_data['total_points']
                )
                
                # Check game state again to see if the game is over after scoring
                with self.get_game_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('SELECT game_over FROM game_state WHERE id = 1')
                    game_over = cursor.fetchone()['game_over']
                
                # Only advance to next player if game isn't over
                if not game_over:
                    # Move to next player
                    self.advance_to_next_player()
                    print("Advanced to next player")
                else:
                    print("Game is over, not advancing to next player")
                
                # Reset the waiting state
                self.waiting_after_third_throw = False
                self.third_throw_time = None
                self.third_throw_data = None
                
                return True
        return False
    
    # Add this method to the DartProcessor class in dart_processor.py

    def record_throw_details(self, turn_number, player_id, throw_number, score, multiplier, points):
        """Record the details of an individual throw in the turn_throw_details table"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # Check if the table exists first
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='turn_throw_details'")
            if not cursor.fetchone():
                # The table doesn't exist yet - this should not normally happen if initialize_db was run
                print("Warning: turn_throw_details table doesn't exist, throw details will not be recorded")
                return
            
            # Check if this throw already exists
            cursor.execute('''
                SELECT 1 FROM turn_throw_details 
                WHERE turn_number = ? AND player_id = ? AND throw_number = ?
            ''', (turn_number, player_id, throw_number))
            
            exists = cursor.fetchone() is not None
            
            if exists:
                # Update existing throw
                cursor.execute('''
                    UPDATE turn_throw_details 
                    SET score = ?, multiplier = ?, points = ?
                    WHERE turn_number = ? AND player_id = ? AND throw_number = ?
                ''', (score, multiplier, points, turn_number, player_id, throw_number))
            else:
                # Insert new throw
                cursor.execute('''
                    INSERT INTO turn_throw_details (turn_number, player_id, throw_number, score, multiplier, points)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (turn_number, player_id, throw_number, score, multiplier, points))
            
            conn.commit()

    # Now, in the process_throw method of the DartProcessor class,
    # add the following code after the line that updates the current throw:

    # Find the line:
    self.update_current_throw(throw_position, points)

    # Add this immediately after:
    # Record detailed throw information
    self.record_throw_details(
        current_turn,    # Current turn number
        current_player,  # Current player ID 
        throw_position,  # Throw number (1, 2, or 3)
        score,           # Raw score (1-20 or 25 for bullseye)
        multiplier,      # Multiplier (1, 2, or 3)
        points           # Total points (score * multiplier)
    )

    def run(self):
        """Main processing loop"""
        print("Dart processor running, press Ctrl+C to stop...")
        
        try:
            while True:
                # First check if we need to complete a delayed third throw processing
                if self.waiting_after_third_throw:
                    self.process_third_throw_completion()
                else:
                    # Only process new throws if we're not waiting for third throw completion
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