import time
from LEDs import LEDs  # Import the LEDs class

def color_wipe_test():
    leds = LEDs()  # Initialize the LED controller
    color = (255, 0, 0)  # Red color for testing

    print("Starting Color Wipe Test...")

    # Wipe each strip in sequence
    for strip_num in range(21):
        leds.colorWipe(strip_num, color, wait_ms=50)  # Run color wipe on each strip
        time.sleep(0.2)  # Small delay between strips
        leds.colorWipe(strip_num, (0,0,0), wait_ms=50)  # Run color wipe on each strip


    print("Test complete. Clearing LEDs...")
    leds.clearAll(wait_ms=10)  # Clear all LEDs

if __name__ == "__main__":
    color_wipe_test()
