

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
            20: 0, 1: 1, 18: 2, 4: 3, 13: 4,
            6: 5, 10: 6, 15: 7, 2: 8, 17: 9,
            3: 10, 19: 11, 7: 12, 16: 13, 8: 14,
            11: 15, 14: 16, 9: 17, 12: 18, 5: 19
        }

        # Initialize the LED strip
        self.strip = PixelStrip(
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
            self.strip.setPixelColor(i, Color(*color))
            self.strip.show()
            time.sleep(wait_ms/1000.0)

    # Turn off all LEDs
    def clearAll(self, wait_ms=1): 
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, Color(0,0,0))
            self.strip.show()
            time.sleep(wait_ms/1000.0)
        
    # Lights up triple segment 
    def tripleSeg(self, dartboard_num, color, wait_ms=5):

        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"ERROR: Invalid dartboard number: {dartboard_num}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]

        # light up triple segment
        if(strip_num % 2 == 0): #even num strip 
            pixel = self.TRPL_RING + self.NUM_LED_PER_STRIP*strip_num
        else: # odd num strip 
            pixel = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.TRPL_RING - 1)
        
        self.strip.setPixelColor(pixel, Color(*color))
        self.strip.show()
        time.sleep(wait_ms/1000.0)
        
    # Lights up double segment 
    def doubleSeg(self, dartboard_num, color, wait_ms=5):

        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"ERROR: Invalid dartboard number: {dartboard_num}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]

        # light up triple segment
        if(strip_num % 2 == 0): #even num strip 
            pixel = self.DBL_RING + self.NUM_LED_PER_STRIP*strip_num
        else: # odd num strip 
            pixel = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.DBL_RING - 1)
        
        self.strip.setPixelColor(pixel, Color(*color))
        self.strip.show()
        time.sleep(wait_ms/1000.0)

    # Lights up outer single segment (closest to circumference)
    def outerSingleSeg(self, dartboard_num, color, wait_ms=5):

        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"ERROR: Invalid dartboard number: {dartboard_num}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]
        
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

    # Lights up inner single segment (furthest from circumference)
    def innerSingleSeg(self, dartboard_num, color, wait_ms=5):

        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"ERROR: Invalid dartboard number: {dartboard_num}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]
        
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
    
    def bullseye(self, wait_ms=50):
        """Gold outward cumulative build, then synchronized inward ring flashes."""
        gold = (250, 90, 0)
        num_rings = self.NUM_LED_PER_STRIP
        active_strips = [0, 5, 10, 15]  # 4 strips equally spaced out of 20


        # Phase 1: Radiate outward (build-up)
        for ring in range(num_rings):
            for strip_num in active_strips:
                if strip_num % 2 == 0:
                    pixel = strip_num * num_rings + ring
                else:
                    pixel = strip_num * num_rings + (num_rings - ring - 1)
                self.strip.setPixelColor(pixel, Color(*gold))
            self.strip.show()  # show after setting full ring
            time.sleep(wait_ms / 1000.0)

        # Phase 2: Collapse inward one ring at a time, all at once
        for ring in reversed(range(num_rings)):
            self.clearAll(wait_ms=0)  # clear entire board first
            for strip_num in active_strips:
                if strip_num % 2 == 0:
                    pixel = strip_num * num_rings + ring
                else:
                    pixel = strip_num * num_rings + (num_rings - ring - 1)
                self.strip.setPixelColor(pixel, Color(*gold))
            self.strip.show()  # synchronized flash
            time.sleep(wait_ms / 1000.0)

        self.clearAll(wait_ms=10)



    
