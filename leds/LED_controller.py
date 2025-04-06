import sqlite3
import time
from contextlib import contextmanager
from LEDs import LEDs
from datetime import datetime
from LEDs_db_init import initialize_leds_database

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
        # Reset the database on startup
        print("Resetting LEDs database...")
        initialize_leds_database()
        
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.led_control = LEDs()  # Initialize real LED control class
        self.current_mode = None
        self.previous_mode = None  # Track previous mode to detect changes
        self.blinking_segments = {}  # To track segments that should be blinking
        
        # Blinking configuration
        self.blink_duration = blink_duration
        self.blink_count = blink_count
        # Calculate frequency based on duration and count
        self.blink_frequency = blink_count / blink_duration if blink_duration > 0 else 2.0
        
        # Define sets for different LED color schemes in classic mode
        self.white_red_segments = {1, 4, 6, 15, 17, 19, 16, 11, 9, 5}
        self.yellow_blue_segments = {20, 18, 13, 10, 2, 3, 7, 8, 14, 12}
        
        # Cricket segments
        self.cricket_segments = {15, 16, 17, 18, 19, 20, 25}
        
        # Cricket colors
        self.cricket_open_color = (255, 255, 255)  # White - open segments
        self.cricket_player_closed_color = (0, 255, 0)  # Green - segments closed by current player
        self.cricket_other_closed_color = (0, 0, 255)  # Blue - segments closed by other players
        self.cricket_all_closed_color = (255, 0, 0)  # Red - segments closed by all players
        
        # Around the Clock configuration
        self.around_clock_colors = {
            'target': (255, 0, 0),       # Red for target number
            'purple': (255, 0, 255),     # Purple
            'white': (255, 255, 255),    # White
        }
        self.purple_single_segments = {20, 18, 13, 10, 2, 3, 7, 8, 14, 12}  # Numbers with purple singles
        self.white_single_segments = {1, 4, 6, 15, 17, 19, 16, 11, 9, 5}    # Numbers with white singles
        self.current_around_clock_target = 1
        
        # Track cricket game state
        self.cricket_state = {}
        self.current_player = 1
        self.player_count = 4

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
            mode_row = cursor.fetchone()
            
            if mode_row:
                mode = mode_row['mode']
                
                # Normalize mode string for comparison
                normalized_mode = None
                if mode.lower() in ['301', '501', 'classic']:
                    normalized_mode = 'classic'
                elif mode.lower() in ['cricket', 'american_cricket']:
                    normalized_mode = 'cricket'
                elif mode.lower() in ['around_clock', 'around_the_clock']:
                    normalized_mode = 'around_clock'
                else:
                    normalized_mode = 'neutral'  # Default to neutral for unrecognized modes
                
                # Check if this is the first call or the mode has changed
                if self.previous_mode is None or self.previous_mode != normalized_mode:
                    print(f"Game mode: '{normalized_mode}'")
                    self.previous_mode = normalized_mode
                
                return normalized_mode
            else:
                # If no game mode is found in the database
                if self.previous_mode is None or self.previous_mode != 'neutral':
                    print("No game mode found in database, defaulting to neutral mode")
                    self.previous_mode = 'neutral'
                
                return 'neutral'  # Default to neutral if no mode is set

    def get_current_player(self):
        """Get current active player from database."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT current_player, player_count FROM player_state WHERE id = 1")
            state = cursor.fetchone()
            if state:
                self.current_player = state['current_player']
                self.player_count = state['player_count']
                return state['current_player']
            return 1  # Default to player 1 if no state is set

    def get_cricket_state(self):
        """Get cricket game state from database."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT segment, player1_closed, player2_closed, player3_closed, 
                       player4_closed, player5_closed, player6_closed, 
                       player7_closed, player8_closed, all_closed
                FROM cricket_state
            """)
            rows = cursor.fetchall()
            
            cricket_state = {}
            for row in rows:
                segment = row['segment']
                cricket_state[segment] = {
                    'player_closed': {},
                    'all_closed': row['all_closed'] == 1
                }
                
                # Player closed states (up to 8 players)
                for i in range(1, 9):
                    cricket_state[segment]['player_closed'][i] = row[f'player{i}_closed'] == 1
            
            self.cricket_state = cricket_state
            return cricket_state

    def get_around_clock_target(self, player_id):
        """Get the current target number for a player in Around the Clock mode."""
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Check if the table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='around_clock_state'")
                if cursor.fetchone() is None:
                    # Table doesn't exist yet - return default
                    print("Warning: around_clock_state table not found in LEDs database")
                    return 1  # Default to target 1
                
                # Query the table for player's current target
                cursor.execute(
                    'SELECT current_target FROM around_clock_state WHERE player_id = ?',
                    (player_id,)
                )
                row = cursor.fetchone()
                
                if row is None:
                    print(f"No entry for player {player_id} in around_clock_state table, using default target 1")
                    return 1  # Default to target 1
                    
                return row['current_target']
        except Exception as e:
            print(f"Error getting Around the Clock target: {e}")
            return 1  # Default to target 1

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

    def setup_cricket_mode(self):
        """Set up LEDs for cricket mode."""
        # Clear all LEDs first to reset
        self.led_control.clearAll(wait_ms=1)
        
        # Get current cricket state
        self.get_cricket_state()
        
        # Get current player
        self.get_current_player()
        
        # Set up cricket segments with appropriate colors
        for segment in self.cricket_segments:
            # Skip if not in mapping (though bullseye is a special case)
            if segment != 25 and segment not in self.led_control.DARTBOARD_MAPPING:
                continue
            
            # Get segment state
            segment_state = self.cricket_state.get(segment, {
                'player_closed': {self.current_player: False},
                'all_closed': False
            })
            
            # Determine color based on state
            segment_color = self.get_segment_color_for_cricket(segment_state)
            
            # Apply color to all segment parts
            if segment == 25:  # Bullseye
                self.led_control.bullseye(segment_color)
            else:
                # All segments (single, double, triple) get the same color in cricket
                self.led_control.innerSingleSeg(segment, segment_color)
                self.led_control.outerSingleSeg(segment, segment_color)
                self.led_control.doubleSeg(segment, segment_color)
                self.led_control.tripleSeg(segment, segment_color)

    def setup_around_clock_mode(self):
        """Set up LEDs for Around the Clock mode."""
        # Clear all LEDs first to reset
        self.led_control.clearAll(wait_ms=1)
        
        # Get current player's target number
        current_player = self.get_current_player()
        current_target = self.get_around_clock_target(current_player)
        
        # Store the current target for reference
        self.current_around_clock_target = current_target
        
        print(f"Around the Clock: Current player {current_player}, target number {current_target}")
        
        # Define our color sets for around the clock mode
        purple_single_white_double_triple = {20, 18, 13, 10, 2, 3, 7, 8, 14, 12}
        white_single_purple_double_triple = {1, 4, 6, 15, 17, 19, 16, 11, 9, 5}
        
        # Set up colors for each segment
        for number in range(1, 21):
            # Skip if not in mapping
            if number not in self.led_control.DARTBOARD_MAPPING:
                continue
            
            # Check if this is the current target number
            is_target = (number == current_target)
            
            # Set colors based on number group and whether it's the target
            if number in purple_single_white_double_triple:
                # Single segments - Purple (unless it's the target)
                single_color = (255, 0, 0) if is_target else (255, 0, 255)  # Red if target, otherwise Purple
                # Double and triple segments - White (unless it's the target)
                double_triple_color = (255, 0, 0) if is_target else (255, 255, 255)  # Red if target, otherwise White
                
                self.led_control.innerSingleSeg(number, single_color)
                self.led_control.outerSingleSeg(number, single_color)
                self.led_control.doubleSeg(number, double_triple_color)
                self.led_control.tripleSeg(number, double_triple_color)
            else:  # number in white_single_purple_double_triple
                # Single segments - White (unless it's the target)
                single_color = (255, 0, 0) if is_target else (255, 255, 255)  # Red if target, otherwise White
                # Double and triple segments - Purple (unless it's the target)
                double_triple_color = (255, 0, 0) if is_target else (255, 0, 255)  # Red if target, otherwise Purple
                
                self.led_control.innerSingleSeg(number, single_color)
                self.led_control.outerSingleSeg(number, single_color)
                self.led_control.doubleSeg(number, double_triple_color)
                self.led_control.tripleSeg(number, double_triple_color)
        
        # Bullseye - Red if it's the target (for target=21), otherwise Purple
        is_bullseye_target = (current_target == 21)  # 21 represents bullseye in Around the Clock
        bullseye_color = (255, 0, 0) if is_bullseye_target else (255, 0, 255)  # Red if target, otherwise Purple
        self.led_control.bullseye(bullseye_color)

    def get_segment_color_for_cricket(self, segment_state):
        """Determine the color for a cricket segment based on its state."""
        # If closed by all players, return red
        if segment_state.get('all_closed', False):
            return self.cricket_all_closed_color
        
        # If closed by current player, return green
        if segment_state.get('player_closed', {}).get(self.current_player, False):
            return self.cricket_player_closed_color
        
        # If closed by any other player, return blue
        player_closed = segment_state.get('player_closed', {})
        for player, closed in player_closed.items():
            if player != self.current_player and closed:
                return self.cricket_other_closed_color
        
        # Otherwise, return white (open)
        return self.cricket_open_color

    def process_dart_event(self, event):
        """Process a dart event and update LEDs accordingly."""
        score = event['score']
        multiplier = event['multiplier']
        segment_type = event['segment_type']
        event_id = event['id']
        
        # Calculate blink timing
        start_time = time.time()
        end_time = start_time + self.blink_duration
        
        # Determine segment ID and original color based on game mode
        if self.current_mode == 'cricket':
            # For cricket mode, we need to check the segment state
            if segment_type == 'bullseye':  # Bullseye
                # For bullseye, we'll use a special ID
                segment_id = 'bullseye'
                segment_state = self.cricket_state.get(25, {
                    'player_closed': {self.current_player: False},
                    'all_closed': False
                })
                original_color = self.get_segment_color_for_cricket(segment_state)
            elif score in self.cricket_segments and score in self.led_control.DARTBOARD_MAPPING:
                # Determine original color based on cricket state
                segment_state = self.cricket_state.get(score, {
                    'player_closed': {self.current_player: False},
                    'all_closed': False
                })
                original_color = self.get_segment_color_for_cricket(segment_state)
                
                # Set segment ID
                if segment_type == 'double':
                    segment_id = f'double_{score}'
                elif segment_type == 'triple':
                    segment_id = f'triple_{score}'
                elif segment_type == 'inner_single':
                    segment_id = f'inner_single_{score}'
                elif segment_type == 'outer_single':
                    segment_id = f'outer_single_{score}'
                else:
                    return
            else:
                # Non-cricket segment, just use normal blinking
                return self.process_dart_event_classic(event)
        else:
            # For classic mode or around the clock, use the original classic logic
            return self.process_dart_event_classic(event)
        
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

    def process_dart_event_classic(self, event):
        """Process a dart event for classic mode."""
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
            
            # Determine original color based on game mode
            if self.current_mode == 'around_clock':
                # Check if bullseye is the target (21)
                original_color = (255, 0, 0) if self.current_around_clock_target == 21 else (255, 0, 255)
            else:
                # Classic mode - bullseye is red
                original_color = (255, 0, 0)  # Red
                
        elif score in self.led_control.DARTBOARD_MAPPING:
            # Determine original color based on segment type, number, and game mode
            original_color = None
            
            if self.current_mode == 'around_clock':
                # For around the clock, check if this is the target number
                is_target = (score == self.current_around_clock_target)
                
                # Check if score is in the specific number groups
                in_purple_single = score in self.purple_single_segments
                
                if segment_type == 'double':
                    # Double segments: White for purple singles, Purple for white singles
                    # But if it's the target, then Red
                    if is_target:
                        original_color = (255, 0, 0)  # Red for target
                    else:
                        original_color = (255, 255, 255) if in_purple_single else (255, 0, 255)  # White/Purple
                    segment_id = f'double_{score}'
                elif segment_type == 'triple':
                    # Triple segments: White for purple singles, Purple for white singles
                    # But if it's the target, then Red
                    if is_target:
                        original_color = (255, 0, 0)  # Red for target
                    else:
                        original_color = (255, 255, 255) if in_purple_single else (255, 0, 255)  # White/Purple
                    segment_id = f'triple_{score}'
                elif segment_type == 'inner_single' or segment_type == 'outer_single':
                    # Single segments: Purple for purple singles, White for white singles
                    # But if it's the target, then Red
                    if is_target:
                        original_color = (255, 0, 0)  # Red for target
                    else:
                        original_color = (255, 0, 255) if in_purple_single else (255, 255, 255)  # Purple/White
                    segment_id = f'{segment_type}_{score}'
                else:
                    return
            else:
                # Classic mode - original classic colors
                if segment_type == 'double':
                    original_color = (255, 0, 0) if score in self.white_red_segments else (0, 0, 255)
                    segment_id = f'double_{score}'
                elif segment_type == 'triple':
                    original_color = (255, 0, 0) if score in self.white_red_segments else (0, 0, 255)
                    segment_id = f'triple_{score}'
                elif segment_type == 'inner_single':
                    original_color = (255, 255, 255) if score in self.white_red_segments else (255, 255, 0)
                    segment_id = f'inner_single_{score}'
                elif segment_type == 'outer_single':
                    original_color = (255, 255, 255) if score in self.white_red_segments else (255, 255, 0)
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
            # Start in neutral waiting state
            print("Starting LED controller in neutral waiting state")
            self.setup_neutral_mode()
            self.current_mode = 'neutral'
            
            print("LED Controller running. Press Ctrl+C to stop...")
            
            # Main processing loop
            while True:
                # Check for game mode changes
                new_mode = self.get_current_mode()
                
                if new_mode != self.current_mode:
                    print(f"Game mode changed from '{self.current_mode}' to '{new_mode}'")
                    self.current_mode = new_mode
                    
                    # Update LED pattern based on new mode
                    if self.current_mode == 'classic':
                        self.setup_classic_mode()
                    elif self.current_mode == 'cricket':
                        self.setup_cricket_mode()
                    elif self.current_mode == 'around_clock':
                        self.setup_around_clock_mode()
                    elif self.current_mode == 'neutral':
                        self.setup_neutral_mode()
                
                # If in cricket mode, check for player/state changes
                if self.current_mode == 'cricket':
                    old_player = self.current_player
                    self.get_current_player()
                    
                    # If player changed, update the display
                    if old_player != self.current_player:
                        print(f"Current player changed from {old_player} to {self.current_player}")
                        self.setup_cricket_mode()
                    else:
                        # Check for cricket state changes
                        old_state = self.cricket_state.copy()
                        self.get_cricket_state()
                        
                        # If state changed, update the display
                        if old_state != self.cricket_state:
                            print("Cricket state changed, updating display")
                            self.setup_cricket_mode()
                # If in around_clock mode, check for player/target changes
                elif self.current_mode == 'around_clock':
                    old_player = self.current_player
                    old_target = getattr(self, 'current_around_clock_target', 1)
                    self.get_current_player()
                    
                    # If player changed, update the display
                    if old_player != self.current_player:
                        print(f"Current player changed from {old_player} to {self.current_player}")
                        self.setup_around_clock_mode()
                    else:
                        try:
                            # Check for target changes
                            current_target = self.get_around_clock_target(self.current_player)
                            if old_target != current_target:
                                print(f"Target changed from {old_target} to {current_target}")
                                self.current_around_clock_target = current_target
                                self.setup_around_clock_mode()
                        except Exception as e:
                            print(f"Error checking target: {e}")
                            # Continue with current state if there's an error
                
                # Get new dart events
                events = self.get_new_dart_events()
                
                # Process each new event
                for event in events:
                    print(f"\nProcessing dart event: score={event['score']}, multiplier={event['multiplier']}, segment_type={event['segment_type']}")
                    self.process_dart_event(event)
                    
                    # Print board state after processing an event if MockLEDs
                    if hasattr(self.led_control, 'print_board_state'):
                        self.led_control.print_board_state()
                
                # Update blinking segments
                self.update_blinking_segments()
                
                # Sleep for a bit before next poll
                time.sleep(self.poll_interval)
                
        except KeyboardInterrupt:
            print("\nLED Controller stopped.")
            # Clean up
            self.led_control.clearAll()
            
            # Print final state and summary if MockLEDs
            if hasattr(self.led_control, 'print_board_state'):
                self.led_control.print_board_state()
            if hasattr(self.led_control, 'print_blinking_summary'):
                self.led_control.print_blinking_summary()

    def setup_neutral_mode(self):
        """Set up LEDs for neutral waiting state."""
        print("Setting up neutral waiting state...")
        
        # Clear all LEDs first to reset
        self.led_control.clearAll(wait_ms=1)
        
        # Apply neutral waiting state colors to all segments
        for number in range(1, 21):  # All dartboard numbers 1-20
            if number not in self.led_control.DARTBOARD_MAPPING:
                continue
                
            # Inner single segments: Blue
            self.led_control.innerSingleSeg(number, (0, 0, 255))  # Blue
            
            # Triple segments: Green
            self.led_control.tripleSeg(number, (0, 255, 0))  # Green
            
            # Outer single segments: Yellow
            self.led_control.outerSingleSeg(number, (255, 255, 0))  # Yellow
            
            # Double segments: Red
            self.led_control.doubleSeg(number, (255, 0, 0))  # Red
        
        # Bullseye: Purple
        self.led_control.bullseye((255, 0, 255))  # Purple
        
        # Display board state if MockLEDs is being used
        if hasattr(self.led_control, 'print_board_state'):
            self.led_control.print_board_state()

def main():
    # You can customize the blinking parameters here
    controller = LEDController(
        blink_duration=3.0,  # Blink for 3 seconds
        blink_count=6        # 6 blinks total
    )
    controller.run()

if __name__ == "__main__":
    main()