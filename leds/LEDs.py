"""
LEDs.py 

Function: 
This file holds the functions to control the LED strips for the dartboard.
This enhanced version both controls the real LEDs and outputs status information
to the console for debugging purposes.
"""

import time
from rpi_ws281x import *
import argparse
import colorama
from colorama import Fore, Back, Style
from datetime import datetime

class LEDs:

    def __init__(self):
        # Initialize colorama for colored terminal output
        colorama.init()
        
        # LED strip configuration:
        self.NUM_STRIPS = 20
        self.NUM_LED_PER_STRIP = 18
        self.LED_COUNT      = self.NUM_STRIPS*self.NUM_LED_PER_STRIP      # Number of LED pixels per strip

        self.LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
        self.LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
        self.LED_DMA        = 10      # DMA channel to use for generating signal (try 10)
        self.LED_BRIGHTNESS = 240     # Set to 0 for darkest and 255 for brightest
        self.LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
        self.LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

        self.TRPL_RING = 9
        self.DBL_RING = 0

        # Dartboard number-to-strip mapping
        self.DARTBOARD_MAPPING = {
            2: 0, 15: 1, 10: 2, 6: 3, 13: 4,
            4: 5, 18: 6, 1: 7, 20: 8, 5: 9,
            12: 10, 9: 11, 14: 12, 11: 13, 8: 14,
            16: 15, 7: 16, 19: 17, 3: 18, 17: 19
        }

        # Initialize the LED strip
        self.strip = PixelStrip(
            self.LED_COUNT, self.LED_PIN, self.LED_FREQ_HZ,
            self.LED_DMA, self.LED_INVERT, self.LED_BRIGHTNESS, self.LED_CHANNEL
        )
        self.strip.begin()
        
        # Board state representation (to track LED colors)
        self.board_state = {}
        
        # Blinking tracking
        self.blinking_segments = {}
        
        self.clear_board_state()
        
        print(f"{Fore.GREEN}LEDs initialized - Hardware LEDs will be controlled with console output{Style.RESET_ALL}")
        print(f"Dartboard has {self.NUM_STRIPS} strips with {self.NUM_LED_PER_STRIP} LEDs each")

    def clear_board_state(self):
        """Initialize the board state tracking dictionary."""
        self.board_state = {
            'strips': {},
            'bullseye': (0, 0, 0)  # Black/off
        }
        
        # Initialize all strips to off
        for strip in range(self.NUM_STRIPS):
            self.board_state['strips'][strip] = [(0, 0, 0) for _ in range(self.NUM_LED_PER_STRIP)]

    def getSegIndexes(self, strip_num):
        """Get the start and end segment indices for a strip."""
        start_seg = strip_num*self.NUM_LED_PER_STRIP
        end_seg = start_seg + self.NUM_LED_PER_STRIP
        return start_seg, end_seg
    
    def color_name(self, color):
        """Convert RGB color to a name for better readability."""
        r, g, b = color
        if r > 200 and g > 200 and b > 200: return "WHITE"
        if r > 200 and g > 200 and b < 50: return "YELLOW"
        if r > 200 and g < 50 and b < 50: return "RED"
        if r < 50 and g > 200 and b < 50: return "GREEN"
        if r < 50 and g < 50 and b > 200: return "BLUE"
        if r > 200 and g > 100 and b < 50: return "ORANGE"
        if r > 200 and g < 50 and b > 200: return "PURPLE"
        if r == 0 and g == 0 and b == 0: return "OFF"
        return f"RGB{color}"

    def get_fore_color(self, color):
        """Get the appropriate Fore color for terminal display."""
        r, g, b = color
        if r > 200 and g > 200 and b > 200: return Fore.WHITE
        if r > 200 and g > 200 and b < 50: return Fore.YELLOW
        if r > 200 and g < 50 and b < 50: return Fore.RED
        if r < 50 and g > 200 and b < 50: return Fore.GREEN
        if r < 50 and g < 50 and b > 200: return Fore.BLUE
        if r > 100 and g > 100 and b < 50: return Fore.YELLOW
        if r > 100 and g < 50 and b > 100: return Fore.MAGENTA
        return Fore.WHITE
    
    def get_segment_key(self, dartboard_num, segment_type):
        """Create a consistent key for tracking segments."""
        return f"{segment_type}_{dartboard_num}"
    
    def track_segment_change(self, dartboard_num, segment_type, color):
        """Track segment changes for blinking detection."""
        current_time = time.time()
        segment_key = self.get_segment_key(dartboard_num, segment_type)
        color_name = self.color_name(color)
        
        # Check if we're tracking this segment
        if segment_key in self.blinking_segments:
            last_info = self.blinking_segments[segment_key]
            last_color = last_info['color']
            last_time = last_info['time']
            last_color_name = self.color_name(last_color)
            
            # Detect if we're starting a GREEN or RED blink
            if (color_name == "GREEN" and last_color_name != "GREEN") or (color_name == "RED" and last_color_name != "RED"):
                # Starting a blink
                blink_count = last_info.get('blink_count', 0) + 1
                self.blinking_segments[segment_key] = {
                    'color': color,
                    'time': current_time,
                    'original_color': last_color,
                    'blink_start_time': current_time,
                    'blink_count': blink_count
                }
                
                if last_info.get('blink_count', 0) == 0:
                    # This is the first blink
                    print(f"{Fore.CYAN}[BLINK START] {segment_type.upper()} {dartboard_num} starting to blink at {self.format_time(current_time)}{Style.RESET_ALL}")
                
                # Print progress update
                print(f"{Fore.CYAN}[BLINK ON] {segment_type.upper()} {dartboard_num} turned {color_name} (Blink #{blink_count}){Style.RESET_ALL}")
                
            # Detect if we're ending a GREEN or RED blink
            elif (last_color_name == "GREEN" and color_name != "GREEN") or (last_color_name == "RED" and color_name != "RED"):
                # Ending a blink
                blink_duration = current_time - last_info.get('blink_start_time', last_time)
                
                self.blinking_segments[segment_key] = {
                    'color': color,
                    'time': current_time,
                    'blink_end_time': current_time,
                    'blink_duration': blink_duration,
                    'blink_count': last_info.get('blink_count', 0),
                    'original_color': last_info.get('original_color', color)
                }
                
                # Print update
                print(f"{Fore.CYAN}[BLINK OFF] {segment_type.upper()} {dartboard_num} returned to {color_name}{Style.RESET_ALL}")
                
                # Check if we've restored to original color
                if self.color_name(color) == self.color_name(last_info.get('original_color', color)) and color != (0, 255, 0) and color != (255, 0, 0):
                    # Calculate total blinking time
                    total_time = current_time - last_info.get('blink_start_time', last_time)
                    print(f"{Fore.CYAN}[BLINK END] {segment_type.upper()} {dartboard_num} finished blinking after {total_time:.2f} seconds and {last_info.get('blink_count', 0)} blinks{Style.RESET_ALL}")
            else:
                # Just update the tracking
                self.blinking_segments[segment_key] = {
                    'color': color,
                    'time': current_time,
                    'blink_count': last_info.get('blink_count', 0),
                    'original_color': last_info.get('original_color', last_color),
                    'blink_start_time': last_info.get('blink_start_time', last_time)
                }
        else:
            # First time seeing this segment
            self.blinking_segments[segment_key] = {
                'color': color,
                'time': current_time,
                'blink_count': 0,
                'original_color': color
            }
    
    def format_time(self, timestamp):
        """Format a timestamp for display."""
        return datetime.fromtimestamp(timestamp).strftime('%H:%M:%S.%f')[:-3]

    # Sweep colors across strip     
    def colorWipe(self, strip_num, color, wait_ms=50):
        """Wipe color across display a pixel at a time."""
        # Control the real LEDs
        start_seg, end_seg = self.getSegIndexes(strip_num) 
        for i in range(start_seg, end_seg):
            self.strip.setPixelColor(i, Color(*color))
            self.strip.show()
            time.sleep(wait_ms/1000.0)
        
        # Track in board state
        for i in range(self.NUM_LED_PER_STRIP):
            self.board_state['strips'][strip_num][i] = color
            
        # Print console status
        dartboard_num = None
        for num, strip in self.DARTBOARD_MAPPING.items():
            if strip == strip_num:
                dartboard_num = num
                break
                
        print(f"{self.get_fore_color(color)}Color Wipe: Strip {strip_num} (Dartboard {dartboard_num}) - {self.color_name(color)}{Style.RESET_ALL}")

    # Turn off all LEDs
    def clearAll(self, wait_ms=0.5): 
        """Clear all LEDs by turning them off."""
        # Control the real LEDs
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, Color(0,0,0))
            self.strip.show()
            time.sleep(wait_ms/1000.0)
        
        # Reset board state tracking
        print(f"{Fore.WHITE}Clearing all LEDs{Style.RESET_ALL}")
        self.clear_board_state()
        
    # Lights up triple segment 
    def tripleSeg(self, dartboard_num, color, wait_ms=0.5):
        """Light up the triple segment for a number."""
        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"{Fore.RED}ERROR: Invalid dartboard number: {dartboard_num}{Style.RESET_ALL}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]

        # light up triple segment - real LEDs
        if(strip_num % 2 == 0): #even num strip 
            pixel = self.TRPL_RING + self.NUM_LED_PER_STRIP*strip_num
        else: # odd num strip 
            pixel = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.TRPL_RING - 1)
        
        self.strip.setPixelColor(pixel, Color(*color))
        self.strip.show()
        time.sleep(wait_ms/1000.0)
        
        # Track segment change for console output
        self.track_segment_change(dartboard_num, "triple", color)
        
        # Update board state tracking
        if strip_num % 2 == 0:  # even num strip
            self.board_state['strips'][strip_num][self.TRPL_RING] = color
        else:  # odd num strip
            self.board_state['strips'][strip_num][self.NUM_LED_PER_STRIP - self.TRPL_RING - 1] = color
            
        # Print console status
        print(f"{self.get_fore_color(color)}Triple Segment: Dartboard {dartboard_num} - {self.color_name(color)}{Style.RESET_ALL}")
        
    # Lights up double segment 
    def doubleSeg(self, dartboard_num, color, wait_ms=0.5):
        """Light up the double segment for a number."""
        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"{Fore.RED}ERROR: Invalid dartboard number: {dartboard_num}{Style.RESET_ALL}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]

        # light up double segment - real LEDs
        if(strip_num % 2 == 0): #even num strip 
            pixel = self.DBL_RING + self.NUM_LED_PER_STRIP*strip_num
        else: # odd num strip 
            pixel = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.DBL_RING - 1)
        
        self.strip.setPixelColor(pixel, Color(*color))
        self.strip.show()
        time.sleep(wait_ms/1000.0)
        
        # Track segment change for console output
        self.track_segment_change(dartboard_num, "double", color)
        
        # Update board state tracking
        if strip_num % 2 == 0:  # even num strip
            self.board_state['strips'][strip_num][self.DBL_RING] = color
        else:  # odd num strip
            self.board_state['strips'][strip_num][self.NUM_LED_PER_STRIP - self.DBL_RING - 1] = color
            
        # Print console status
        print(f"{self.get_fore_color(color)}Double Segment: Dartboard {dartboard_num} - {self.color_name(color)}{Style.RESET_ALL}")

    # Lights up outer single segment (closest to circumference)
    def outerSingleSeg(self, dartboard_num, color, wait_ms=0.5):
        """Light up the outer single segment for a number."""
        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"{Fore.RED}ERROR: Invalid dartboard number: {dartboard_num}{Style.RESET_ALL}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]
        
        # Control real LEDs
        if(strip_num % 2 == 0): #even num strip 
            start_seg = (self.DBL_RING + self.NUM_LED_PER_STRIP*strip_num) + 1
            end_seg = self.TRPL_RING + self.NUM_LED_PER_STRIP*strip_num
        else: # odd num strip
            end_seg = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.DBL_RING) - 1
            start_seg = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.TRPL_RING)
        
        for i in range(start_seg, end_seg):
            self.strip.setPixelColor(i, Color(*color))
            self.strip.show()
            time.sleep(wait_ms/1000.0)
        
        # Track segment change for console output
        self.track_segment_change(dartboard_num, "outer_single", color)
        
        # Update board state tracking
        if strip_num % 2 == 0:  # even num strip
            for i in range(self.DBL_RING + 1, self.TRPL_RING):
                self.board_state['strips'][strip_num][i] = color
        else:  # odd num strip
            for i in range(self.NUM_LED_PER_STRIP - self.TRPL_RING, self.NUM_LED_PER_STRIP - self.DBL_RING - 1):
                self.board_state['strips'][strip_num][i] = color
        
        # Print console status
        print(f"{self.get_fore_color(color)}Outer Single Segment: Dartboard {dartboard_num} - {self.color_name(color)}{Style.RESET_ALL}")

    # Lights up inner single segment (furthest from circumference)
    def innerSingleSeg(self, dartboard_num, color, wait_ms=0.5):
        """Light up the inner single segment for a number."""
        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"{Fore.RED}ERROR: Invalid dartboard number: {dartboard_num}{Style.RESET_ALL}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]
        
        # Control real LEDs
        if(strip_num % 2 == 0): #even num strip 
            start_seg = self.NUM_LED_PER_STRIP*strip_num + self.TRPL_RING + 1 
            end_seg = self.NUM_LED_PER_STRIP*strip_num + self.NUM_LED_PER_STRIP
        else: # odd num strip
            start_seg = self.NUM_LED_PER_STRIP*strip_num 
            end_seg = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.TRPL_RING - 1)
        
        for i in range(start_seg, end_seg):
            self.strip.setPixelColor(i, Color(*color))
            self.strip.show()
            time.sleep(wait_ms/1000.0)
        
        # Track segment change for console output
        self.track_segment_change(dartboard_num, "inner_single", color)
        
        # Update board state tracking
        if strip_num % 2 == 0:  # even num strip
            for i in range(self.TRPL_RING + 1, self.NUM_LED_PER_STRIP):
                self.board_state['strips'][strip_num][i] = color
        else:  # odd num strip
            for i in range(0, self.NUM_LED_PER_STRIP - self.TRPL_RING - 1):
                self.board_state['strips'][strip_num][i] = color
        
        # Print console status
        print(f"{self.get_fore_color(color)}Inner Single Segment: Dartboard {dartboard_num} - {self.color_name(color)}{Style.RESET_ALL}")
    
    def bullseye(self, wait_ms=1):
        pass 
        # """Gold outward cumulative build, then synchronized inward ring flashes."""
        # gold = (250, 90, 0)
        
        # # Track for console output
        # self.track_segment_change(25, "bullseye", gold)
        
        # # Update board state
        # self.board_state['bullseye'] = gold
        
        # # Print console status
        # print(f"{self.get_fore_color(gold)}Bullseye: {self.color_name(gold)}{Style.RESET_ALL}")
        
        # # Control real LEDs
        # num_rings = self.NUM_LED_PER_STRIP
        # active_strips = [0, 5, 10, 15]  # 4 strips equally spaced out of 20

        # # Phase 1: Radiate outward (build-up)
        # for ring in range(num_rings):
            # for strip_num in active_strips:
                # if strip_num % 2 == 0:
                    # pixel = strip_num * num_rings + ring
                # else:
                    # pixel = strip_num * num_rings + (num_rings - ring - 1)
                # self.strip.setPixelColor(pixel, Color(*gold))
            # self.strip.show()  # show after setting full ring
            # time.sleep(wait_ms / 1000.0)

        # # Phase 2: Collapse inward one ring at a time, all at once
        # for ring in reversed(range(num_rings)):
            # self.clearAll(wait_ms=0)  # clear entire board first
            # for strip_num in active_strips:
                # if strip_num % 2 == 0:
                    # pixel = strip_num * num_rings + ring
                # else:
                    # pixel = strip_num * num_rings + (num_rings - ring - 1)
                # self.strip.setPixelColor(pixel, Color(*gold))
            # self.strip.show()  # synchronized flash
            # time.sleep(wait_ms / 1000.0)

        # self.clearAll(wait_ms=10)
    
    def print_board_state(self):
        """Print a representation of the current board state to the console."""
        print("\n--- Current Dartboard LED State ---")
        
        # Print bullseye
        bullseye_color = self.color_name(self.board_state['bullseye'])
        print(f"Bullseye: {self.get_fore_color(self.board_state['bullseye'])}{bullseye_color}{Style.RESET_ALL}")
        
        # Print segments by dartboard number
        for dartboard_num in sorted(self.DARTBOARD_MAPPING.keys()):
            strip_num = self.DARTBOARD_MAPPING[dartboard_num]
            
            # Get the colors for the different segments
            double_idx = self.DBL_RING if strip_num % 2 == 0 else self.NUM_LED_PER_STRIP - self.DBL_RING - 1
            triple_idx = self.TRPL_RING if strip_num % 2 == 0 else self.NUM_LED_PER_STRIP - self.TRPL_RING - 1
            
            double_color = self.board_state['strips'][strip_num][double_idx]
            triple_color = self.board_state['strips'][strip_num][triple_idx]
            
            # For simplicity, just check one of the inner/outer single segments
            inner_idx = self.TRPL_RING + 1 if strip_num % 2 == 0 else self.NUM_LED_PER_STRIP - self.TRPL_RING - 2
            if 0 <= inner_idx < self.NUM_LED_PER_STRIP:
                inner_color = self.board_state['strips'][strip_num][inner_idx]
            else:
                inner_color = (0, 0, 0)  # Default off
                
            outer_idx = self.DBL_RING + 1 if strip_num % 2 == 0 else self.NUM_LED_PER_STRIP - self.DBL_RING - 2
            if 0 <= outer_idx < self.NUM_LED_PER_STRIP:
                outer_color = self.board_state['strips'][strip_num][outer_idx]
            else:
                outer_color = (0, 0, 0)  # Default off
            
            print(f"Dartboard {dartboard_num:2d}: "
                  f"Double: {self.get_fore_color(double_color)}{self.color_name(double_color):<8}{Style.RESET_ALL} | "
                  f"Outer: {self.get_fore_color(outer_color)}{self.color_name(outer_color):<8}{Style.RESET_ALL} | "
                  f"Triple: {self.get_fore_color(triple_color)}{self.color_name(triple_color):<8}{Style.RESET_ALL} | "
                  f"Inner: {self.get_fore_color(inner_color)}{self.color_name(inner_color):<8}{Style.RESET_ALL}")
        
        print("------------------------------------\n")

    def print_blinking_summary(self):
        """Print a summary of blinking segments."""
        print("\n=== Blinking Segments Summary ===")
        
        active_blinks = {}
        completed_blinks = {}
        
        for key, info in self.blinking_segments.items():
            if info.get('blink_count', 0) > 0:
                if 'blink_end_time' in info:
                    # This is a completed blink
                    completed_blinks[key] = info
                else:
                    # This is an active blink
                    active_blinks[key] = info
        
        if active_blinks:
            print("Currently Blinking:")
            for key, info in active_blinks.items():
                current_time = time.time()
                duration = current_time - info.get('blink_start_time', current_time)
                print(f"  - {key}: Blinking for {duration:.2f} seconds, {info.get('blink_count', 0)} blinks so far")
        else:
            print("No segments currently blinking")
            
        if completed_blinks:
            print("\nCompleted Blinks:")
            for key, info in completed_blinks.items():
                duration = info.get('blink_end_time', 0) - info.get('blink_start_time', 0)
                print(f"  - {key}: Blinked for {duration:.2f} seconds, {info.get('blink_count', 0)} total blinks")
                
        print("================================\n")
