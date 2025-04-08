import cv2 as cv
import numpy as np
import time
import os
import yaml
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from triangulate import *
from statistics import mean
from collections import defaultdict

class DartDetectionLive:
    def __init__(self, debug, intersect):
        self.x = None
        self.y = None

        self.good_2_throw = False

        self.num_cameras = 4
        self.cam_indexes = [0,2,4,6]
        self.streams = []
        self.time_stamp = None
        self.debug = debug
        self.intersect = intersect

        #Dart Detection Boolean Variables
        self.is_dart = False 
        self.is_takeout = False 
       
        self.is_movement = [False] * self.num_cameras #this is general movement,needs to be processed further to conclude if its a dart
        self.num_still_frames = [0] * self.num_cameras
        self.num_still_critea = 2
        self.no_contour_check = 5
        self.last_score = None

        self.score_calculator = DartPositionFinder(
            board_radius=225.5,   # 451mm diameter / 2
            scoring_radius=170,   # 340mm diameter / 2
            camera_distance_factor=1.9,
            camera_distance=508,
        )

        self.plotter = DartboardScoringVisualizer()

        # set ref and current frames (used to detect if there is a dart)
        self.reference_frames = [None] * self.num_cameras
        self.reference_frames_movement = [None] * self.num_cameras
        self.current_frames = [None] * self.num_cameras
        self.current_frames_roi = [None] * self.num_cameras
        self.current_frames_copy = [None] * self.num_cameras
        self.shifted_contours = [None] * self.num_cameras
        self.fgMasks = [None] * self.num_cameras
        self.fgMasks_move = [None] * self.num_cameras
        self.frames_thresh_current = [None] * self.num_cameras
        self.masks = [[] for _ in range(self.num_cameras)]
        self.processed_dart = [False] * self.num_cameras
        #confidence timer (reset states if a camera is false triggering, due to noise,
        #lighting flickers and ghost contours)
        self.false_trigger_count = [0] * self.num_cameras
        self.movement_duration = [0] * self.num_cameras
        self.false_trigger_limit = 5              # how many fails before reset
        self.max_movement_frames = 35              # how long movement is allowed before reset

        # detection parameters
        self.min_threshold = 100
        self.max_threshold = 30000
        self.min_area = 30
        self.takeout_time = 4/self.num_cameras
        self.frame_update = 15

        #boolean that keeps the dart detection loop running
        self.success = True
        self.dart_count = 1
        self.dart_positions = defaultdict(dict)
        #plotting intersection data
        self.plot_data = defaultdict(dict)


        # store calibration values for each camera (the below are default values)
        self.calibration = {
            cam_index: {
                "threshold": 110,  # binary threshold value
                "roi_y": 250,
                "roi_h": 100,
                "threshold_y": 320, #the y coor of the surface of dartboard
                "roi_x": 0,
                "roi_w": 640
            } for cam_index in range(self.num_cameras)
        }  

        #self.initialize() #TODO: TAKEKOUT FOR WEBAPP

    def initialize(self):
        # load calibration values per camera
        for cam_index in range(self.num_cameras):
            self.load_from_yaml(cam_index)
            self.plot_data[cam_index]['y_top'] = self.calibration[cam_index]["roi_y"]
            self.plot_data[cam_index]['y_bot']  = self.calibration[cam_index]["roi_y"] + self.calibration[cam_index]["roi_h"] - 1

        self.load_streams()

    def update_state(self, is_running):
        self.success = is_running

    def return_takeout_state(self):
        return self.is_takeout

    def load_streams(self):
        for i in self.cam_indexes:
            stream = cv.VideoCapture(i)
            if not stream.isOpened():
                print(f"Warning: Could not open webcam {i}")
                continue  
            else:
                print(f"Camera: {i} is opened")

            # Set resolution
            stream.set(cv.CAP_PROP_FRAME_WIDTH, 640)
            stream.set(cv.CAP_PROP_FRAME_HEIGHT, 480)
            self.streams.append(stream)

    def load_from_yaml(self, cam_index):
        """Load calibration values from a YAML file if it exists."""
        file_name = f"configs/calibration_{cam_index*2}.yaml"
        if os.path.exists(file_name):
            try:
                with open(file_name, "r") as file:
                    calibration_data = yaml.safe_load(file)
                    if calibration_data:
                        self.calibration[cam_index]["threshold"] = calibration_data.get("threshold", self.calibration[cam_index]["threshold"])
                        self.calibration[cam_index]["roi_y"] = calibration_data.get("roi_y", self.calibration[cam_index]["roi_y"])
                        self.calibration[cam_index]["roi_h"] = calibration_data.get("roi_height", self.calibration[cam_index]["roi_h"])
                        self.calibration[cam_index]["threshold_y"] = calibration_data.get("surface_y", self.calibration[cam_index]["threshold_y"])
                        print(f"\nLoaded calibration settings for Camera {cam_index} from {file_name}.")
                    else:
                        print("no data")
            except yaml.YAMLError as e:
                print(f"Error reading {file_name}: {e}")
        else:
            print("missing calibration file: ", file_name)

    def update_reference_frame(self, cam_index):
        """Update reference frame for the given camera."""
        success, frame = self.streams[cam_index].read()
        if success:
            self.reference_frames[cam_index] = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)

    
    def update_movement_frame(self, cam_index):
        """Update reference frame for the given camera."""
        success, frame = self.streams[cam_index].read()
        if success:
            self.reference_frames_movement[cam_index] = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)


    def get_threshold(self, cam_index):
        """Apply thresholding to detect motion for the given camera."""

        success, frame = self.streams[cam_index].read()
        
        if self.debug:
            self.current_frames_copy[cam_index] = frame.copy()

        self.current_frames[cam_index] = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)

        _, self.frames_thresh_current[cam_index] = cv.threshold(
            self.current_frames[cam_index],
            self.calibration[cam_index]["threshold"],
            255,
            cv.THRESH_BINARY
        )

        # compute absolute difference ( to detect if there is movement bewteen frames)
        diff = cv.absdiff(self.reference_frames[cam_index], self.current_frames[cam_index])
        diff_move =  cv.absdiff(self.reference_frames_movement[cam_index], self.current_frames[cam_index])
        #print("i am hang2")

        diff = cv.GaussianBlur(diff, (5, 5), 0)
        
        _, self.fgMasks[cam_index] = cv.threshold(
            diff,
            self.calibration[cam_index]["threshold"],
            255,
            cv.THRESH_BINARY
        )


        #image processing on diff frame to remove noise etc
        kernel = np.ones((3, 3), np.uint8)
        #self.fgMasks[cam_index] = cv.morphologyEx(self.fgMasks[cam_index], cv.MORPH_OPEN, kernel)

        self.fgMasks[cam_index] = cv.morphologyEx(self.fgMasks[cam_index], cv.MORPH_OPEN, np.ones((3,3), np.uint8))
        self.fgMasks[cam_index]= cv.dilate(self.fgMasks[cam_index], np.ones((3,3), np.uint8), iterations=1)

        #kernel = cv.getStructuringElement(cv.MORPH_RECT, (3, 3))
        #self.fgMasks[cam_index] = cv.morphologyEx(self.fgMasks[cam_index], cv.MORPH_CLOSE, kernel)

        #set the threshold diff frame to only the ROI
        if self.intersect:
            self.current_frames_roi[cam_index] = self.fgMasks[cam_index][
                self.calibration[cam_index]["roi_y"] : self.calibration[cam_index]["roi_y"] + self.calibration[cam_index]["roi_h"],
                self.calibration[cam_index]["roi_x"] : self.calibration[cam_index]["roi_x"] + self.calibration[cam_index]["roi_w"]
            ]
        else:
            self.current_frames_roi[cam_index] = self.fgMasks[cam_index][
                self.calibration[cam_index]["roi_y"] : self.calibration[cam_index]["threshold_y"]+ self.calibration[cam_index]["roi_y"] + self.calibration[cam_index]["roi_h"],
                self.calibration[cam_index]["roi_x"] : self.calibration[cam_index]["roi_x"] + self.calibration[cam_index]["roi_w"]
            ]
        
        _, self.fgMasks_move[cam_index] = cv.threshold(
            diff_move,
            self.calibration[cam_index]["threshold"],
            255,
            cv.THRESH_BINARY
        )


    def get_intersection(self, x_bot, x_top, y_bot,y_top,cam_index):
        '''
        Returns the x coor intersection of the tip of the dart with the surface of the dartboard
        '''
        if x_bot == x_top:  # vertical line case
            x_intersect = x_bot
        else:
            m = (y_bot - y_top) / (x_bot - x_top)
            b = y_top - m * x_top
            x_intersect = (self.calibration[cam_index]["threshold_y"] - b) / m

        self.plot_data[cam_index]["x_top"] = x_top
        self.plot_data[cam_index]["x_bot"]  = x_bot

        return x_intersect

    #TODO: CAN THREAD THIS CODE PROBABLY
    def process_contour(self, cam_index):
        '''
        Process the contours so it can find the dart tip for each cameras
        '''

        self.dart_positions[cam_index] = None
        
        #length = len(self.masks[cam_index])
        #print(f"number of frames:{length} for camera {cam_index} ")

        #process it backwards since we want the "last" momement of the dart
        #hypotheiclaly this should be its last known position
        for frame in reversed(self.masks[cam_index]):
            
            contours, _ = cv.findContours(frame, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)
            contours_with_rect = [(c, cv.boundingRect(c)) for c in contours]
            contours_sorted = sorted(contours_with_rect, key=lambda x: cv.contourArea(x[0]), reverse=True)
            #contours_sorted = sorted(contours_with_rect, key=lambda x: (x[1][1], x[1][0]))
            contours = [c[0] for c in contours_sorted]

            for contour in contours:
                contour = cv.convexHull(contour)
                area = cv.contourArea(contour)
                
                if area > self.min_area:
            
                    print(f"Dart detected! camera {cam_index}, Count: {self.dart_count}")
                    # time.sleep(0.2)

                    y_values = contour[:, :, 1]  # Extract y-coordinates
                    if np.std(y_values) < 1:  # Standard deviation check
                        continue  # Ignore this contour

                    # --- Bottom Point ---
                    y_bot = int(np.max(y_values))
                    bottom_points = contour[contour[:, :, 1] == y_bot]
                    
                    y_bot += self.calibration[cam_index]["roi_y"]
                    #print(f"y_bot: {y_bot} for camera {cam_index} ")

                    # Apply bottom ROI threshold
                    bottom_y_threshold = self.plot_data[cam_index]['y_bot']
                    #print(f"y_thresh bot: {bottom_y_threshold} for camera {cam_index} ")
                    if y_bot < bottom_y_threshold:
                        y_bot = bottom_y_threshold  # Clamp to bottom line

                    # --- Top Point ---
                    if self.intersect:
                        y_top = int(np.min(y_values))
                        top_points = contour[contour[:, :, 1] == y_top]

                        y_top+=self.calibration[cam_index]["roi_y"]

                        #print(f"y_top: {y_top} for camera {cam_index} ")

                        # Apply top ROI threshold
                        top_y_threshold = self.plot_data[cam_index]['y_top']
                        #print(f"y_thresh top: {top_y_threshold} for camera {cam_index} ")

                        if y_top > top_y_threshold:
                            y_top = top_y_threshold  # Clamp to top line

                        x_top = int(np.mean(top_points[:, 0]))
                        x_bot = int(np.mean(bottom_points[:, 0]))

                        # Intersect override
                        x_bot = int(self.get_intersection(x_bot, x_top, y_bot, y_top, cam_index))
                    else:
                        x_bot = int(np.mean(bottom_points[:, 0]))

                    # --- Apply ROI calibration offsets ---
                    x_bot += self.calibration[cam_index]["roi_x"]
                    y_bot += self.calibration[cam_index]["roi_y"]

                    # --- Save the corrected dart position ---
                    self.dart_positions[cam_index] = (x_bot, y_bot)

                    #self.update_reference_frame(cam_index)

                    self.shifted_contours[cam_index] = contour + np.array([[[self.calibration[cam_index]["roi_x"], self.calibration[cam_index]["roi_y"]]]])
                 
                    self.processed_dart[cam_index] = True

                    self.false_trigger_count[cam_index] = 0
                    self.movement_duration[cam_index] = 0


                    return True
                        
                else:
                    print("area of contour not great enough for camera: ", cam_index)
                    print(f"camid:{cam_index}, area:{area}")

        print(f"final no area great enough, camid: {cam_index}")
        self.masks[cam_index] = []
        self.is_movement[cam_index] = False
        return False

    def detect_dart(self, cam_index):
        """Detect dart position for a given camera."""
        
        return_value = False

        self.get_threshold(cam_index)

        if self.is_movement[cam_index]:
            nonzero_count = cv.countNonZero(self.fgMasks_move[cam_index])
        else:
            nonzero_count = cv.countNonZero(self.fgMasks[cam_index])

        if nonzero_count != 0:
            print(f"CAM {cam_index}: {nonzero_count}\n")
        

        if self.min_threshold < nonzero_count < self.max_threshold and self.is_takeout is False:
            self.masks[cam_index].append(self.current_frames_roi[cam_index])
            self.num_still_frames[cam_index] = 0
            self.update_movement_frame(cam_index)
            self.is_movement[cam_index] = True
            #self.movement_duration[cam_index] += 1
            self.false_trigger_count[cam_index] += 1
            time.sleep(0.2)
            return_value = True
        elif (nonzero_count > self.max_threshold): #takeout
            # Large movement -> trigger takeout
            if self.is_dart is False and self.is_takeout is False: #need the is_takeout statment since multiple threads can trigger it
                print("Triggering takeout for all cameras bc of camera: ", cam_index)
                self.is_takeout = True #TODO: FIND OUT WHY I HAVE THIS, I THINK ITS FOR THE THREADING
                #self.is_movement = False
                self.trigger_takeout()
        elif nonzero_count == 0:
            #dont think we should set is movment to false here since it affects the checler
            self.is_dart = False
            self.num_still_frames[cam_index]+=1
        else:
            #self.update_reference_frame(cam_index)
            self.is_dart = False
            self.update_movement_frame(cam_index)
            self.num_still_frames[cam_index] = 0

        # Always update movement duration — even if there's no new detection
        if self.is_movement[cam_index]:
            self.movement_duration[cam_index] += 1
        else:
            self.movement_duration[cam_index] = 0

        # Timeout Reset
        if self.is_movement[cam_index] and self.movement_duration[cam_index] > self.max_movement_frames:
            print(f"[Timeout Reset] Cam {cam_index} stuck in movement too long. Resetting...")
            self.reset_camera_state(cam_index)

        # False Trigger Count Reset
        if self.false_trigger_count[cam_index] >= self.false_trigger_limit:
            print(f"[False Trigger Reset] Cam {cam_index} had too many failed detections. Resetting...")
            self.reset_camera_state(cam_index)

        return return_value
            
    def trigger_takeout(self):
        # Reset the dart positions at takeout
        self.dart_positions = {}
        time.sleep(3)
        for cam in range(self.num_cameras):
            start_time = time.time()
            while time.time() - start_time < self.takeout_time:
                self.update_reference_frame(cam)
                self.update_movement_frame(cam)
                
                time.sleep(0.1)
            self.is_movement[cam] = False
            print(f"Takeout procedure completed for camera {cam} \n")
            self.num_still_frames[cam] = 0
            self.masks[cam] = []
            self.false_trigger_count[cam]= 0
            self.movement_duration[cam] = 0
        time.sleep(1)
        
        self.is_takeout = False #TODO: i think the key to avoiding double takeouts is here
        print(f"Takeout done for all cameras: {self.is_takeout}")

    def log_dart_position(self, dart_count, positions):
        """Log dart positions from all cameras into the YAML file."""
        data = {}

        if os.path.exists("configs/scores.yaml"):
            with open("configs/scores.yaml", "r") as file:
                try:
                    data = yaml.safe_load(file) or {}
                except yaml.YAMLError as e:
                    print(f"Error loading YAML: {e}")
                    data = {}
    
        data[f"dart_{dart_count}"] = {
            f"cam{i}": list(positions.get(f"cam{i}")) if positions.get(f"cam{i}") else "N/A"
            for i in range(self.num_cameras)
        }

        with open("configs/scores.yaml", "w") as file:
            yaml.dump(data, file, default_flow_style=False)

        print(f"Dart {dart_count} logged: {data[f'dart_{dart_count}']}")
        self.dart_positions = {}

    def check_no_movement(self):
        '''
        Returns boolean flag that tells us if we cant start processing the contours
        '''
        no_movement_count = 0
        is_move_count = 0
        no_move = False
        no_count = False

        for cam in range(self.num_cameras):
            if self.num_still_frames[cam] >= self.num_still_critea:
                no_movement_count+=1
            if self.is_movement[cam]:
                is_move_count+=1


        #all cameras have to detect no movement
        if no_movement_count >= self.num_cameras:
            no_count = True
        
        if is_move_count >= self.num_cameras - 1:
            no_move = True


        return no_count, no_move
 
    def draw_detection(self, cam_index):

        #apps python can read shared variables so no race coniditon
        if self.debug and self.is_dart and self.current_frames_copy[cam_index] is not None:

            cv.drawContours(self.current_frames_copy[cam_index], [self.shifted_contours[cam_index]], -1, (255, 255, 0), 2)
            # Draw ROI rectangle
            
            cv.rectangle(
                self.current_frames_copy[cam_index],
                (self.calibration[cam_index]["roi_x"], self.calibration[cam_index]["roi_y"]),
                (
                    self.calibration[cam_index]["roi_x"] + self.calibration[cam_index]["roi_w"],
                    self.calibration[cam_index]["roi_y"] + self.calibration[cam_index]["roi_h"]
                ),
                (255, 255, 0), 2
            )

            # Draw threshold line
            cv.line(
                self.current_frames_copy[cam_index],
                (0, self.calibration[cam_index]["threshold_y"]),
                (self.current_frames_copy[cam_index].shape[1], self.calibration[cam_index]["threshold_y"]),
                (0, 0, 255), 2
            )


            if self.dart_positions[cam_index] != None:

                text = f"x coor {self.dart_positions[cam_index][0]}"
                position = (50, 50)  # (x, y)
                font = cv.FONT_HERSHEY_SIMPLEX
                font_scale = 1
                color = (0, 255, 0)  # Green in BGR
                thickness = 2

                # Add text to the frame
                cv.putText(self.current_frames_copy[cam_index], text, position, font, font_scale, color, thickness)

                #final intersection points
                cv.circle(
                    self.current_frames_copy[cam_index],
                    (int(self.dart_positions[cam_index][0]), self.calibration[cam_index]["threshold_y"]),
                    4, (255, 0, 0), -1
                )

                if self.intersect:

                    # Draw green line between bottom and top points
                    cv.line(
                        self.current_frames_copy[cam_index],
                        (self.plot_data[cam_index]['x_bot'], self.plot_data[cam_index]['y_bot']),
                        (self.plot_data[cam_index]['x_top'], self.plot_data[cam_index]['y_top']),
                        (0, 255, 0),  # Green color in BGR
                        1             # Thickness of the line
                    )

                    # Draw bottom circle 
                    cv.circle(
                        self.current_frames_copy[cam_index],
                        (self.plot_data[cam_index]['x_bot'] , self.plot_data[cam_index]['y_bot']),
                        3,
                        (0, 0, 255),
                        -1
                    )

                    # Draw top circle 
                    cv.circle(
                        self.current_frames_copy[cam_index],
                        (self.plot_data[cam_index]['x_top'], self.plot_data[cam_index]['y_top']),
                        3,
                        (0, 255, 0),
                        -1
                    )

    def reset_camera_state(self, cam_index):
        self.is_movement[cam_index] = False
        self.masks[cam_index] = []
        self.num_still_frames[cam_index] = 0
        self.update_movement_frame(cam_index)
        self.update_reference_frame(cam_index)
        self.false_trigger_count[cam_index] = 0
        self.movement_duration[cam_index] = 0

    def run_loop(self):
        """Main loop for detecting darts in real-time."""
        for cam_index in range(self.num_cameras):
            self.update_reference_frame(cam_index)
            self.update_movement_frame(cam_index)
        time.sleep(5)
        for cam_index in range(self.num_cameras):
            self.update_reference_frame(cam_index)
            self.update_movement_frame(cam_index)

        print("Background stabilization done --> Start to throw darts !!! ")

        frame_counter = 0
        cameras = [0,1,2,3]
        start_index = 0

        while self.success:
            time.sleep(0.2)
            cameras_order = [(start_index + i) % len(cameras) for i in range(len(cameras))]

            # Run dart detection concurrently for all cameras
        
            with ThreadPoolExecutor(max_workers=len(cameras)) as executor:
                futures = {
                    executor.submit(self.detect_dart, cam): cam
                    for cam in cameras_order
                }
                cameras_with_dart = []

                # Gather all results (in the order tasks complete)
                for future in as_completed(futures):
                    cam = futures[future]
                    is_movement = future.result()

                    if is_movement:
                        cameras_with_dart.append(cam)

                if cameras_with_dart:
                    #skip rest of deteciton logic
                    if self.is_takeout:
                        for cam in range(self.num_cameras):
                            self.reset_camera_state(cam)
                        continue
                    # We only care about the "first" camera in the circular order
                    # that found a dart.
                    # cameras_with_dart is in order of completion, not necessarily circular order,
                    # so we figure out which is earliest in cameras_order:
                    earliest_cam = None
                    for cam in cameras_order:
                        if cam in cameras_with_dart:
                            earliest_cam = cam
                            break

                    # earliest_cam is the “first in circular order” that detected a dart
                    #print(f"Detected a dart in camera {earliest_cam}. Updating start_index.")
                    start_index = earliest_cam

                    # this loops back to the begging of the while loop
                    continue


                
            num_dart_found = 0

            bool1,bool2 = self.check_no_movement()

            if bool1 and bool2:
                with ThreadPoolExecutor(max_workers=len(cameras)) as executor:
                    futures = [
                        executor.submit(self.process_contour, cam)
                        for cam in cameras
                    ]

                    for future in futures:
                        if future.result():  # This waits for the result and checks it ( so no race condiiton)
                            num_dart_found += 1

                    if num_dart_found >= 2:
                        data = {}
                        self.is_dart = True
                        for i in range(self.num_cameras):
                            if self.dart_positions[i] is not None:
                                data[f"cam{i}"] = list(self.dart_positions[i])
                            else:
                                data[f"cam{i}"] = "NA"
                            self.update_reference_frame(i)
                            self.update_movement_frame(i)

                        self.time_stamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                        score, multiplier, r, theta, self.x, self.y = self.score_calculator.calculate_score(self.dart_count, data)
                        self.last_score = (self.time_stamp,score,multiplier,[r,theta])

                        print(f"Dart {self.dart_count} logged: {data}")
                        print(f"Score: {score}, multiplier: {multiplier}")
                        #self.plotter.visualize_board(dart_positions=[(self.x, self.y)])


                        #self.log_dart_position(self.dart_count, data)
                        self.dart_count += 1
                        self.is_movement = [False] * self.num_cameras
                        self.num_still_frames = [0] * self.num_cameras
                        self.masks = [[] for _ in range(self.num_cameras)]
                        self.processed_dart = [False] * self.num_cameras
                        self.false_trigger_count = [0] * self.num_cameras
                        self.movement_duration = [0] * self.num_cameras
                        
                        time.sleep(0.5)  # Small delay to prevent double-detection
                    else:
                        self.is_movement = [False] * self.num_cameras
                        self.masks = [[] for _ in range(self.num_cameras)]

                self.is_movement = [False] * self.num_cameras
                self.false_trigger_count = [0] * self.num_cameras
                self.movement_duration = [0] * self.num_cameras
                self.masks = [[] for _ in range(self.num_cameras)]
                


            
            with ThreadPoolExecutor(max_workers=self.num_cameras) as executor:
                #TODO: MAYBE FIND A DIFF PLACE TO UPDATE THE SELF.COPY_FRAME
                executor.map(self.draw_detection, range(self.num_cameras))

            for cam_index in range(self.num_cameras):
                #cv.imshow(f'Cam{cam_index} Live Feed', self.current_frames[cam_index])
                #cv.imshow(f'Cam{cam_index} Move Mask Feed ',  self.fgMasks_move[cam_index])
                #cv.imshow(f'Cam{cam_index} Mask Feed',  self.fgMasks[cam_index])
                #cv.imshow(f'Cam{cam_index} Mask Feed',  self.current_frames_roi[cam_index])
                #cv.imshow(f'Cam{cam_index} Ref Feed', self.reference_frames[cam_index])
                #cv.imshow(f'Cam{cam_index} Threshsold', self.frames_thresh_current[cam_index])
                if self.debug and self.current_frames_copy[cam_index] is not None and self.is_dart:
                    cv.imshow(f'Camera: {cam_index} Detected Darts', self.current_frames_copy[cam_index])
                    
                    self.current_frames_copy[cam_index] = None
                    self.shifted_contours[cam_index] = None

            # Reset reference frames periodically
            if frame_counter % self.frame_update == 0:
                for cam_index in range(self.num_cameras):
                    if self.is_movement[cam_index] is False:
                        self.update_reference_frame(cam_index)
                        self.update_movement_frame(cam_index)
            frame_counter += 1



            self.dart_positions = {}
            self.is_dart = False

            if cv.waitKey(1) & 0xFF == ord('q'):
                break

        for stream in self.streams:
            stream.release()

        cv.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Real time detection")
    parser.add_argument("-d", action="store_true", help="Boolean to show debug frames")
    parser.add_argument("-i", action="store_true", help="Boolean to use interesect method")
    args = parser.parse_args()
    detector = DartDetectionLive(args.d, args.i)
    detector.run_loop()
