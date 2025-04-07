import time
from LEDs import LEDs  # Import the LEDs class
 
def color_wipe_test():
    leds = LEDs()  # Initialize the LED controller
    color = (0, 100, 0)

    for i in range(20): 
        leds.colorWipe(i, color)
        time.sleep(0.05)
  
 
if __name__ == "__main__":
    color_wipe_test()
