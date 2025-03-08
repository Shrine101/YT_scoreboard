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
            cursor.execute('SELECT throw_number, points, score, multiplier FROM current_throws ORDER BY throw_number')
            throws = [dict(throw) for throw in cursor.fetchall()]
            
            return {
                'current_turn': state['current_turn'],
                'current_player': state['current_player'],
                'game_over': state['game_over'],
                'current_throws': throws
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

    def get_player_score_before_turn(self, player_id, turn_number):
        """Get a player's score before a specific turn"""
        with self.get_game_connection() as conn:
            cursor = conn.cursor()
            
            # Get the total points scored by this player before this turn
            cursor.execute(
                'SELECT SUM(points) as total_points FROM turn_scores WHERE player_id = ? AND turn_number < ? AND bust = 0',
                (player_id, turn_number)
            )
            
            total_previous_points = cursor.fetchone()['total_points'] or 0
            
            # Calculate the score before this turn (301 - previous points)
            score_before_turn = 301 - total_previous_points
            
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
            # This is the main change - we zero out the points when it's a bust
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
                        points_to_record,  # 0 if bust, otherwise the actual points
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
                        turn_number, player_id, points_to_record,  # 0 if bust, otherwise the actual points
                        throw_columns.get('throw1', 0), throw_columns.get('throw1_multiplier', 0), throw_columns.get('throw1_points', 0),
                        throw_columns.get('throw2', 0), throw_columns.get('throw2_multiplier', 0), throw_columns.get('throw2_points', 0),
                        throw_columns.get('throw3', 0), throw_columns.get('throw3_multiplier', 0), throw_columns.get('throw3_points', 0),
                        1 if is_bust else 0
                    )
                )
            
            # Update player's total score - MODIFIED for 301 game with bust handling
            # Get sum of all points scored by this player from non-busted turns
            cursor.execute(
                'SELECT SUM(points) as total_points FROM turn_scores WHERE player_id = ? AND bust = 0',
                (player_id,)
            )
            total_player_points = cursor.fetchone()['total_points'] or 0
            
            # Subtract from 301 to get current score
            new_score = 301 - total_player_points
            
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
            cursor.execute('UPDATE current_throws SET points = 0, score = 0, multiplier = 0')
            
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
        
        # Update the current throw with score, multiplier, and points
        self.update_current_throw(throw_position, score, multiplier, points)
        
        # Calculate total points for current throws
        total_current_points = 0
        for t in current_throws:
            if t['throw_number'] < throw_position:
                total_current_points += t['points']
        total_current_points += points  # Add points from this throw
        
        # Check if this would result in a bust
        player_score_before_turn = self.get_player_score_before_turn(current_player, current_turn)
        new_score = player_score_before_turn - total_current_points
        is_bust = (new_score < 0)
        
        # Handle bust or third throw immediately
        if is_bust or throw_position == 3:
            print(f"{'BUST' if is_bust else 'Third throw'} detected! Immediately finishing turn.")
            
            # Get current throw details (need to fetch again after updating)
            updated_throws = []
            with self.get_game_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT throw_number, points, score, multiplier FROM current_throws ORDER BY throw_number')
                updated_throws = [dict(throw) for throw in cursor.fetchall()]
            
            # Process the bust immediately instead of waiting
            self.add_score_to_turn(current_turn, current_player, total_current_points, updated_throws)
            
            # Only advance if game isn't over
            with self.get_game_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT game_over FROM game_state WHERE id = 1')
                game_over = cursor.fetchone()['game_over']
            
            if not game_over:
                # Advance to next player
                next_player, next_turn = self.advance_to_next_player()
                
                # Log the advancement
                print(f"Advanced to Player {next_player}, Turn {next_turn}{' due to bust' if is_bust else ''}")
            
            # Reset any waiting state
            if self.waiting_after_third_throw:
                self.waiting_after_third_throw = False
                self.third_throw_time = None
                self.third_throw_data = None
                
        else:
            # If not a bust or third throw, continue with normal play
            print(f"Processed throw: {score}x{multiplier}={points} points "
                  f"(Player {current_player}, Turn {current_turn}, Throw {throw_position})")
            
            # Reset delayed processing flag since we're processing immediately now
            self.waiting_after_third_throw = False

    def process_third_throw_completion(self):
        """This method is no longer needed since we process throws immediately now"""
        # Simply returning False as we don't use delayed processing anymore
        return False

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