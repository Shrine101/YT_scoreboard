import time
from LEDs import LEDs  # Import the LEDs class
 
def color_wipe_test():
    leds = LEDs()  # Initialize the LED controller
    purple = (50, 0, 50)
    blue = (0, 0, 100)

    for i in range(1, 21): 
        leds.doubleSeg(i, purple)
        leds.tripleSeg(i, blue)
        time.sleep(0.01)
    
    for i in range(1, 21): 
        leds.doubleSeg(i, (0,0,0))
        leds.tripleSeg(i, (0,0,0))
        time.sleep(0.01)
    
    
        
 
if __name__ == "__main__":
    color_wipe_test()
