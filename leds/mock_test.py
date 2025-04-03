"""
Test script to run the LED Controller with the MockLEDs implementation
"""

import sys

def run_with_mock():
    """Run the LED controller using the mock LEDs implementation."""
    # Modify the system module cache to replace LEDs with MockLEDs
    print("Setting up MockLEDs...")
    
    # Import MockLEDs
    from MockLEDs import MockLEDs
    
    # Create a dummy module for LEDs that returns our MockLEDs class
    class DummyModule:
        LEDs = MockLEDs
    
    # Replace the LEDs module in sys.modules
    sys.modules['LEDs'] = DummyModule
    
    # Now import the LED_controller module (it will use our mock)
    print("Importing LED_controller...")
    import LED_controller
    
    # Start the controller with testing parameters
    print("Starting LED controller with MockLEDs...\n")
    controller = LED_controller.LEDController(
        blink_duration=2.0,  # Shorter blink for faster testing
        blink_count=2,       # Fewer blinks for testing
        poll_interval=0.5    # Faster polling for testing
    )
    
    # Run the controller normally - it will use MockLEDs due to our module patching
    controller.run()


def check_database_mode(db_path):
    """Check the current game mode in the database."""
    import sqlite3
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check game_mode table
        cursor.execute("SELECT mode FROM game_mode WHERE id = 1")
        mode_row = cursor.fetchone()
        
        if mode_row:
            print(f"Current game mode in database: '{mode_row['mode']}'")
        else:
            print("No game mode found in database")
            
        conn.close()
    except Exception as e:
        print(f"Error checking database: {e}")

if __name__ == "__main__":
    run_with_mock()