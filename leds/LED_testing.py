import time
from LEDs import LEDs  # Import the LEDs class
 
def color_wipe_test():
    leds = LEDs()  # Initialize the LED controller
    purple = (50, 0, 50)
    blue = (0, 0, 100)
    red = (100, 0, 0)
    green = (0, 100, 0)

    for i in range(1, 21): 
        leds.doubleSeg(i, purple)
        leds.tripleSeg(i, blue)
        time.sleep(0.001)
    
    for i in range (1, 21): 
        leds.innerSingleSeg(i, green)
        time.sleep(0.001)

    
    # for i in range(1, 21): 
    #     leds.doubleSeg(i, (0,0,0))
    #     leds.tripleSeg(i, (0,0,0))
    #     leds.innerSingleSeg(i, (0,0,0))
    #     time.sleep(0.001)

    
    
    
        
 
if __name__ == "__main__":
    color_wipe_test()
