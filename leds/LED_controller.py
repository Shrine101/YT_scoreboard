import sqlite3
import time
from contextlib import contextmanager
from LEDs import LEDs
from datetime import datetime
from LEDs_db_init import initialize_leds_database
from moving_target_db_init import initialize_moving_target_database

class LEDController:
    def __init__(self, db_path='LEDs.db', poll_interval=0.5, 
                 blink_duration=2, blink_count=4):
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
        
        # Initialize moving target database
        initialize_moving_target_database()
        
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
        self.cricket_open_color = (100, 100, 100)  # White - open segments
        self.cricket_player_closed_color = (0, 100, 0)  # Green - segments closed by current player
        self.cricket_other_closed_color = (0, 0, 100)  # Blue - segments closed by other players
        self.cricket_all_closed_color = (100, 0, 0)  # Red - segments closed by all players
        
        # Around the Clock configuration
        self.around_clock_colors = {
            'target': (100, 0, 0),       # Red for target number
            'purple': (100, 0, 100),     # Purple
            'white': (100, 100, 100),    # White
        }
        self.purple_single_segments = {20, 18, 13, 10, 2, 3, 7, 8, 14, 12}  # Numbers with purple singles
        self.white_single_segments = {1, 4, 6, 15, 17, 19, 16, 11, 9, 5}    # Numbers with white singles
        self.current_around_clock_target = 1
        
        # Moving target related attributes - Updated with clockwise sequence
        self.moving_target_db_path = 'moving_target.db'
        self.target_move_interval = 3.0  # seconds
        self.last_target_move_time = time.time()
        # Clockwise sequence around dartboard
        self.moving_target_sequence = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]
        self.current_target_index = 0
        self.current_target_number = self.moving_target_sequence[0]  # Initialize to first number (20)
        self.previous_target_number = None  # Track previous target for seamless transitions
        
        # Moving target colors
        self.BLUE_TARGET = (0, 0, 100)  # Blue color for active target
        self.GREEN_HIT = (0, 100, 0)    # Green for successful hit
        self.RED_MISS = (100, 0, 0)     # Red for missed target
        
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

    @contextmanager
    def get_moving_target_connection(self):
        """Get a connection to the Moving Target database."""
        conn = sqlite3.connect(self.moving_target_db_path)
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
                elif mode.lower() in ['moving_target']:
                    normalized_mode = 'moving_target'
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

    def update_moving_target(self):
        """Update the moving target by changing which segments are active."""
        current_time = time.time()
        
        # Don't move the target if there are any blinking segments (animation in progress)
        if self.blinking_segments:
            # Reset the timer to prevent immediate movement after animation
            self.last_target_move_time = current_time
            return
        
        # Check if it's time to move the target
        if current_time - self.last_target_move_time >= self.target_move_interval:
            # Move to the next target
            self.current_target_index = (self.current_target_index + 1) % len(self.moving_target_sequence)
            new_target = self.moving_target_sequence[self.current_target_index]
            
            # Store previous target for transition
            self.previous_target_number = self.current_target_number
            self.current_target_number = new_target
            
            # Update the database
            with self.get_moving_target_connection() as conn:
                cursor = conn.cursor()
                
                # Update the target state
                cursor.execute('''
                    UPDATE target_state 
                    SET current_target = ?, last_moved_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                ''', (new_target,))
                
                # Clear existing active segments
                cursor.execute("DELETE FROM active_segments")
                
                # Add new active segments for the current target number
                # Add all segments (double, triple, inner and outer singles)
                segment_types = ['double', 'triple', 'inner_single', 'outer_single']
                for segment_type in segment_types:
                    cursor.execute('''
                        INSERT INTO active_segments (segment_number, segment_type)
                        VALUES (?, ?)
                    ''', (new_target, segment_type))
                
                conn.commit()
            
            # Update the LED display to show the new target - with seamless transition
            self.update_target_position(new_target)
            
            # Update the last move time
            self.last_target_move_time = current_time
            print(f"Moved target to number {new_target}")

    def update_target_position(self, target_number):
        """
        Update the target position with seamless transition between numbers.
        First turns on new target, then optionally turns off previous target.
        """
        # Check if the target is valid
        if target_number not in self.led_control.DARTBOARD_MAPPING:
            print(f"Error: Target number {target_number} not in dartboard mapping")
            return
        
        # Define blue target color
        blue_color = self.BLUE_TARGET  # (0, 0, 100)
        
        # First, turn ON the new target segments with minimal wait time
        # This ensures the new target appears immediately
        self.led_control.doubleSeg(target_number, blue_color, wait_ms=1)
        self.led_control.tripleSeg(target_number, blue_color, wait_ms=1)
        self.led_control.innerSingleSeg(target_number, blue_color, wait_ms=1)
        self.led_control.outerSingleSeg(target_number, blue_color, wait_ms=1)
        
        # If there was a previous target that's different from current one, turn it off
        if self.previous_target_number is not None and self.previous_target_number != target_number:
            # Turn off previous target with black color (0,0,0)
            black_color = (0, 0, 0)
            prev_num = self.previous_target_number
            
            # Only if the previous number exists and is different
            if prev_num in self.led_control.DARTBOARD_MAPPING:
                self.led_control.doubleSeg(prev_num, black_color, wait_ms=1)
                self.led_control.tripleSeg(prev_num, black_color, wait_ms=1)
                self.led_control.innerSingleSeg(prev_num, black_color, wait_ms=1)
                self.led_control.outerSingleSeg(prev_num, black_color, wait_ms=1)
        
        print(f"Target updated to number {target_number} with blue color")

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
        """Set up LEDs for classic mode with red and blue segments."""
        # Clear all LEDs first to reset
        self.led_control.clearAll(wait_ms=1)
        
        # Define colors
        RED = (100, 0, 0)
        BLUE = (0, 0, 100)
        
        # Set up LEDs for all numbers 1-20
        for number in range(1, 21):
            if number not in self.led_control.DARTBOARD_MAPPING:
                continue
                
            # Determine the colors based on the number
            if number in [20, 18, 13, 10, 2, 3, 7, 8, 14, 12]:
                # These numbers have RED singles and BLUE doubles/triples
                single_color = RED
                ring_color = BLUE
            else:  # numbers 1, 4, 6, 15, 17, 19, 16, 11, 9, 5
                # These numbers have BLUE singles and RED doubles/triples
                single_color = BLUE
                ring_color = RED
                
            # Set single segments
            self.led_control.innerSingleSeg(number, single_color)
            self.led_control.outerSingleSeg(number, single_color)
            
            # Set double and triple segments
            self.led_control.doubleSeg(number, ring_color)
            self.led_control.tripleSeg(number, ring_color)
        
        # Bullseye remains off (no LEDs)
        print("Classic mode set up with custom red and blue segments")

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
        
        # Only light up the current target number, all other LEDs remain off
        if current_target <= 20:  # Regular numbers 1-20
            # For the target, light up all its segments in red
            self.led_control.innerSingleSeg(current_target, (100, 0, 0))  # Red
            self.led_control.outerSingleSeg(current_target, (100, 0, 0))  # Red
            self.led_control.doubleSeg(current_target, (100, 0, 0))  # Red
            self.led_control.tripleSeg(current_target, (100, 0, 0))  # Red
        elif current_target == 21:  # Bullseye (represented as 21)
            # Light up only the bullseye in red
            self.led_control.bullseye((100, 0, 0))  # Red

    def setup_moving_target_mode(self, target_number=None):
        """Set up LEDs for moving target mode."""
        # Clear all LEDs first to reset
        self.led_control.clearAll(wait_ms=1)
        
        # If no target number specified, get it from the database
        if target_number is None:
            with self.get_moving_target_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT current_target FROM target_state WHERE id = 1")
                state = cursor.fetchone()
                if state:
                    target_number = state['current_target']
                else:
                    # Default to 20 if no state found
                    target_number = 20
    
        # Store current target for hit detection
        self.current_target_number = target_number
        self.previous_target_number = None  # Reset previous target
        
        print(f"Setting up Moving Target mode with target number {target_number}")
        
        # Make sure target number is in the mapping
        if target_number not in self.led_control.DARTBOARD_MAPPING:
            print(f"Error: Target number {target_number} not in dartboard mapping")
            return
        
        # Light up all segments for the target number with blue color
        blue_color = self.BLUE_TARGET  # (0, 0, 100)
        
        # Light up all segments of the target with blue color
        self.led_control.doubleSeg(target_number, blue_color, wait_ms=1)
        self.led_control.tripleSeg(target_number, blue_color, wait_ms=1)
        self.led_control.innerSingleSeg(target_number, blue_color, wait_ms=1)
        self.led_control.outerSingleSeg(target_number, blue_color, wait_ms=1)

    def setup_neutral_mode(self):
        """Set up LEDs for neutral waiting state."""
        print("Setting up neutral waiting state...")
        
        # Clear all LEDs first to reset
        self.led_control.clearAll(wait_ms=1)
        
        # Apply neutral waiting state colors only to double, triple, and bullseye
        for number in range(1, 21):  # All dartboard numbers 1-20
            if number not in self.led_control.DARTBOARD_MAPPING:
                continue
                
            # Keep triple segments: Green
            self.led_control.tripleSeg(number, (0, 100, 0))  # Green
            
            # Keep double segments: Red
            self.led_control.doubleSeg(number, (100, 0, 0))  # Red
            
            # Inner and outer single segments are now left off
        
        # Bullseye: Purple
        self.led_control.bullseye((100, 0, 100))  # Purple
        
        # Display board state if MockLEDs is being used
        if hasattr(self.led_control, 'print_board_state'):
            self.led_control.print_board_state()

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

    def get_active_target_segments(self):
        """Get the currently active target segments from the moving_target database"""
        try:
            with self.get_moving_target_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT segment_number, segment_type FROM active_segments WHERE active = 1')
                segments = cursor.fetchall()
                
                # Convert to a list of tuples (segment_number, segment_type)
                active_segments = [(seg['segment_number'], seg['segment_type']) for seg in segments]
                
                return active_segments
        except Exception as e:
            print(f"Error getting active target segments: {e}")
            return []  # Return empty list on error

    def check_if_hit_target(self, score, segment_type):
        """Check if the throw hit the current active target"""
        active_segments = self.get_active_target_segments()
        
        # Check if the thrown dart matches any active segment
        is_hit = (score, segment_type) in active_segments
        
        print(f"Target check: {score} {segment_type} - {'HIT' if is_hit else 'MISS'}")
        return is_hit

    def process_dart_event(self, event):
        """Process a dart event and update LEDs accordingly."""
        score = event['score']
        multiplier = event['multiplier']
        segment_type = event['segment_type']
        event_id = event['id']
        
        # Check for hit/miss information in segment_type (for Moving Target mode)
        # Format: "segment_type_target_hit" or "segment_type_target_miss"
        hit_miss_info = segment_type.split('_')
        
        # For Moving Target mode with hit/miss info
        if self.current_mode == 'moving_target' and len(hit_miss_info) >= 3 and hit_miss_info[-2] == 'target':
            target_index = hit_miss_info.index('target')
            base_segment_type = '_'.join(hit_miss_info[:target_index])
            is_hit = hit_miss_info[-1] == 'hit'
            
            # Calculate blink timing
            start_time = time.time()
            end_time = start_time + self.blink_duration
            
            if is_hit:
                # If it's a hit, blink all segments of the current target in green
                print(f"Target HIT! Blinking target {self.current_target_number} in green")
                self._setup_target_hit_animation(self.current_target_number, start_time, end_time)
            else:
                # If it's a miss, only blink the hit segment in red
                print(f"Target MISS! Blinking hit segment {score} ({base_segment_type}) in red")
                self._setup_target_miss_animation(score, base_segment_type, start_time, end_time)
        else:
            # For other game modes, use the existing logic
            return self.process_dart_event_classic(event)

    def _setup_target_hit_animation(self, target_number, start_time, end_time):
        """Setup blinking animation for successful target hit (green)."""
        if target_number not in self.led_control.DARTBOARD_MAPPING:
            print(f"Error: Target number {target_number} not in dartboard mapping")
            return
        
        # Set up blinking for all segments of the target
        segment_types = ['double', 'triple', 'inner_single', 'outer_single']
        
        # First, turn all target segments to green immediately for visual feedback
        green_color = self.GREEN_HIT  # (0, 100, 0)
        
        # Turn target segments green immediately
        self.led_control.doubleSeg(target_number, green_color, wait_ms=1)
        self.led_control.tripleSeg(target_number, green_color, wait_ms=1)
        self.led_control.innerSingleSeg(target_number, green_color, wait_ms=1)
        self.led_control.outerSingleSeg(target_number, green_color, wait_ms=1)
        
        # Set up blinking for all segments
        for segment_type in segment_types:
            segment_id = f'{segment_type}_{target_number}'
            
            self.blinking_segments[segment_id] = {
                'start_time': start_time,
                'end_time': end_time,
                'original_color': self.BLUE_TARGET,  # Blue (original target color)
                'blink_color': green_color,
                'score': target_number,
                'segment_type': segment_type,
                'blink_count': self.blink_count,
                'blinks_completed': 0,
                'current_state': 'on',  # Start in 'on' state since we already turned it on
                'last_toggle': start_time
            }
        
        # Force an update to continue the blinking sequence
        self.update_blinking_segments(True)

    def _setup_target_miss_animation(self, score, segment_type, start_time, end_time):
        """Setup blinking animation for missed target (hit segment blinks red)."""
        # Set hit segment to blink red
        if segment_type == 'bullseye':
            segment_id = 'bullseye'
        elif score in self.led_control.DARTBOARD_MAPPING:
            segment_id = f'{segment_type}_{score}'
        else:
            print(f"Error: Score {score} not in dartboard mapping")
            return
        
        # Red color for misses
        red_color = self.RED_MISS  # (100, 0, 0)
        
        # First, turn the hit segment red immediately for visual feedback
        if segment_type == 'double':
            self.led_control.doubleSeg(score, red_color, wait_ms=1)
        elif segment_type == 'triple':
            self.led_control.tripleSeg(score, red_color, wait_ms=1)
        elif segment_type == 'inner_single':
            self.led_control.innerSingleSeg(score, red_color, wait_ms=1)
        elif segment_type == 'outer_single':
            self.led_control.outerSingleSeg(score, red_color, wait_ms=1)
        elif segment_type == 'bullseye':
            # Handle bullseye if your LED controller supports it
            if hasattr(self.led_control, 'bullseye'):
                self.led_control.bullseye(red_color, wait_ms=1)
        
        # Determine the original color of this segment (off/black for most segments)
        original_color = (0, 0, 0)  # Default black/off
        
        # Create the blinking entry
        self.blinking_segments[segment_id] = {
            'start_time': start_time,
            'end_time': end_time,
            'original_color': original_color,
            'blink_color': red_color,
            'score': score,
            'segment_type': segment_type,
            'blink_count': self.blink_count,
            'blinks_completed': 0,
            'current_state': 'on',  # Start in 'on' state since we already turned it red
            'last_toggle': start_time
        }
        
        # Force an update to continue the blinking sequence
        self.update_blinking_segments(True)

    def process_dart_event_classic(self, event):
        """Process a dart event for classic mode."""
        score = event['score']
        multiplier = event['multiplier']
        segment_type = event['segment_type']
        event_id = event['id']
        
        # Calculate blink timing
        start_time = time.time()
        end_time = start_time + self.blink_duration
        
        # Special case for bullseye
        if segment_type == 'bullseye':
            print("Bullseye hit! All segments will blink green simultaneously.")
            # Create a special bullseye master record to track synchronized blinking
            master_record = {
                'start_time': start_time,
                'end_time': end_time,
                'blink_count': self.blink_count,
                'blinks_completed': 0,
                'current_state': 'off',  # Start in 'off' state
                'last_toggle': start_time,
                'blink_color': (0, 100, 0),  # Green for blinking
                'is_bullseye_master': True  # Mark this as the master record
            }
            
            self.blinking_segments['bullseye_master'] = master_record
            
            # First, turn all LEDs to their original colors to ensure a clean start
            for number in range(1, 21):
                if number not in self.led_control.DARTBOARD_MAPPING:
                    continue
                    
                # Get the original colors for this number
                if number in [20, 18, 13, 10, 2, 3, 7, 8, 14, 12]:
                    single_color = (100, 0, 0)  # RED
                    ring_color = (0, 0, 100)    # BLUE
                else:  # numbers 1, 4, 6, 15, 17, 19, 16, 11, 9, 5
                    single_color = (0, 0, 100)  # BLUE
                    ring_color = (100, 0, 0)    # RED
                
                # Apply original colors
                self.led_control.innerSingleSeg(number, single_color)
                self.led_control.outerSingleSeg(number, single_color)
                self.led_control.doubleSeg(number, ring_color)
                self.led_control.tripleSeg(number, ring_color)
                
                # Set up segment records with references to the master
                self.blinking_segments[f'inner_single_{number}_bull'] = {
                    'master_ref': 'bullseye_master',
                    'original_color': single_color,
                    'score': number,
                    'segment_type': 'inner_single',
                    'blink_color': (0, 100, 0)  # Green for blinking
                }
                
                self.blinking_segments[f'outer_single_{number}_bull'] = {
                    'master_ref': 'bullseye_master',
                    'original_color': single_color,
                    'score': number,
                    'segment_type': 'outer_single',
                    'blink_color': (0, 100, 0)  # Green for blinking
                }
                
                self.blinking_segments[f'double_{number}_bull'] = {
                    'master_ref': 'bullseye_master',
                    'original_color': ring_color,
                    'score': number,
                    'segment_type': 'double',
                    'blink_color': (0, 100, 0)  # Green for blinking
                }
                
                self.blinking_segments[f'triple_{number}_bull'] = {
                    'master_ref': 'bullseye_master',
                    'original_color': ring_color,
                    'score': number,
                    'segment_type': 'triple',
                    'blink_color': (0, 100, 0)  # Green for blinking
                }
            
            # Now, turn all LEDs green for the first "on" state
            for number in range(1, 21):
                if number not in self.led_control.DARTBOARD_MAPPING:
                    continue
                
                # Turn all segments to green for the first blink
                self.led_control.innerSingleSeg(number, (0, 100, 0))
                self.led_control.outerSingleSeg(number, (0, 100, 0))
                self.led_control.doubleSeg(number, (0, 100, 0))
                self.led_control.tripleSeg(number, (0, 100, 0))
            
            # Update master record to "on" state since we just turned everything green
            master_record['current_state'] = 'on'
            
            # Immediately start blinking cycle
            # We'll need to force the first toggle to make it start
            self.update_blinking_segments(True)  # Force update
            return
        
        # Normal case (not bullseye)
        # Determine segment ID and original color
        if score in self.led_control.DARTBOARD_MAPPING:
            # Determine segment ID
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
            
            # Determine original color based on number and segment type
            if score in [20, 18, 13, 10, 2, 3, 7, 8, 14, 12]:
                if segment_type in ['double', 'triple']:
                    original_color = (0, 0, 100)  # BLUE
                else:  # inner or outer single
                    original_color = (100, 0, 0)  # RED
            else:  # numbers 1, 4, 6, 15, 17, 19, 16, 11, 9, 5
                if segment_type in ['double', 'triple']:
                    original_color = (100, 0, 0)  # RED
                else:  # inner or outer single
                    original_color = (0, 0, 100)  # BLUE
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
            'current_state': 'off',  # Start in 'off' state
            'last_toggle': start_time,
            'blink_color': (0, 100, 0)  # Always use green for blinking
        }
        
        # Immediately light up the hit segment with first update
        self.update_blinking_segments(True)  # Force update
        print(f"Segment hit: {score} {segment_type} - will blink green and return to original color")

    def update_blinking_segments(self, force_update=False):
        """Update any segments that should be blinking."""
        current_time = time.time()
        
        # Process each blinking segment
        to_remove = []
        
        # First check for bullseye master record which controls synchronized blinking
        if 'bullseye_master' in self.blinking_segments:
            master = self.blinking_segments['bullseye_master']
            
            # Check if the bullseye blinking period has expired
            if current_time > master['end_time']:
                print("Bullseye blinking complete, restoring original colors")
                
                # Find all segments controlled by this master
                bullseye_segments = [k for k in self.blinking_segments.keys() if k.endswith('_bull')]
                
                # Restore all segments to their original colors
                for segment_id in bullseye_segments:
                    info = self.blinking_segments[segment_id]
                    score = info['score']
                    segment_type = info['segment_type']
                    original_color = info['original_color']
                    
                    if segment_type == 'double':
                        self.led_control.doubleSeg(score, original_color)
                    elif segment_type == 'triple':
                        self.led_control.tripleSeg(score, original_color)
                    elif segment_type == 'inner_single':
                        self.led_control.innerSingleSeg(score, original_color)
                    elif segment_type == 'outer_single':
                        self.led_control.outerSingleSeg(score, original_color)
                    
                    # Mark for removal
                    to_remove.append(segment_id)
                
                # Also remove the master record
                to_remove.append('bullseye_master')
            else:
                # Calculate if we need to toggle the blink state for all segments
                blink_interval = 1.0 / (self.blink_frequency * 2)  # Each blink requires two toggles (on, off)
                time_since_toggle = current_time - master['last_toggle']
                
                if force_update or time_since_toggle >= blink_interval:
                    # Time to toggle the state for all segments
                    new_state = 'on' if master['current_state'] == 'off' else 'off'
                    
                    # Track completed blinks - a blink is completed when going from on->off
                    if new_state == 'off' and master['current_state'] == 'on':
                        master['blinks_completed'] += 1
                        
                        # If we've completed our blinks but still have time, end early
                        if master['blinks_completed'] >= master['blink_count']:
                            master['end_time'] = current_time
                            return  # Skip the rest of the processing
                    
                    # Apply the same state to all segments
                    for number in range(1, 21):
                        if number not in self.led_control.DARTBOARD_MAPPING:
                            continue
                            
                        if new_state == 'on':
                            # Turn all segments green
                            self.led_control.innerSingleSeg(number, (0, 100, 0))
                            self.led_control.outerSingleSeg(number, (0, 100, 0))
                            self.led_control.doubleSeg(number, (0, 100, 0))
                            self.led_control.tripleSeg(number, (0, 100, 0))
                        else:
                            # Restore original colors during "off" part of the blink
                            # Get the original colors for this number
                            if number in [20, 18, 13, 10, 2, 3, 7, 8, 14, 12]:
                                single_color = (100, 0, 0)  # RED
                                ring_color = (0, 0, 100)    # BLUE
                            else:  # numbers 1, 4, 6, 15, 17, 19, 16, 11, 9, 5
                                single_color = (0, 0, 100)  # BLUE
                                ring_color = (100, 0, 0)    # RED
                                
                            # Apply original colors
                            self.led_control.innerSingleSeg(number, single_color)
                            self.led_control.outerSingleSeg(number, single_color)
                            self.led_control.doubleSeg(number, ring_color)
                            self.led_control.tripleSeg(number, ring_color)
                    
                    # Update master record
                    master['current_state'] = new_state
                    master['last_toggle'] = current_time
                    
                    # Print status for debugging
                    if new_state == 'on':
                        print(f"Bullseye blink: All segments ON (green) - Blink {master['blinks_completed'] + 1}/{master['blink_count']}")
                    else:
                        print(f"Bullseye blink: All segments OFF (original colors)")
                
                # Skip processing other segments since bullseye master is active
                return
        
        # Process regular blinking segments (when no bullseye master is active)
        for segment_id, info in self.blinking_segments.items():
            # Skip segments controlled by bullseye master and the master itself
            if segment_id == 'bullseye_master' or segment_id.endswith('_bull') or 'master_ref' in info:
                continue
                
            # Check if this segment's blinking period has expired
            if 'end_time' in info and current_time > info['end_time']:
                if self.current_mode == 'classic':
                    # In classic mode, restore to original color (red or blue) when done blinking
                    if segment_id == 'bullseye':
                        # Bullseye has no LEDs in classic mode, so do nothing
                        pass
                    elif 'segment_type' in info:
                        score = info['score']
                        segment_type = info['segment_type']
                        original_color = info['original_color']
                        
                        if segment_type == 'double':
                            self.led_control.doubleSeg(score, original_color)
                        elif segment_type == 'triple':
                            self.led_control.tripleSeg(score, original_color)
                        elif segment_type == 'inner_single':
                            self.led_control.innerSingleSeg(score, original_color)
                        elif segment_type == 'outer_single':
                            self.led_control.outerSingleSeg(score, original_color)
                elif self.current_mode == 'moving_target':
                    # For moving target mode, when animation ends:
                    # If hit segment is the target, restore it to blue
                    # If hit segment is not the target, turn it off
                    if segment_id.startswith(('double_', 'triple_', 'inner_single_', 'outer_single_')):
                        segment_parts = segment_id.rsplit('_', 1)
                        segment_type = segment_parts[0]
                        score = int(segment_parts[1])

                        if score == self.current_target_number:
                            # This is the target - set back to blue
                            blue_color = self.BLUE_TARGET  # (0, 0, 100)
                            if segment_type == 'double':
                                self.led_control.doubleSeg(score, blue_color)
                            elif segment_type == 'triple':
                                self.led_control.tripleSeg(score, blue_color)
                            elif segment_type == 'inner_single':
                                self.led_control.innerSingleSeg(score, blue_color)
                            elif segment_type == 'outer_single':
                                self.led_control.outerSingleSeg(score, blue_color)
                        else:
                            # Not the target - turn it off (black)
                            if segment_type == 'double':
                                self.led_control.doubleSeg(score, (0, 0, 0))
                            elif segment_type == 'triple':
                                self.led_control.tripleSeg(score, (0, 0, 0))
                            elif segment_type == 'inner_single':
                                self.led_control.innerSingleSeg(score, (0, 0, 0))
                            elif segment_type == 'outer_single':
                                self.led_control.outerSingleSeg(score, (0, 0, 0))
                    elif segment_id == 'bullseye':
                        # Handle bullseye if needed
                        if hasattr(self.led_control, 'bullseye'):
                            self.led_control.bullseye((0, 0, 0))  # Turn off bullseye
                else:
                    # For other modes, restore original color
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
                # Make sure required fields exist
                if 'last_toggle' not in info or 'current_state' not in info:
                    continue
                    
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
                        # In classic mode, always use green for blinking ON state
                        if self.current_mode == 'classic':
                            blink_color = (0, 100, 0)  # Green
                        else:
                            # For other modes, use custom blink color if set, otherwise green
                            blink_color = info.get('blink_color', (0, 100, 0))
                        
                        if segment_id == 'bullseye':
                            if self.current_mode == 'classic':
                                # Bullseye has no LEDs in classic mode, so do nothing for bullseye itself
                                pass
                            else:
                                self.led_control.bullseye(blink_color)
                        elif 'segment_type' in info:
                            score = info['score']
                            segment_type = info['segment_type']
                            
                            if segment_type == 'double':
                                self.led_control.doubleSeg(score, blink_color)
                            elif segment_type == 'triple':
                                self.led_control.tripleSeg(score, blink_color)
                            elif segment_type == 'inner_single':
                                self.led_control.innerSingleSeg(score, blink_color)
                            elif segment_type == 'outer_single':
                                self.led_control.outerSingleSeg(score, blink_color)
                    else:
                        # For OFF state in classic mode, use original color for the off state of the blink
                        if self.current_mode == 'classic':
                            if segment_id == 'bullseye':
                                # Bullseye has no LEDs in classic mode, so do nothing
                                pass
                            elif 'segment_type' in info:
                                score = info['score']
                                segment_type = info['segment_type']
                                original_color = info['original_color']
                                
                                if segment_type == 'double':
                                    self.led_control.doubleSeg(score, original_color)
                                elif segment_type == 'triple':
                                    self.led_control.tripleSeg(score, original_color)
                                elif segment_type == 'inner_single':
                                    self.led_control.innerSingleSeg(score, original_color)
                                elif segment_type == 'outer_single':
                                    self.led_control.outerSingleSeg(score, original_color)
                        else:
                            # For other modes, use original color for OFF state
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
                    elif self.current_mode == 'moving_target':
                        self.setup_moving_target_mode()
                    elif self.current_mode == 'neutral':
                        self.setup_neutral_mode()
                
                # Handle moving target mode updates - Only update if we're in moving target mode and no animations
                if self.current_mode == 'moving_target' and not self.blinking_segments:
                    self.update_moving_target()
                
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

def main():
    # You can customize the blinking parameters here
    controller = LEDController(
        blink_duration=3.0,  # Blink for 3 seconds
        blink_count=6        # 6 blinks total
    )
    controller.run()

if __name__ == "__main__":
    main()
