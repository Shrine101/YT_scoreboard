import cv2
import numpy as np
import tkinter as tk
from tkinter import *
import threading
import yaml
import os


class CameraCalibration:
    def __init__(self, cam_index=0):
        """Initialize the camera and setup the GUI sliders."""
        self.cam_index = cam_index
        self.video_capture = cv2.VideoCapture(self.cam_index)

        self.file_name = "configs/calibration_" + str(self.cam_index) + ".yaml"

        # Default slider values
        self.threshold_value = 50
        self.roi_y = 100
        self.roi_height = 200
        self.surface_y = 250
        self.surface_center = 320

        self.load_from_yaml()

        # Setup GUI (Tkinter runs in main thread)
        self.root = tk.Tk()
        self.root.title("Camera Calibration")

        # Create sliders
        self.create_slider("Threshold", 0, 255, self.threshold_value, self.update_threshold)
        self.create_slider("ROI Y", 0, 480, self.roi_y, self.update_roi_y)
        self.create_slider("ROI Height", 25, 400, self.roi_height, self.update_roi_height)
        self.create_slider("Surface Y", 0, 480, self.surface_y, self.update_surface_y)
        #self.create_slider("Surface Center", 0, 640, self.surface_center, self.update_surface_center)
        # "Set" button to save settings and exit
        self.set_button = Button(self.root, text="Set", command=self.save_and_exit, font=("Arial", 14), padx=20, pady=10)
        self.set_button.pack(pady=10)
        # Start OpenCV in a separate thread
        self.video_thread = threading.Thread(target=self.process_video, daemon=True)
        self.video_thread.start()


    
    def load_from_yaml(self):
  
        if os.path.exists(self.file_name):  # Check if file exists
            with open(self.file_name, "r") as file:
                calibration_data = yaml.safe_load(file)

            # Update instance variables if keys exist
            if calibration_data:
                self.threshold_value = calibration_data.get("threshold", self.threshold_value)
                self.roi_y = calibration_data.get("roi_y", self.roi_y)
                self.roi_height = calibration_data.get("roi_height", self.roi_height)
                self.surface_y= calibration_data.get("surface_y", self.surface_y)
                self.surface_center = calibration_data.get("surface_center", self.surface_center)

                print("\nLoaded calibration settings from ", self.file_name)
                    #print(calibration_data)


    def save_to_yaml(self):
        """Save calibration settings to a YAML file."""
        try:
            with open("calibration.yaml", "r") as file:
                calibration_data = yaml.safe_load(file) or {}
        except FileNotFoundError:
            calibration_data = {}
            
         # Initialize cameras section if it doesn't exist
        if 'cameras' not in calibration_data:
            calibration_data['cameras'] = {}

        # Update calibration data for this specific camera
        camera_calibration = {
            "threshold": self.threshold_value,
            "roi_y": self.roi_y,
            "roi_height": self.roi_height,
            "surface_y": self.surface_y,
            "surface_center": self.surface_center
        }

        # Save this camera's data under its own section
        #calibration_data['cameras'][f'camera_{self.cam_index}'] = camera_calibration
        calibration_data = camera_calibration
        
        # Save to a YAML file
        with open(self.file_name, "w") as file:
            yaml.dump(calibration_data, file, default_flow_style=False)

        print("\nCalibration settings saved to ", self.file_name)

    def exit_gui(self):
        self.root.destroy()

    def save_and_exit(self):
        """Save settings and close the application."""
        self.save_to_yaml()  # Save settings to YAML file
        self.running = False  # Stop OpenCV loop
        #self.root.quit()  # Close Tkinter
        cv2.destroyAllWindows()  # Close OpenCV windows
        self.root.after(0, self.exit_gui)


    def create_slider(self, label, min_val, max_val, default, command):
        """Creates a labeled, larger slider in the GUI."""
        frame = tk.Frame(self.root)
        frame.pack(pady=5)  # Add spacing

        # Larger font for labels
        tk.Label(frame, text=label, font=("Arial", 14)).pack(side="left", padx=10)

        # Bigger slider with increased width and height
        scale = Scale(
            frame, from_=min_val, to=max_val, orient="horizontal",
            command=command, length=400, sliderlength=30,  # Increase width & slider size
            tickinterval=(max_val - min_val) // 4,  # Show ticks
            font=("Arial", 12)  # Bigger numbers
        )
        
        scale.set(default)
        scale.pack(side="right", padx=10)

    def update_threshold(self, value):
        self.threshold_value = int(value)

    def update_roi_y(self, value):
        self.roi_y = int(value)

    def update_roi_height(self, value):
        self.roi_height = int(value)

    def update_surface_y(self, value):
        self.surface_y = int(value)

    def update_surface_center(self, value):
        self.surface_center = int(value)


    def process_video(self):
        """Capture video frames, apply Canny edge detection, and overlay lines."""
        self.video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        while True:
            ret, frame = self.video_capture.read()
            if not ret:
                break


            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Apply Gaussian Blur (reduces noise)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)

            # Apply Thresholding (instead of Canny)
            _, thresholded = cv2.threshold(blurred, self.threshold_value, 255, cv2.THRESH_BINARY)

            # Extract ROI (Region of Interest)
            #roi = thresholded[self.roi_y:self.roi_y + self.roi_height, :]
            roi = thresholded

            #print(cv2.countNonZero(roi))
            #print("\n")

            # Convert ROI to BGR for visualization
            roi_colored = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
           

            # Draw Overlay Lines on Main Frame
            cv2.line(frame, (0, self.surface_y), (frame.shape[1], self.surface_y), (0, 0, 255), 2)  # Red Surface Line
            #cv2.line(frame, (self.surface_center, 0), (self.surface_center, frame.shape[0]), (0, 255, 0), 2)  # Green Center Line
            cv2.rectangle(frame, (0, self.roi_y), (frame.shape[1], self.roi_y + self.roi_height), (255, 0, 0), 2)  # ROI Box

            # Display the processed images
            cv2.imshow("Camera Calibration", frame)       # Main Frame with Overlays
            cv2.imshow("Thresholded ROI", roi_colored)    # ROI with Thresholding


            # Exit on 'q' key press
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        self.video_capture.release()
        cv2.destroyAllWindows()

    def run(self):
        """Run Tkinter GUI in the main thread."""
        self.root.mainloop()

# Run the camera calibration tool
import argparse
if __name__ == "__main__":
   
    parser = argparse.ArgumentParser(description="Open a camera using the specified ID.")
    parser.add_argument("-c", type=int, help="camera ID to open (0,2,4 etc)")
    args = parser.parse_args()

    if args.c is not None:
        try:
            cam_calibration = CameraCalibration(args.c)
            cam_calibration.run()
        except:
            sys.exit(0)
    else:
        print('ENTER A CAMERA INDEX THAT YOU WANT TO CALIBRATE')
