import sqlite3
import time
from contextlib import contextmanager
from LEDs import LEDs
from datetime import datetime

class LEDController:
    def __init__(self, db_path='LEDs.db', poll_interval=0.5, 
                 blink_duration=2.0, blink_count=4):
        """Initialize the LED Controller with configurable blinking parameters.
        
        Args:
            db_path (str): Path to the LED database file
            poll_interval (float): How often to check for updates (seconds)
            blink_duration (float): How long to blink when a dart hits (seconds)
            blink_count (int): Number of times to blink the LED
        """
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.led_control = LEDs()  # Initialize LED control class
        self.current_mode = None
        self.blinking_segments = {}  # To track segments that should be blinking
        
        # Blinking configuration
        self.blink_duration = blink_duration
        self.blink_count = blink_count
        # Calculate frequency based on duration and count
        self.blink_frequency = blink_count / blink_duration if blink_duration > 0 else 2.0
        
        # Define sets for different LED color schemes in classic mode
        self.white_red_segments = {1, 4, 6, 15, 17, 19, 16, 11, 9, 5}
        self.yellow_blue_segments = {20, 18, 13, 10, 2, 3, 7, 8, 14, 12}

        # Set colors for later use 
        self.dim_white = (100, 100, 100)
        self.red = (200, 0, 0)
        self.blue = (0, 0, 200)
        self.yellow = (200, 100, 0)


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
                'SELECT id, score, multiplier, segment_type, timestamp FROM dart_events WHERE processed = 0 ORDER BY timestamp ASC'
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
        # Clear all LEDs first to reset
        self.led_control.clearAll(wait_ms=1)
        
        # Process white/red segments
        for number in self.white_red_segments:
            # Skip if not in mapping
            if number not in self.led_control.DARTBOARD_MAPPING:
                continue
                
            # Single segments - White
            self.led_control.innerSingleSeg(number, self.dim_white)  # White
            self.led_control.outerSingleSeg(number, self.dim_white)  # White
            
            # Double segment - Red
            self.led_control.doubleSeg(number, self.red)  # Red
            
            # Triple segment - Red
            self.led_control.tripleSeg(number, self.red)  # Red
        
        # Process yellow/blue segments
        for number in self.yellow_blue_segments:
            # Skip if not in mapping
            if number not in self.led_control.DARTBOARD_MAPPING:
                continue
                
            # Single segments - Yellow
            self.led_control.innerSingleSeg(number, self.yellow)  # Yellow
            self.led_control.outerSingleSeg(number, self.yellow)  # Yellow
            
            # Double segment - Blue
            self.led_control.doubleSeg(number, self.blue)  # Blue
            
            # Triple segment - Blue
            self.led_control.tripleSeg(number, self.blue)  # Blue
        
        # Bullseye - Red
        self.led_control.bullseye()  # Red

    def process_dart_event(self, event):
        """Process a dart event and update LEDs accordingly."""
        score = event['score']
        multiplier = event['multiplier']
        segment_type = event['segment_type']
        event_id = event['id']
        
        # Calculate blink timing
        start_time = time.time()
        end_time = start_time + self.blink_duration
        
        # Determine segment ID and original color
        if segment_type == 'bullseye':  # Bullseye
            # For bullseye, we'll use a special ID
            segment_id = 'bullseye'
            original_color = self.red  # Red
        elif score in self.led_control.DARTBOARD_MAPPING:
            # Determine original color based on segment type and number
            original_color = None
            
            if segment_type == 'double':
                original_color = self.red if score in self.white_red_segments else self.blue
                segment_id = f'double_{score}'
            elif segment_type == 'triple':
                original_color = self.red if score in self.white_red_segments else self.blue
                segment_id = f'triple_{score}'
            elif segment_type == 'inner_single':
                original_color = self.dim_white if score in self.white_red_segments else self.yellow
                segment_id = f'inner_single_{score}'
            elif segment_type == 'outer_single':
                original_color = self.dim_white if score in self.white_red_segments else self.yellow
                segment_id = f'outer_single_{score}'
            else:
                return
        else:
            return
        
        # Store blinking information
        self.blinking_segments[segment_id] = {
            'start_time': start_time,
            'end_time': end_time,
            'original_color': original_color,
            'score': score,
            'segment_type': segment_type,
            'blink_count': self.blink_count,
            'blinks_completed': 0,
            'current_state': 'off',  # Start in 'off' state so first update turns it on
            'last_toggle': start_time
        }
        
        # Immediately light up the hit segment with first update
        self.update_blinking_segments(True)  # True to force update

    def update_blinking_segments(self, force_update=False):
        """Update any segments that should be blinking."""
        current_time = time.time()
        
        # Process each blinking segment
        to_remove = []
        
        for segment_id, info in self.blinking_segments.items():
            # Check if this segment's blinking period has expired
            if current_time > info['end_time']:
                # Restore original color
                if segment_id == 'bullseye':
                    self.led_control.bullseye(info['original_color'])
                elif 'segment_type' in info:
                    score = info['score']
                    segment_type = info['segment_type']
                    
                    if segment_type == 'double':
                        self.led_control.doubleSeg(score, info['original_color'])
                    elif segment_type == 'triple':
                        self.led_control.tripleSeg(score, info['original_color'])
                    elif segment_type == 'inner_single':
                        self.led_control.innerSingleSeg(score, info['original_color'])
                    elif segment_type == 'outer_single':
                        self.led_control.outerSingleSeg(score, info['original_color'])
                
                # Mark for removal
                to_remove.append(segment_id)
            else:
                # Calculate if we need to toggle the blink state
                blink_interval = 1.0 / (self.blink_frequency * 2)  # Each blink requires two toggles (on, off)
                time_since_toggle = current_time - info['last_toggle']
                
                if force_update or time_since_toggle >= blink_interval:
                    # Time to toggle the state
                    new_state = 'on' if info['current_state'] == 'off' else 'off'
                    
                    # Track completed blinks - a blink is completed when going from on->off
                    if new_state == 'off' and info['current_state'] == 'on':
                        info['blinks_completed'] += 1
                        
                        # If we've completed our blinks but still have time, end early
                        if info['blinks_completed'] >= info['blink_count']:
                            info['end_time'] = current_time
                            continue
                    
                    # Toggle the color based on the new state
                    if new_state == 'on':
                        # Set to green (on state)
                        green_color = (0, 255, 0)  # Bright green
                        
                        if segment_id == 'bullseye':
                            self.led_control.bullseye(green_color)
                        elif 'segment_type' in info:
                            score = info['score']
                            segment_type = info['segment_type']
                            
                            if segment_type == 'double':
                                self.led_control.doubleSeg(score, green_color)
                            elif segment_type == 'triple':
                                self.led_control.tripleSeg(score, green_color)
                            elif segment_type == 'inner_single':
                                self.led_control.innerSingleSeg(score, green_color)
                            elif segment_type == 'outer_single':
                                self.led_control.outerSingleSeg(score, green_color)
                    else:
                        # Set to original color (off state)
                        if segment_id == 'bullseye':
                            self.led_control.bullseye(info['original_color'])
                        elif 'segment_type' in info:
                            score = info['score']
                            segment_type = info['segment_type']
                            
                            if segment_type == 'double':
                                self.led_control.doubleSeg(score, info['original_color'])
                            elif segment_type == 'triple':
                                self.led_control.tripleSeg(score, info['original_color'])
                            elif segment_type == 'inner_single':
                                self.led_control.innerSingleSeg(score, info['original_color'])
                            elif segment_type == 'outer_single':
                                self.led_control.outerSingleSeg(score, info['original_color'])
                    
                    # Update segment info
                    info['current_state'] = new_state
                    info['last_toggle'] = current_time
        
        # Remove expired segments
        for segment_id in to_remove:
            del self.blinking_segments[segment_id]

    def run(self):
        """Main processing loop for the LED controller."""
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
            # Clean up
            self.led_control.clearAll()

def main():
    # You can customize the blinking parameters here
    controller = LEDController(
        blink_duration=3.0,  # Blink for 3 seconds
        blink_count=6        # 6 blinks total
    )
    controller.run()

if __name__ == "__main__":
    main()