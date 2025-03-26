"""
MockLEDs.py 

Function: 
This is a mock implementation of the LEDs class that prints status messages 
instead of controlling actual LED hardware. Used for testing without physical LEDs.
"""

import time
import colorama
from colorama import Fore, Back, Style

class MockLEDs:
    """A mock implementation of the LEDs class that prints status messages instead of controlling hardware."""

    def __init__(self):
        # Initialize colorama for colored terminal output
        colorama.init()
        
        # LED strip configuration (same as the original LEDs class)
        self.NUM_STRIPS = 20
        self.NUM_LED_PER_STRIP = 19
        self.LED_COUNT = self.NUM_STRIPS*self.NUM_LED_PER_STRIP + 1
        
        # Ring positions
        self.NUM_RING = 0 
        self.TRPL_RING = 10
        self.DBL_RING = 1

        # Dartboard number-to-strip mapping (same as the original LEDs class)
        self.DARTBOARD_MAPPING = {
            20: 0, 1: 1, 18: 2, 4: 3, 13: 4,
            6: 5, 10: 6, 15: 7, 2: 8, 17: 9,
            3: 10, 19: 11, 7: 12, 16: 13, 8: 14,
            11: 15, 14: 16, 9: 17, 12: 18, 5: 19
        }
        
        # Board state representation (to track LED colors)
        self.board_state = {}
        self.clear_board_state()
        
        print(f"{Fore.GREEN}MockLEDs initialized - No hardware will be controlled{Style.RESET_ALL}")
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
        """Get the start and end indices for a segment."""
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
    
    def colorWipe(self, strip_num, color, wait_ms=50):
        """Simulate color wipe effect by updating the board state."""
        start_seg, end_seg = self.getSegIndexes(strip_num)
        
        # Update in board state
        for i in range(self.NUM_LED_PER_STRIP):
            self.board_state['strips'][strip_num][i] = color
            
        dartboard_num = None
        for num, strip in self.DARTBOARD_MAPPING.items():
            if strip == strip_num:
                dartboard_num = num
                break
                
        print(f"{self.get_fore_color(color)}Color Wipe: Strip {strip_num} (Dartboard {dartboard_num}) - {self.color_name(color)}{Style.RESET_ALL}")
        time.sleep(wait_ms/1000.0)

    def clearAll(self, wait_ms=1): 
        """Turn off all LEDs in the mock."""
        print(f"{Fore.WHITE}Clearing all LEDs{Style.RESET_ALL}")
        self.clear_board_state()
        time.sleep(wait_ms/1000.0)

    def numSeg(self, dartboard_num, color, wait_ms=5):
        """Light up number segment on outer circumference of dartboard."""
        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"{Fore.RED}ERROR: Invalid dartboard number: {dartboard_num}{Style.RESET_ALL}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]
        print(f"{self.get_fore_color(color)}Number Segment: Dartboard {dartboard_num} - {self.color_name(color)}{Style.RESET_ALL}")
        
        # Update in board state
        if strip_num % 2 == 0:  # even num strip
            self.board_state['strips'][strip_num][self.NUM_RING] = color
        else:  # odd num strip
            self.board_state['strips'][strip_num][self.NUM_LED_PER_STRIP - 1] = color
            
        time.sleep(wait_ms/1000.0)
        
    def tripleSeg(self, dartboard_num, color, wait_ms=5):
        """Light up triple segment."""
        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"{Fore.RED}ERROR: Invalid dartboard number: {dartboard_num}{Style.RESET_ALL}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]
        print(f"{self.get_fore_color(color)}Triple Segment: Dartboard {dartboard_num} - {self.color_name(color)}{Style.RESET_ALL}")
        
        # Update in board state
        if strip_num % 2 == 0:  # even num strip
            self.board_state['strips'][strip_num][self.TRPL_RING] = color
        else:  # odd num strip
            self.board_state['strips'][strip_num][self.NUM_LED_PER_STRIP - self.TRPL_RING - 1] = color
            
        time.sleep(wait_ms/1000.0)
        
    def doubleSeg(self, dartboard_num, color, wait_ms=5):
        """Light up double segment."""
        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"{Fore.RED}ERROR: Invalid dartboard number: {dartboard_num}{Style.RESET_ALL}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]
        print(f"{self.get_fore_color(color)}Double Segment: Dartboard {dartboard_num} - {self.color_name(color)}{Style.RESET_ALL}")
        
        # Update in board state
        if strip_num % 2 == 0:  # even num strip
            self.board_state['strips'][strip_num][self.DBL_RING] = color
        else:  # odd num strip
            self.board_state['strips'][strip_num][self.NUM_LED_PER_STRIP - self.DBL_RING - 1] = color
            
        time.sleep(wait_ms/1000.0)

    def outerSingleSeg(self, dartboard_num, color, wait_ms=5):
        """Light up outer single segment (closest to circumference)."""
        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"{Fore.RED}ERROR: Invalid dartboard number: {dartboard_num}{Style.RESET_ALL}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]
        print(f"{self.get_fore_color(color)}Outer Single Segment: Dartboard {dartboard_num} - {self.color_name(color)}{Style.RESET_ALL}")
        
        # Update in board state - simplified just to show the concept
        if strip_num % 2 == 0:  # even num strip
            for i in range(self.DBL_RING + 1, self.TRPL_RING):
                self.board_state['strips'][strip_num][i] = color
        else:  # odd num strip
            for i in range(self.NUM_LED_PER_STRIP - self.TRPL_RING, self.NUM_LED_PER_STRIP - self.DBL_RING - 1):
                self.board_state['strips'][strip_num][i] = color
                
        time.sleep(wait_ms/1000.0)

    def innerSingleSeg(self, dartboard_num, color, wait_ms=5):
        """Light up inner single segment (furthest from circumference)."""
        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"{Fore.RED}ERROR: Invalid dartboard number: {dartboard_num}{Style.RESET_ALL}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]
        print(f"{self.get_fore_color(color)}Inner Single Segment: Dartboard {dartboard_num} - {self.color_name(color)}{Style.RESET_ALL}")
        
        # Update in board state - simplified just to show the concept
        if strip_num % 2 == 0:  # even num strip
            for i in range(self.TRPL_RING + 1, self.NUM_LED_PER_STRIP):
                self.board_state['strips'][strip_num][i] = color
        else:  # odd num strip
            for i in range(0, self.NUM_LED_PER_STRIP - self.TRPL_RING - 1):
                self.board_state['strips'][strip_num][i] = color
                
        time.sleep(wait_ms/1000.0)
    
    def bullseye(self, color, wait_ms=5):
        """Light up the bullseye (centre LED)."""
        print(f"{self.get_fore_color(color)}Bullseye: {self.color_name(color)}{Style.RESET_ALL}")
        
        # Update in board state
        self.board_state['bullseye'] = color
        
        time.sleep(wait_ms / 1000.0)

    def print_board_state(self):
        """Print a representation of the current board state."""
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