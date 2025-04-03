import sqlite3
import os
import random
from datetime import datetime
from contextlib import contextmanager

class ManualDartEntry:
    def __init__(self, db_path='cv_data.db'):
        self.db_path = db_path
        self.setup_database()
        
    @contextmanager
    def get_db_connection(self):
        """Create a connection to the SQLite database"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
            
    def setup_database(self):
        """Create the database and necessary tables if they don't exist"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS throws (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    score INTEGER NOT NULL,
                    multiplier INTEGER NOT NULL,
                    position_x REAL,
                    position_y REAL
                )
            ''')
            conn.commit()
            print(f"Database initialized at {self.db_path}")
            
    def add_throw(self, score, multiplier, position_x=0.0, position_y=0.0):
        """Add a throw to the database with the current timestamp"""
        # Get current timestamp in SQLite format
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO throws (timestamp, score, multiplier, position_x, position_y)
                VALUES (?, ?, ?, ?, ?)
            ''', (current_time, score, multiplier, position_x, position_y))
            conn.commit()
            
            # Get the ID of the inserted throw
            throw_id = cursor.lastrowid
            
            if score == 0:
                print(f"Added throw #{throw_id}: MISSED THROW (Score: 0, Multiplier: 0, Points: 0)")
            else:
                print(f"Added throw #{throw_id}: Score: {score}, Multiplier: {multiplier}, Points: {score * multiplier}")
                
            print(f"Position: r={position_x}, θ={position_y}°, Time: {current_time}")
            
    def list_recent_throws(self, limit=5):
        """List the most recent throws in the database"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, score, multiplier, score * multiplier as points, position_x, position_y
                FROM throws 
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
            
            throws = cursor.fetchall()
            
            if not throws:
                print("No throws found in the database.")
                return
                
            print("\nRecent throws:")
            print("-" * 90)
            print(f"{'ID':4} | {'Timestamp':<19} | {'Score':5} | {'Mult':4} | {'Points':6} | {'r (x)':6} | {'θ (y)':7}")
            print("-" * 90)
            
            for throw in throws:
                print(f"{throw['id']:4} | {throw['timestamp']:<19} | {throw['score']:5} | {throw['multiplier']:4} | "
                      f"{throw['points']:6} | {throw['position_x']:6.1f} | {throw['position_y']:7.1f}")
            
            print("-" * 90)

def print_menu():
    """Print the main menu"""
    print("\n===== MANUAL DART ENTRY =====")
    print("1. Add a throw")
    print("2. Add a missed throw")
    print("3. View recent throws")
    print("4. Exit")
    return input("Select an option (1-4): ")

def get_valid_score():
    """Get a valid dartboard score (1-20 or 25)"""
    while True:
        try:
            score = int(input("Enter score (1-20, 25 for bullseye): "))
            # FIXED: Now correctly validates that score is either 1-20 OR exactly 25
            if (score >= 1 and score <= 20) or score == 25:
                return score
            print("Invalid score. Must be between 1-20 or exactly 25 for bullseye.")
        except ValueError:
            print("Please enter a valid number.")

def get_valid_multiplier(score):
    """Get a valid multiplier based on the score"""
    if score == 25:  # Bullseye
        while True:
            try:
                multiplier = int(input("Enter multiplier (1-2): "))
                if multiplier >= 1 and multiplier <= 2:
                    return multiplier
                print("Bullseye can only have multiplier 1 (25 points) or 2 (50 points)")
            except ValueError:
                print("Please enter a valid number.")
    else:  # Regular number
        while True:
            try:
                multiplier = int(input("Enter multiplier (1-3): "))
                if multiplier >= 1 and multiplier <= 3:
                    return multiplier
                print("Invalid multiplier. Must be between 1-3.")
            except ValueError:
                print("Please enter a valid number.")

def get_valid_input(prompt, min_val, max_val, input_type=int):
    """Get a valid numeric input within a range"""
    while True:
        try:
            value = input_type(input(prompt))
            if min_val <= value <= max_val:
                return value
            print(f"Please enter a value between {min_val} and {max_val}.")
        except ValueError:
            print(f"Invalid input. Please enter a valid {input_type.__name__}.")

def main():
    # Use the default path in the current directory
    database_path = 'cv_data.db'
    
    dart_entry = ManualDartEntry(database_path)
    
    while True:
        choice = print_menu()
        
        if choice == '1':
            print("\n----- Add a throw -----")
            print("Valid scores: 1-20 for regular segments, 25 for bullseye")
            
            # Get a valid score and multiplier
            score = get_valid_score()
            multiplier = get_valid_multiplier(score)
            
            # Dartboard position coordinates in polar form
            print("\n--- Enter Position in Polar Coordinates ---")
            print("r = distance from center (0-225, where 0 is bullseye, 225 is edge)")
            print("θ = angle in degrees (0-359, where 0° is top center, moving clockwise)")
            
            # Get r (position_x) value (0-225)
            position_x = get_valid_input("Enter r value (0-225): ", 0, 225, float)
            
            # Get theta (position_y) value (0-359)
            position_y = get_valid_input("Enter θ angle (0-359): ", 0, 359, float)
            
            # Add the throw to the database
            dart_entry.add_throw(score, multiplier, position_x, position_y)
            
            # Show a summary of what was added
            print("\nThrow summary:")
            print(f"Score: {score}, Multiplier: {multiplier}, Total points: {score * multiplier}")
            print(f"Position: r={position_x}, θ={position_y}°")
            print(f"This corresponds to {segment_description(score, multiplier, position_x)} on the dartboard")
            
        elif choice == '2':
            print("\n----- Add a missed throw -----")
            print("This will record a throw that completely missed the dartboard (0 points)")
            
            # For missed throws, use positions that are clearly outside the dartboard
            position_x = 300.0  # Far outside the normal dartboard radius (>225)
            position_y = float(random.randint(0, 359))  # Random angle
            
            # Add the missed throw to the database
            dart_entry.add_throw(0, 0, position_x, position_y)
            
            print("\nMissed throw recorded successfully!")
            
        elif choice == '3':
            # View recent throws
            limit = get_valid_input("Number of throws to display: ", 1, 50, int)
            dart_entry.list_recent_throws(limit)
            
        elif choice == '4':
            print("Exiting. Goodbye!")
            break
            
        else:
            print("Invalid choice. Please try again.")

def segment_description(score, multiplier, radius):
    """Return a description of which segment this is likely to be"""
    if score == 0:
        return "missed throw (outside the dartboard)"
    if score == 25:
        return "bullseye" if multiplier == 1 else "double bullseye"
    
    # Approximate segment boundaries based on a standard dartboard
    if multiplier == 2:
        return "double ring"
    elif multiplier == 3:
        return "triple ring"
    else:  # multiplier == 1
        if radius < 103:  # This threshold can be adjusted based on your dartboard model
            return "inner single (between triple and bullseye)"
        else:
            return "outer single (between double and edge)"

if __name__ == "__main__":
    main()