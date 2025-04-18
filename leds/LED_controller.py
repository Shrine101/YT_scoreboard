import sqlite3
import time
from contextlib import contextmanager
from LEDs import LEDs
from datetime import datetime
from LEDs_db_init import initialize_leds_database
from moving_target_db_init import initialize_moving_target_database

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
        
        # Moving target related attributes
        self.moving_target_db_path = 'moving_target.db'
        self.target_move_interval = 3.0  # seconds
        self.last_target_move_time = time.time()
        self.moving_target_sequence = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]
        self.current_target_index = 0
        
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
            
            # Update the LED display to show the new target
            self.setup_moving_target_mode(new_target)
            
            # Update the last move time
            self.last_target_move_time = current_time
            print(f"Moved target to number {new_target}")

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
        
        # In classic mode, we now keep all LEDs off until hit by a dart
        # No LED segments are lit when the game starts

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
            self.led_control.innerSingleSeg(current_target, (255, 0, 0))  # Red
            self.led_control.outerSingleSeg(current_target, (255, 0, 0))  # Red
            self.led_control.doubleSeg(current_target, (255, 0, 0))  # Red
            self.led_control.tripleSeg(current_target, (255, 0, 0))  # Red
        elif current_target == 21:  # Bullseye (represented as 21)
            # Light up only the bullseye in red
            self.led_control.bullseye((255, 0, 0))  # Red

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
    
        print(f"Setting up Moving Target mode with target number {target_number}")
        
        # Make sure target number is in the mapping
        if target_number not in self.led_control.DARTBOARD_MAPPING:
            print(f"Error: Target number {target_number} not in dartboard mapping")
            return
        
        # Make all segments white (as requested)
        white_color = (255, 255, 255)  # White
        
        # Light up all segments for the target number with white color
        self.led_control.doubleSeg(target_number, white_color)
        self.led_control.tripleSeg(target_number, white_color)
        self.led_control.innerSingleSeg(target_number, white_color)
        self.led_control.outerSingleSeg(target_number, white_color)

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
            self.led_control.tripleSeg(number, (0, 255, 0))  # Green
            
            # Keep double segments: Red
            self.led_control.doubleSeg(number, (255, 0, 0))  # Red
            
            # Inner and outer single segments are now left off
        
        # Bullseye: Purple
        self.led_control.bullseye((255, 0, 255))  # Purple
        
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

    def _setup_target_blinking(self, target_number, blink_color, start_time, end_time):
        """Helper method to set up blinking for all segments of a target."""
        if target_number not in self.led_control.DARTBOARD_MAPPING:
            print(f"Error: Target number {target_number} not in dartboard mapping")
            return
        
        # Set up blinking for all segments of the target
        segment_types = ['double', 'triple', 'inner_single', 'outer_single']
        
        for segment_type in segment_types:
            segment_id = f'{segment_type}_{target_number}'
            
            self.blinking_segments[segment_id] = {
                'start_time': start_time,
                'end_time': end_time,
                'original_color': (255, 255, 255),  # White (original color)
                'blink_color': blink_color,
                'score': target_number,
                'segment_type': segment_type,
                'blink_count': self.blink_count,
                'blinks_completed': 0,
                'current_state': 'off',  # Start in 'off' state
                'last_toggle': start_time
            }
        
        # Force an immediate update to start blinking
        self.update_blinking_segments(True)
        
    def _setup_segment_blinking(self, score, segment_type, blink_color, start_time, end_time):
        """Helper method to set up blinking for a single segment."""
        if segment_type == 'bullseye':
            segment_id = 'bullseye'
        elif score in self.led_control.DARTBOARD_MAPPING:
            segment_id = f'{segment_type}_{score}'
        else:
            print(f"Error: Score {score} not in dartboard mapping")
            return
            
        # Set the segment to the blink color first to ensure it displays immediately
        if segment_type == 'double':
            self.led_control.doubleSeg(score, blink_color)
        elif segment_type == 'triple':
            self.led_control.tripleSeg(score, blink_color)
        elif segment_type == 'inner_single':
            self.led_control.innerSingleSeg(score, blink_color)
        elif segment_type == 'outer_single':
            self.led_control.outerSingleSeg(score, blink_color)
        elif segment_type == 'bullseye':
            self.led_control.bullseye(blink_color)
            
        # Create the blinking entry
        self.blinking_segments[segment_id] = {
            'start_time': start_time,
            'end_time': end_time,
            'original_color': (255, 255, 255),  # White (original color)
            'blink_color': blink_color,
            'score': score,
            'segment_type': segment_type,
            'blink_count': self.blink_count,
            'blinks_completed': 0,
            'current_state': 'on',  # Start in 'on' state since we already turned it on
            'last_toggle': start_time
        }
        
        # Add a slight delay before forcing an update to ensure the on->off transition is visible
        time.sleep(0.1)
        
        # Force an update to continue the blinking sequence
        self.update_blinking_segments(True)

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
            base_segment_type = hit_miss_info[0]
            is_hit = hit_miss_info[-1] == 'hit'
            
            # Get current target number
            with self.get_moving_target_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT current_target FROM target_state WHERE id = 1")
                state = cursor.fetchone()
                current_target = state['current_target'] if state else 20
            
            # Calculate blink timing
            start_time = time.time()
            end_time = start_time + self.blink_duration
            
            if is_hit:
                # If it's a hit, blink all segments of the target in green
                print(f"Target HIT! Blinking target {current_target} in green")
                blink_color = (0, 255, 0)  # Green
                self._setup_target_blinking(current_target, blink_color, start_time, end_time)
            else:
                # If it's a miss, only blink the hit segment in red
                print(f"Target MISS! Blinking hit segment {score} ({base_segment_type}) in red")
                blink_color = (255, 0, 0)  # Red
                
                # Use the segment helper method to properly set up blinking for the hit segment
                self._setup_segment_blinking(score, base_segment_type, blink_color, start_time, end_time)
        else:
            # For other game modes, use the existing logic
            return self.process_dart_event_classic(event)

    def process_dart_event_classic(self, event):
        """Process a dart event for classic mode."""
        score = event['score']
        multiplier = event['multiplier']
        segment_type = event['segment_type']
        event_id = event['id']
        
        # Calculate blink timing
        start_time = time.time()
        end_time = start_time + self.blink_duration
        
        # Determine segment ID
        if segment_type == 'bullseye':
            segment_id = 'bullseye'
        elif score in self.led_control.DARTBOARD_MAPPING:
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
            return
        
        # In classic mode, original color should always be OFF (0,0,0)
        original_color = (0, 0, 0)  # Black/OFF
        
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
            'blink_color': (0, 255, 0)  # Always use green for blinking
        }
        
        # Immediately light up the hit segment with first update
        self.update_blinking_segments(True)  # Force update

    def update_blinking_segments(self, force_update=False):
        """Update any segments that should be blinking."""
        current_time = time.time()
        
        # Process each blinking segment
        to_remove = []
        
        for segment_id, info in self.blinking_segments.items():
            # Check if this segment's blinking period has expired
            if current_time > info['end_time']:
                if self.current_mode == 'classic':
                    # In classic mode, always turn segments OFF when done blinking
                    off_color = (0, 0, 0)  # Black/OFF
                    
                    if segment_id == 'bullseye':
                        self.led_control.bullseye(off_color)
                    elif 'segment_type' in info:
                        score = info['score']
                        segment_type = info['segment_type']
                        
                        if segment_type == 'double':
                            self.led_control.doubleSeg(score, off_color)
                        elif segment_type == 'triple':
                            self.led_control.tripleSeg(score, off_color)
                        elif segment_type == 'inner_single':
                            self.led_control.innerSingleSeg(score, off_color)
                        elif segment_type == 'outer_single':
                            self.led_control.outerSingleSeg(score, off_color)
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
                            blink_color = (0, 255, 0)  # Green
                        else:
                            # For other modes, use custom blink color if set, otherwise green
                            blink_color = info.get('blink_color', (0, 255, 0))
                        
                        if segment_id == 'bullseye':
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
                        # For OFF state in classic mode, always use black/off
                        if self.current_mode == 'classic':
                            off_color = (0, 0, 0)  # Black/OFF
                            
                            if segment_id == 'bullseye':
                                self.led_control.bullseye(off_color)
                            elif 'segment_type' in info:
                                score = info['score']
                                segment_type = info['segment_type']
                                
                                if segment_type == 'double':
                                    self.led_control.doubleSeg(score, off_color)
                                elif segment_type == 'triple':
                                    self.led_control.tripleSeg(score, off_color)
                                elif segment_type == 'inner_single':
                                    self.led_control.innerSingleSeg(score, off_color)
                                elif segment_type == 'outer_single':
                                    self.led_control.outerSingleSeg(score, off_color)
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
                
                # Handle moving target mode updates
                if self.current_mode == 'moving_target':
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