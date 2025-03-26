import sqlite3
import time
from datetime import datetime

def add_dart_event(score, multiplier):
    """Add a dart event to the LEDs database."""
    conn = sqlite3.connect('LEDs.db')
    cursor = conn.cursor()
    
    # Insert the dart event
    cursor.execute(
        'INSERT INTO dart_events (score, multiplier, processed, timestamp) VALUES (?, ?, 0, CURRENT_TIMESTAMP)',
        (score, multiplier)
    )
    
    # Get the ID of the inserted event
    event_id = cursor.lastrowid
    
    # Commit and close
    conn.commit()
    conn.close()
    
    print(f"Added dart event #{event_id}: Score={score}, Multiplier={multiplier}")
    return event_id

def main():
    """Test utility for adding dart events."""
    print("Dart Event Test Utility")
    print("----------------------")
    
    while True:
        print("\nOptions:")
        print("1. Add a new dart event")
        print("2. Exit")
        
        choice = input("Select an option (1-2): ")
        
        if choice == '1':
            # Get dart details
            while True:
                try:
                    score = int(input("Enter score (1-20, 25 for bullseye): "))
                    if (score >= 1 and score <= 20) or score == 25:
                        break
                    print("Invalid score. Must be between 1-20 or 25 for bullseye.")
                except ValueError:
                    print("Please enter a valid number.")
            
            # Get multiplier
            while True:
                try:
                    if score == 25:
                        print("Bullseye can only have multiplier 1 (25) or 2 (50)")
                        multiplier = int(input("Enter multiplier (1-2): "))
                        if multiplier >= 1 and multiplier <= 2:
                            break
                    else:
                        multiplier = int(input("Enter multiplier (1-3): "))
                        if multiplier >= 1 and multiplier <= 3:
                            break
                    print("Invalid multiplier.")
                except ValueError:
                    print("Please enter a valid number.")
            
            # Add the event
            add_dart_event(score, multiplier)
            print(f"Dart event added: {score}x{multiplier}")
            
        elif choice == '2':
            print("Exiting test utility.")
            break
        else:
            print("Invalid option. Please try again.")

if __name__ == "__main__":
    main()