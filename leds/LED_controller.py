import sqlite3
import time
from contextlib import contextmanager
from LEDs import LEDs
from datetime import datetime

class LEDController:
    def __init__(self, db_path='LEDs.db', poll_interval=0.5):
        """Initialize the LED Controller."""
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.led_control = LEDs()  # Initialize LED control class
        self.current_mode = None
        self.blinking_segments = {}  # To track segments that should be blinking
        
        # Define sets for different LED color schemes in classic mode
        self.white_red_segments = {1, 4, 6, 15, 17, 19, 16, 11, 9, 5}
        self.yellow_blue_segments = {20, 18, 13, 10, 2, 3, 7, 8, 14, 12}
        
        print("LED Controller initialized.")

    @contextmanager
    def get_db_connection(self):
        """Get a connection to the LEDs database."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def get_current_mode(self):
        """Get current game mode from database."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT mode FROM game_mode WHERE id = 1")
            mode = cursor.fetchone()
            return mode['mode'] if mode else 'classic'  # Default to classic if no mode is set

    def get_new_dart_events(self):
        """Get new unprocessed dart events from database."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id, score, multiplier, timestamp FROM dart_events WHERE processed = 0 ORDER BY timestamp ASC'
            )
            events = cursor.fetchall()
            
            # Mark events as processed
            if events:
                event_ids = [event['id'] for event in events]
                cursor.execute(
                    f"UPDATE dart_events SET processed = 1 WHERE id IN ({','.join(['?'] * len(event_ids))})",
                    event_ids
                )
                conn.commit()
                
            return events

    def mark_event_as_processed(self, event_id):
        """Mark an event as processed in the database."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE dart_events SET processed = 1 WHERE id = ?", (event_id,))
            conn.commit()

    def setup_classic_mode(self):
        """Set up LEDs for classic mode."""
        print("Setting up classic mode pattern...")
        
        # Clear all LEDs first to reset
        self.led_control.clearAll(wait_ms=1)
        
        # Process white/red segments
        for number in self.white_red_segments:
            # Skip if not in mapping
            if number not in self.led_control.DARTBOARD_MAPPING:
                continue
                
            # Single segments - White
            self.led_control.innerSingleSeg(number, (255, 255, 255))  # White
            self.led_control.outerSingleSeg(number, (255, 255, 255))  # White
            
            # Double segment - Red
            self.led_control.doubleSeg(number, (255, 0, 0))  # Red
            
            # Triple segment - Red
            self.led_control.tripleSeg(number, (255, 0, 0))  # Red
        
        # Process yellow/blue segments
        for number in self.yellow_blue_segments:
            # Skip if not in mapping
            if number not in self.led_control.DARTBOARD_MAPPING:
                continue
                
            # Single segments - Yellow
            self.led_control.innerSingleSeg(number, (255, 255, 0))  # Yellow
            self.led_control.outerSingleSeg(number, (255, 255, 0))  # Yellow
            
            # Double segment - Blue
            self.led_control.doubleSeg(number, (0, 0, 255))  # Blue
            
            # Triple segment - Blue
            self.led_control.tripleSeg(number, (0, 0, 255))  # Blue
        
        # Bullseye - Red
        self.led_control.bullseye((255, 0, 0))  # Red
        
        print("Classic mode setup complete.")

    def process_dart_event(self, event):
        """Process a dart event and update LEDs accordingly."""
        score = event['score']
        multiplier = event['multiplier']
        event_id = event['id']
        
        print(f"Processing dart event #{event_id}: Score={score}, Multiplier={multiplier}")
        
        # Store original colors to restore after blinking
        original_colors = {}
        
        # Add the segment to the blinking segments with expiration time (current time + 2 seconds)
        expiration_time = time.time() + 2
        
        if score == 25:  # Bullseye
            # For bullseye, we'll just store the special case
            self.blinking_segments['bullseye'] = {
                'expiration': expiration_time,
                'original_color': (255, 0, 0)  # Original color is red
            }
        elif score in self.led_control.DARTBOARD_MAPPING:
            # For regular segments
            if multiplier == 2:  # Double ring
                color = (255, 0, 0) if score in self.white_red_segments else (0, 0, 255)
                self.blinking_segments[f'double_{score}'] = {
                    'expiration': expiration_time,
                    'original_color': color,
                    'score': score,
                    'segment_type': 'double'
                }
            elif multiplier == 3:  # Triple ring
                color = (255, 0, 0) if score in self.white_red_segments else (0, 0, 255)
                self.blinking_segments[f'triple_{score}'] = {
                    'expiration': expiration_time,
                    'original_color': color,
                    'score': score,
                    'segment_type': 'triple'
                }
            else:  # Single segment - use inner for simplicity
                color = (255, 255, 255) if score in self.white_red_segments else (255, 255, 0)
                self.blinking_segments[f'single_{score}'] = {
                    'expiration': expiration_time,
                    'original_color': color,
                    'score': score,
                    'segment_type': 'single'
                }
        
        # Immediately light up the hit segment in green
        self.update_blinking_segments(True)  # True to force update

    def update_blinking_segments(self, force_update=False):
        """Update any segments that should be blinking."""
        current_time = time.time()
        
        # Check if time to update (we'll toggle the blink state every 0.2 seconds)
        should_update = force_update or (int(current_time * 5) % 2 == 0)  # 5Hz blink rate
        
        if should_update:
            # Process each blinking segment
            to_remove = []
            
            for segment_id, info in self.blinking_segments.items():
                # Check if this segment's blinking period has expired
                if current_time > info['expiration']:
                    # Restore original color
                    if segment_id == 'bullseye':
                        self.led_control.bullseye(info['original_color'])
                    elif 'segment_type' in info:
                        score = info['score']
                        if info['segment_type'] == 'double':
                            self.led_control.doubleSeg(score, info['original_color'])
                        elif info['segment_type'] == 'triple':
                            self.led_control.tripleSeg(score, info['original_color'])
                        elif info['segment_type'] == 'single':
                            # For simplicity, we'll update both inner and outer single segments
                            self.led_control.innerSingleSeg(score, info['original_color'])
                            self.led_control.outerSingleSeg(score, info['original_color'])
                    
                    # Mark for removal
                    to_remove.append(segment_id)
                else:
                    # This segment should be blinking - set to green
                    green_color = (0, 255, 0)  # Bright green
                    
                    if segment_id == 'bullseye':
                        self.led_control.bullseye(green_color)
                    elif 'segment_type' in info:
                        score = info['score']
                        if info['segment_type'] == 'double':
                            self.led_control.doubleSeg(score, green_color)
                        elif info['segment_type'] == 'triple':
                            self.led_control.tripleSeg(score, green_color)
                        elif info['segment_type'] == 'single':
                            # For simplicity, we'll update both inner and outer single segments
                            self.led_control.innerSingleSeg(score, green_color)
                            self.led_control.outerSingleSeg(score, green_color)
            
            # Remove expired segments
            for segment_id in to_remove:
                del self.blinking_segments[segment_id]

    def run(self):
        """Main processing loop for the LED controller."""
        print("LED Controller running, press Ctrl+C to stop...")
        
        try:
            # Initial setup based on current mode
            self.current_mode = self.get_current_mode()
            if self.current_mode == 'classic':
                self.setup_classic_mode()
            
            # Main processing loop
            while True:
                # Check for game mode changes
                new_mode = self.get_current_mode()
                if new_mode != self.current_mode:
                    print(f"Game mode changed from {self.current_mode} to {new_mode}")
                    self.current_mode = new_mode
                    
                    # Update LED pattern based on new mode
                    if self.current_mode == 'classic':
                        self.setup_classic_mode()
                    # Add other modes here as needed
                
                # Get new dart events
                events = self.get_new_dart_events()
                
                # Process each new event
                for event in events:
                    self.process_dart_event(event)
                
                # Update blinking segments
                self.update_blinking_segments()
                
                # Sleep for a bit before next poll
                time.sleep(self.poll_interval)
                
        except KeyboardInterrupt:
            print("\nLED Controller stopped.")
            # Clean up
            self.led_control.clearAll()

def main():
    controller = LEDController()
    controller.run()

if __name__ == "__main__":
    main()