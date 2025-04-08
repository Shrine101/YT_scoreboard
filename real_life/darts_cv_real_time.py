import threading
import time
from final_detection import DartDetectionLive

class DartDetection:
    def __init__(self, debug=False, intersect=True):
        self.cv_running = False
        self.last_score = None
        self.lock = threading.Lock()
        self.detector = DartDetectionLive(debug=debug, intersect=intersect)

    def initialize(self):
        """Simulate initialization time"""
        self.detector.initialize()
        print("Dart detection initialized")

    def start(self):
        """Start the CV detection loop in background thread."""
        self.cv_running = True
        self.cv_thread = threading.Thread(target=self._cv_background_loop, daemon=True)
        self.cv_thread.start()
        self.detector.update_state(self.cv_running)

    def stop(self):
        """Stop the CV detection."""
        self.cv_running = False
        self.detector.success = False
        self.cv_thread.join(timeout=1)
        self.detector.update_state(self.cv_running)

    def return_takeout_state(self):
        is_takeout = False
        with self.lock:
            is_takeout = self.detector.is_takeout if hasattr(self.detector, 'is_takeout') else None
            return is_takeout

    def _cv_background_loop(self):
        """Run DartDetectionLive.run_loop() which will loop forever (until success=False)."""
        self.detector.run_loop()

    def get_next_throw(self):
        """Expose latest score if available. This method can be called from the web API."""
        with self.lock:
            result = self.detector.last_score if hasattr(self.detector, 'last_score') else None
            self.detector.last_score = None  # Clear after reading
            return result
