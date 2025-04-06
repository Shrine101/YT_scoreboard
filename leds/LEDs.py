"""
LEDs.py 

Function: 
This file holds the functions to control the LED strips for the dartboard. 
"""

import time
from rpi_ws281x import *
import argparse

class LEDs:

    def __init__(self):
        # LED strip configuration:
        self.NUM_STRIPS = 20
        self.NUM_LED_PER_STRIP = 18
        self.LED_COUNT = self.NUM_STRIPS * self.NUM_LED_PER_STRIP

        self.LED_PIN = 18
        self.LED_FREQ_HZ = 800000
        self.LED_DMA = 10
        self.LED_BRIGHTNESS = 240
        self.LED_INVERT = False
        self.LED_CHANNEL = 0

        self.TRPL_RING = 9
        self.DBL_RING = 0

        self.DARTBOARD_MAPPING = {
            20: 0, 1: 1, 18: 2, 4: 3, 13: 4,
            6: 5, 10: 6, 15: 7, 2: 8, 17: 9,
            3: 10, 19: 11, 7: 12, 16: 13, 8: 14,
            11: 15, 14: 16, 9: 17, 12: 18, 5: 19
        }

        self.strip = PixelStrip(
            self.LED_COUNT, self.LED_PIN, self.LED_FREQ_HZ,
            self.LED_DMA, self.LED_INVERT, self.LED_BRIGHTNESS, self.LED_CHANNEL
        )
        self.strip.begin()

    def getSegIndexes(self, strip_num):
        start_seg = strip_num * self.NUM_LED_PER_STRIP
        end_seg = start_seg + self.NUM_LED_PER_STRIP
        return start_seg, end_seg

    def colorWipe(self, strip_num, color, wait_ms=50):
        start_seg, end_seg = self.getSegIndexes(strip_num)
        for i in range(start_seg, end_seg):
            self.strip.setPixelColor(i, Color(*color))
            self.strip.show()
            time.sleep(wait_ms / 1000.0)

    def clearAll(self, wait_ms=1):
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, Color(0, 0, 0))
            self.strip.show()
            time.sleep(wait_ms / 1000.0)

    def tripleSeg(self, dartboard_num, color, wait_ms=5):
        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"ERROR: Invalid dartboard number: {dartboard_num}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]

        if strip_num % 2 == 0:
            pixel = self.TRPL_RING + self.NUM_LED_PER_STRIP * strip_num
        else:
            pixel = self.NUM_LED_PER_STRIP * strip_num + (self.NUM_LED_PER_STRIP - self.TRPL_RING - 1)

        self.strip.setPixelColor(pixel, Color(*color))
        self.strip.show()
        time.sleep(wait_ms / 1000.0)
        print(f"Triple segment lit for dartboard number {dartboard_num}")

    def doubleSeg(self, dartboard_num, color, wait_ms=5):
        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"ERROR: Invalid dartboard number: {dartboard_num}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]

        if strip_num % 2 == 0:
            pixel = self.DBL_RING + self.NUM_LED_PER_STRIP * strip_num
        else:
            pixel = self.NUM_LED_PER_STRIP * strip_num + (self.NUM_LED_PER_STRIP - self.DBL_RING - 1)

        self.strip.setPixelColor(pixel, Color(*color))
        self.strip.show()
        time.sleep(wait_ms / 1000.0)
        print(f"Double segment lit for dartboard number {dartboard_num}")

    def outerSingleSeg(self, dartboard_num, color, wait_ms=5):
        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"ERROR: Invalid dartboard number: {dartboard_num}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]

        if strip_num % 2 == 0:
            start_seg = (self.DBL_RING + self.NUM_LED_PER_STRIP * strip_num) + 1
            end_seg = self.TRPL_RING + self.NUM_LED_PER_STRIP * strip_num
        else:
            end_seg = self.NUM_LED_PER_STRIP * strip_num + (self.NUM_LED_PER_STRIP - self.DBL_RING) - 1
            start_seg = self.NUM_LED_PER_STRIP * strip_num + (self.NUM_LED_PER_STRIP - self.TRPL_RING)

        for i in range(start_seg, end_seg):
            self.strip.setPixelColor(i, Color(*color))
            self.strip.show()
            time.sleep(wait_ms / 1000.0)
        print(f"Outer single segment lit for dartboard number {dartboard_num}")

    def innerSingleSeg(self, dartboard_num, color, wait_ms=5):
        if dartboard_num not in self.DARTBOARD_MAPPING:
            print(f"ERROR: Invalid dartboard number: {dartboard_num}")
            return

        strip_num = self.DARTBOARD_MAPPING[dartboard_num]

        if strip_num % 2 == 0:
            start_seg = self.NUM_LED_PER_STRIP * strip_num + self.TRPL_RING + 1
            end_seg = self.NUM_LED_PER_STRIP * strip_num + self.NUM_LED_PER_STRIP
        else:
            start_seg = self.NUM_LED_PER_STRIP * strip_num
            end_seg = self.NUM_LED_PER_STRIP * strip_num + (self.NUM_LED_PER_STRIP - self.TRPL_RING - 1)

        for i in range(start_seg, end_seg):
            self.strip.setPixelColor(i, Color(*color))
            self.strip.show()
            time.sleep(wait_ms / 1000.0)
        print(f"Inner single segment lit for dartboard number {dartboard_num}")

    def bullseye(self, wait_ms=50):
        """Gold outward cumulative build, then synchronized inward ring flashes."""
        gold = (250, 90, 0)
        num_rings = self.NUM_LED_PER_STRIP
        active_strips = [0, 5, 10, 15]

        print("Bullseye animation starting...")

        for ring in range(num_rings):
            for strip_num in active_strips:
                if strip_num % 2 == 0:
                    pixel = strip_num * num_rings + ring
                else:
                    pixel = strip_num * num_rings + (num_rings - ring - 1)
                self.strip.setPixelColor(pixel, Color(*gold))
            self.strip.show()
            time.sleep(wait_ms / 1000.0)

        for ring in reversed(range(num_rings)):
            self.clearAll(wait_ms=0)
            for strip_num in active_strips:
                if strip_num % 2 == 0:
                    pixel = strip_num * num_rings + ring
                else:
                    pixel = strip_num * num_rings + (num_rings - ring - 1)
                self.strip.setPixelColor(pixel, Color(*gold))
            self.strip.show()
            time.sleep(wait_ms / 1000.0)

        self.clearAll(wait_ms=10)
        print("Bullseye animation complete.")
