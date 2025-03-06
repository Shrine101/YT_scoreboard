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
            # Get current turn and player
            cursor = conn.cursor()
            cursor.execute('SELECT current_turn, current_player FROM game_state WHERE id = 1')
            state = cursor.fetchone()
            
            # Get current throws
            cursor.execute('SELECT throw_number, points FROM current_throws ORDER BY throw_number')
            throws = [dict(throw) for throw in cursor.fetchall()]
            
            return {
                'current_turn': state['current_turn'],
                'current_player': state['current_player'],
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
            
            conn.commit()

    def advance_to_next_player(self):
        """Move to the next player, and possibly next turn"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # Get current state and player count
            cursor.execute('SELECT current_turn, current_player FROM game_state WHERE id = 1')
            state = cursor.fetchone()
            
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
            # Calculate total points for this player's turn
            total_points = sum(t['points'] for t in current_throws) + points
            
            # Add score to turn_scores
            self.add_score_to_turn(current_turn, current_player, total_points)
            
            # Move to next player
            self.advance_to_next_player()
        
        # Update timestamp to this throw's timestamp to avoid processing it again
        self.last_throw_timestamp = throw['timestamp']
        
        print(f"Processed throw: {score}x{multiplier}={points} points "
              f"(Player {current_player}, Turn {current_turn}, Throw {throw_position})")

    def run(self):
        """Main processing loop"""
        print("Dart processor running, press Ctrl+C to stop...")
        
        try:
            while True:
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