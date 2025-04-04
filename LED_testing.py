

"""
LEDs.py 

Function: 
This file is holds the functions to control the LED strips for the dartboard. 
"""

import time
from rpi_ws281x import *
import argparse

class LEDs:

    def __init__(self):
        # LED strip configuration:
        self.NUM_STRIPS = 20
        self.NUM_LED_PER_STRIP = 18
        self.LED_COUNT      = self.NUM_STRIPS*self.NUM_LED_PER_STRIP + 1     # Number of LED pixels per strip

        self.LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
        self.LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
        self.LED_DMA        = 10      # DMA channel to use for generating signal (try 10)
        self.LED_BRIGHTNESS = 240     # Set to 0 for darkest and 255 for brightest
        self.LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
        self.LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

        self.TRPL_RING = 9
        self.DBL_RING = 0

        # Initialize the LED strip
        self.strip = Adafruit_NeoPixel(
            self.LED_COUNT, self.LED_PIN, self.LED_FREQ_HZ,
            self.LED_DMA, self.LED_INVERT, self.LED_BRIGHTNESS, self.LED_CHANNEL
        )
        self.strip.begin()

    def getSegIndexes(self, strip_num):
    
        start_seg = strip_num*self.NUM_LED_PER_STRIP
        end_seg = start_seg + self.NUM_LED_PER_STRIP
        
        return start_seg, end_seg 
    
    # Sweep colors across strip     
    def colorWipe(self, strip_num, color, wait_ms=50):
        start_seg, end_seg = self.getSegIndexes(strip_num) 
        for i in range(start_seg, end_seg):
            self.strip.setPixelColor(i, color)
            self.strip.show()
            time.sleep(wait_ms/1000.0)

    # Turn off all LEDs
    def clearAll(self, wait_ms=1): 
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, Color(0,0,0))
            self.strip.show()
            time.sleep(wait_ms/1000.0)

    # Lights up number segment on outer circumference of dartboard 
    def numSeg(self, strip_num, color, wait_ms=5):
        # light up number segment outside of dartboard
        if(strip_num % 2 == 0): #even num strip 
            pixel = self.NUM_RING + self.NUM_LED_PER_STRIP*strip_num
        else: # odd num strip 
            pixel = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - 1)
            
        self.strip.setPixelColor(pixel, color)
        self.strip.show()
        time.sleep(wait_ms/1000.0)
        
    # Lights up triple segment 
    def tripleSeg(self, strip_num, color, wait_ms=5):
        # light up triple segment
        if(strip_num % 2 == 0): #even num strip 
            pixel = self.TRPL_RING + self.NUM_LED_PER_STRIP*strip_num
        else: # odd num strip 
            pixel = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.TRPL_RING - 1)
        
        self.strip.setPixelColor(pixel, color)
        self.strip.show()
        time.sleep(wait_ms/1000.0)
        
    # Lights up double segment 
    def doubleSeg(self, strip_num, color, wait_ms=5):
        # light up triple segment
        if(strip_num % 2 == 0): #even num strip 
            pixel = self.DBL_RING + self.NUM_LED_PER_STRIP*strip_num
        else: # odd num strip 
            pixel = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.DBL_RING - 1)
        
        self.strip.setPixelColor(pixel, color)
        self.strip.show()
        time.sleep(wait_ms/1000.0)

    # Lights up outer single segment (closest to circumference)
    def outerSingleSeg(self, strip_num, color, wait_ms=5):
        
        if(strip_num % 2 == 0): #even num strip 
            start_seg = (self.DBL_RING + self.NUM_LED_PER_STRIP*strip_num) + 1
            end_seg = self.TRPL_RING + self.NUM_LED_PER_STRIP*strip_num
        else: # odd num strip
            end_seg = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.DBL_RING) - 1
            start_seg = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.TRPL_RING)
        
        
        for i in range(start_seg, end_seg):
            self.strip.setPixelColor(i, color)
            self.strip.show()
            time.sleep(wait_ms/1000.0)

    # Lights up inner single segment (furthest from circumference)
    def innerSingleSeg(self, strip_num, color, wait_ms=5):
        
        if(strip_num % 2 == 0): #even num strip 
            start_seg = self.NUM_LED_PER_STRIP*strip_num + self.TRPL_RING + 1 
            end_seg = self.NUM_LED_PER_STRIP*strip_num + self.NUM_LED_PER_STRIP
        else: # odd num strip
            start_seg = self.NUM_LED_PER_STRIP*strip_num 
            end_seg = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.TRPL_RING - 1)
        
        
        for i in range(start_seg, end_seg):
            self.strip.setPixelColor(i, color)
            self.strip.show()
            time.sleep(wait_ms/1000.0)
            
    def bullseye(self, color, wait_ms=5):
        """Lights up the bullseye (centre LED)"""
        bullseye_pixel = self.LED_COUNT - 1  # Assuming the last LED represents the bullseye
        self.strip.setPixelColor(bullseye_pixel, color)
        self.strip.show()
        time.sleep(wait_ms / 1000.0)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clear', action='store_true', help='Clear the display on exit')
    args = parser.parse_args()

    led_control = LEDs()

    print("Press Ctrl-C to quit.")
    if not args.clear:
        print("Use '-c' argument to clear LEDs on exit")
    
    color = (200, 200, 200)  

    try:
       for i in range(20): 
           led_control.tripleSeg(i, color)
           led_control.doubleSeg(i, color)
       led_control.bullseye(color)
        
    except KeyboardInterrupt:
        if args.clear:
            led_control.clearAll()
        print("\nExiting program.")

if __name__ == '__main__':
    main()
