import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

class ManualDartEntry:
    def __init__(self, db_path='cv_data.db'):
        self.db_path = db_path
        self.setup_database()
        
    @contextmanager
    def get_db_connection(self):
        """Create a connection to the SQLite database"""
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
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
            print(f"Added throw #{throw_id}: Score: {score}, Multiplier: {multiplier}, Points: {score * multiplier}, Time: {current_time}")
            
    def list_recent_throws(self, limit=5):
        """List the most recent throws in the database"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, score, multiplier, score * multiplier as points
                FROM throws 
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (limit,))
            
            throws = cursor.fetchall()
            
            if not throws:
                print("No throws found in the database.")
                return
                
            print("\nRecent throws:")
            print("-" * 70)
            print(f"{'ID':4} | {'Timestamp':<19} | {'Score':5} | {'Mult':4} | {'Points':6}")
            print("-" * 70)
            
            for throw in throws:
                print(f"{throw['id']:4} | {throw['timestamp']:<19} | {throw['score']:5} | {throw['multiplier']:4} | {throw['points']:6}")
            
            print("-" * 70)

def print_menu():
    """Print the main menu"""
    print("\n===== MANUAL DART ENTRY =====")
    print("1. Add a throw")
    print("2. View recent throws")
    print("3. Exit")
    return input("Select an option (1-3): ")

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
    # Create the database directory if it doesn't exist
    database_path = 'simulation/cv_data.db'
    os.makedirs(os.path.dirname(database_path), exist_ok=True)
    
    dart_entry = ManualDartEntry(database_path)
    
    while True:
        choice = print_menu()
        
        if choice == '1':
            print("\n----- Add a throw -----")
            print("Valid scores: 1-20 for regular segments, 25 for bullseye")
            score = get_valid_input("Enter score (1-20, 25): ", 1, 25, int)
            
            # Handle multiplier based on score
            if score == 25:  # Bullseye can only be single (25) or double (50)
                print("Bullseye can only have multiplier 1 (25 points) or 2 (50 points)")
                multiplier = get_valid_input("Enter multiplier (1-2): ", 1, 2, int)
            else:
                multiplier = get_valid_input("Enter multiplier (1-3): ", 1, 3, int)
            
            # Simple position coordinates (optional)
            use_position = input("Add position coordinates? (y/n): ").lower() == 'y'
            position_x = position_y = 0.0
            
            if use_position:
                position_x = get_valid_input("Enter X position (-1.0 to 1.0): ", -1.0, 1.0, float)
                position_y = get_valid_input("Enter Y position (-1.0 to 1.0): ", -1.0, 1.0, float)
            
            # Add the throw to the database
            dart_entry.add_throw(score, multiplier, position_x, position_y)
            
        elif choice == '2':
            # View recent throws
            limit = get_valid_input("Number of throws to display: ", 1, 50, int)
            dart_entry.list_recent_throws(limit)
            
        elif choice == '3':
            print("Exiting. Goodbye!")
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()