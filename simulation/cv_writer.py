import sqlite3
from datetime import datetime
from contextlib import contextmanager
from darts_cv_simulation import DartDetection
import time

class CVDatabaseWriter:
    def __init__(self, db_path='cv_data.db'):
        self.db_path = db_path
        self.dart_detector = DartDetection()
        self.setup_database()

    @contextmanager
    def get_db_connection(self):
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
            # Add the system_state table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    ready_for_throw BOOLEAN DEFAULT 1,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert initial state if not exists
            cursor.execute('''
                INSERT OR IGNORE INTO system_state (id, ready_for_throw)
                VALUES (1, 1)
            ''')
            
            conn.commit()
    
    def set_ready_state(self, is_ready):
        """Update the ready state in the database"""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE system_state 
                    SET ready_for_throw = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE id = 1
                ''', (1 if is_ready else 0,))
                conn.commit()
        except sqlite3.Error as e:
            print(f"Error updating ready state: {e}")

    def record_throw(self, throw_data):
        """Record a throw to the database"""
        if not throw_data:
            return

        # Set system as not ready to process throws
        self.set_ready_state(False)
        
        score, multiplier, position = throw_data
        # Get current local time as a string in the format SQLite expects
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO throws (timestamp, score, multiplier, position_x, position_y)
                    VALUES (?, ?, ?, ?, ?)
                ''', (current_time, score, multiplier, position[0], position[1]))
                conn.commit()
                print(f"Recorded throw at {current_time}: Score={score}, Multiplier={multiplier}")
                print("")
            
            # Wait 2 seconds before setting system back to ready
            print("Waiting 2 seconds before accepting next throw...")
            time.sleep(2)
            
            # After successful processing and delay, set back to ready
            self.set_ready_state(True)
        except sqlite3.Error as e:
            # On error, still wait 2 seconds then set back to ready
            time.sleep(2)
            self.set_ready_state(True)
            print(f"Database error: {e}")
        except Exception as e:
            # On error, still wait 2 seconds then set back to ready
            time.sleep(2)
            self.set_ready_state(True)
            print(f"Error recording throw: {e}")

def main():
    # Create the database writer
    db_writer = CVDatabaseWriter()
    
    # Initialize the dart detector
    print("Initializing dart detection simulation...")
    db_writer.dart_detector.initialize()
    
    try:
        # Start the dart detection
        print("Starting dart detection simulation...")
        db_writer.dart_detector.start()
        
        # Main loop
        while True:
            # Get and record next throw
            throw = db_writer.dart_detector.get_next_throw()
            if throw:
                db_writer.record_throw(throw)
            
    except KeyboardInterrupt:
        print("\nStopping dart detection...")
        db_writer.dart_detector.stop()
        print("Dart detection stopped.")

if __name__ == "__main__":
    main()