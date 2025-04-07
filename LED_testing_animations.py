import time
from LEDs import LEDs  # Import the LEDs class
 
def color_wipe_test():
    leds = LEDs()  # Initialize the LED controller
    color = (150, 0, 150)
    
    leds.swirlAnimation()
  
 
if __name__ == "__main__":
    color_wipe_test()
