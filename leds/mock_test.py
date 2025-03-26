"""
Test script to run the LED Controller with the MockLEDs implementation
"""

import importlib
import sys
import os

def run_with_mock():
    """Run the LED controller using the mock LEDs implementation."""
    # Modify the system module cache to replace LEDs with MockLEDs
    # This must be done before importing LED_controller
    print("Setting up MockLEDs...")
    
    # Import MockLEDs
    from MockLEDs import MockLEDs
    
    # Create a dummy module for LEDs that returns our MockLEDs class
    class DummyModule:
        LEDs = MockLEDs
    
    # Replace the LEDs module in sys.modules
    sys.modules['LEDs'] = DummyModule
    
    # Now import the LED_controller module (it will use our mock)
    print("Importing LED_controller...")
    import LED_controller
    
    # Start the controller
    print("Starting LED controller with MockLEDs...\n")
    controller = LED_controller.LEDController( blink_duration=2.0, blink_count=2)
    
    # Add a method to print board state periodically
    original_run = controller.run
    
    def run_with_state_display():
        """Modified run method that periodically displays board state."""
        print("LED Controller running (MOCK VERSION), press Ctrl+C to stop...")
        
        try:
            # Initial setup based on current mode
            controller.current_mode = controller.get_current_mode()
            if controller.current_mode == 'classic':
                controller.setup_classic_mode()
                
            # Print initial state
            controller.led_control.print_board_state()
            
            print("\nWaiting for dart events... Use test_dart_event.py to add events.")
            print("Press Ctrl+C to exit.\n")
            
            # Main processing loop
            while True:
                # Check for game mode changes
                new_mode = controller.get_current_mode()
                if new_mode != controller.current_mode:
                    print(f"Game mode changed from {controller.current_mode} to {new_mode}")
                    controller.current_mode = new_mode
                    
                    # Update LED pattern based on new mode
                    if controller.current_mode == 'classic':
                        controller.setup_classic_mode()
                        controller.led_control.print_board_state()
                
                # Get new dart events
                events = controller.get_new_dart_events()
                
                # Process each new event
                for event in events:
                    controller.process_dart_event(event)
                    controller.led_control.print_board_state()
                
                # Update blinking segments
                controller.update_blinking_segments()
                
        except KeyboardInterrupt:
            print("\nLED Controller stopped.")
            # Clean up
            controller.led_control.clearAll()
            controller.led_control.print_board_state()
    
    # Replace the run method with our enhanced version
    controller.run = run_with_state_display
    
    # Run the controller
    controller.run()

if __name__ == "__main__":
    run_with_mock()