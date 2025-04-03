# darts_cv_simulation.py

import random
import time

class DartDetection:
    def __init__(self):
        self.cv_running = False

    def generate_random_score(self):
        """Generate a random dart score with possibility of a miss"""
        # Add a chance to completely miss (0 score)
        if random.random() < 0.15:  # 15% chance to miss the board
            # For a miss, use position far from center to indicate it's outside the board
            # In a real system, this might not be detected at all, but for simulation we'll return it
            miss_position = (random.randint(300, 400), random.randint(0, 359))
            print(f"MISS! Dart missed the board completely. Position: {miss_position}")
            return (0, 0, miss_position)  # Score 0, multiplier 0 for a miss
            
        # Original logic for hitting the board
        multiplier = 1
        # Generate a more realistic random position
        position = (random.randint(0, 225), random.randint(0, 359))

        dartboard_numbers = list(range(1, 21)) + [25]  # 25 is bullseye
        single_score = random.choice(dartboard_numbers)

        if single_score == 25:  # no triple for bullseye
            multiplier = random.choice([1, 2])
        else:
            multiplier = random.choices([1, 2, 3], weights=[60, 20, 20])[0]

        
        print(f"HIT! single_score = {single_score}, multiplier = {multiplier}, position = {position}")
        return (single_score, multiplier, position)

    def initialize(self):
        """Simulate initialization time"""
        time.sleep(2)
        print("Dart detection initialized")

    def start(self):
        """Start the simulation"""
        self.cv_running = True

    def stop(self):
        """Stop the simulation"""
        self.cv_running = False

    def get_next_throw(self):
        """Get the next throw if running"""
        if not self.cv_running:
            return None
            
        time.sleep(7)  # Simulate detection time
        return self.generate_random_score()