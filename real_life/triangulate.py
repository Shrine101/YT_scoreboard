import numpy as np
from typing import List, Tuple, Optional, Callable
import matplotlib.pyplot as plt
import json
import yaml
import math
from dartboard_scoring import *

class DartPositionFinder:
    def __init__(self, num_cameras: int = 4, angle_spacing: float = 36, 
                 board_radius: float = 225.5, scoring_radius: float = 170,  # 451mm/2 and 340mm/2
                 camera_distance_factor: float = 1.9,
                 camera_distance: float = 508,
                 distortion_func: Optional[Callable[[float], float]] = None):
        """
        Initialize the dart position finder with camera positions.
        
        Args:
            num_cameras: Number of cameras
            angle_spacing: Angle between cameras in degrees
            board_radius: Total physical radius of the dart board in cm
            scoring_radius: Radius of the scoring area in cm
            camera_distance_factor: Factor of board radius at which cameras are placed
            distortion_func: Optional function to model camera distortion
                           Takes normalized position (0-1) and returns corrected position
        """
        self.num_cameras = num_cameras
        self.angle_spacing = np.deg2rad(angle_spacing)
        self.board_radius = board_radius
        self.scoring_radius = scoring_radius
        #self.camera_radius = board_radius * camera_distance_factor
        self.camera_radius = board_radius + camera_distance
        self.distortion_func = distortion_func or (lambda x: x)  # Identity function if None
        
        self.dart_camera_pixels_current = [[],[],[],[]]
        self.dart_camera_views_current = [[],[],[],[]]
        self.camera_bounds = [[],[],[],[]]
        self.crit_angle_20in = 17.089
        self.crit_angle_21in = 16.549
        self.crit_angle_21_625in = 16.228
        self.crit_angle_18_375in = 18.044
        # crit angle = abs(arctan(225.5/(225.5+511)))
        self.crit_angle_511mm = 17.023
        self.crit_angle_508mm = 17.089
        self.crit_angle_510mm = 17.045
        #self.critical_angles = [self.crit_angle_511mm, self.crit_angle_508mm, self.crit_angle_510mm, self.crit_angle_508mm]
        #self.camera_distances = [511, 508, 510, 508]
        # only change following line for if cameras are at slightly different distances from bullseye
        self.camera_distances = [516, 510, 506, 505]
        self.crit_angle0 = math.degrees(math.atan(225.5/(225.5+self.camera_distances[0])))
        self.crit_angle1 = math.degrees(math.atan(225.5/(225.5+self.camera_distances[1])))
        self.crit_angle2 = math.degrees(math.atan(225.5/(225.5+self.camera_distances[2])))
        self.crit_angle3 = math.degrees(math.atan(225.5/(225.5+self.camera_distances[3])))
        self.critical_angles = [self.crit_angle0, self.crit_angle1, self.crit_angle2, self.crit_angle3]
        # only change following 4 lines if cameras are placed at different angles
        self.camera0angle = 144
        self.camera1angle = 108
        self.camera2angle = 72
        self.camera3angle = 36
        self.camera_angles = [self.camera0angle, self.camera1angle, self.camera2angle, self.camera3angle]
        #self.cam_locations = [[-593.414,431.140],[-226.664,697.600],[226.664,697.600], [593.414,431.140]]
        # [(camera_dist + 225.5) * cos144, (camera_dist + 225.5) * sin144, (camera_dist + 225.5) * cos108, (camera_dist + 225.5) * sin108, (camera_dist + 225.5) * cos72, (camera_dist + 225.5) * sin72, (camera_dist + 225.5) * cos36, (camera_dist + 225.5) * sin36]
        self.camera0location_x = (225.5+self.camera_distances[0]) * math.cos(math.radians(self.camera_angles[0]))
        self.camera0location_y = (225.5+self.camera_distances[0]) * math.sin(math.radians(self.camera_angles[0]))
        self.camera1location_x = (225.5+self.camera_distances[1]) * math.cos(math.radians(self.camera_angles[1]))
        self.camera1location_y = (225.5+self.camera_distances[1]) * math.sin(math.radians(self.camera_angles[1]))
        self.camera2location_x = (225.5+self.camera_distances[2]) * math.cos(math.radians(self.camera_angles[2]))
        self.camera2location_y = (225.5+self.camera_distances[2]) * math.sin(math.radians(self.camera_angles[2]))
        self.camera3location_x = (225.5+self.camera_distances[3]) * math.cos(math.radians(self.camera_angles[3]))
        self.camera3location_y = (225.5+self.camera_distances[3]) * math.sin(math.radians(self.camera_angles[3]))
        #self.cam_locations = [[-595.841, 432.904],[-226.664, 697.600],[227.282, 699.502], [593.414, 431.140]]
        self.cam_locations = [[self.camera0location_x, self.camera0location_y],[self.camera1location_x, self.camera1location_y],[self.camera2location_x, self.camera2location_y], [self.camera3location_x, self.camera3location_y]]

        #self.cam_locations = [[-593.414,431.140],[-226.664,697.600],[226.664,697.600], [593.414,431.140]]
        # [(camera_dist + 225.5) * cos144, (camera_dist + 225.5) * sin144, (camera_dist + 225.5) * cos108, (camera_dist + 225.5) * sin108, (camera_dist + 225.5) * cos72, (camera_dist + 225.5) * sin72, (camera_dist + 225.5) * cos36, (camera_dist + 225.5) * sin36]
        #self.cam_locations = [[-595.841, 432.904],[-226.664, 697.600],[227.282, 699.502], [593.414, 431.140]]
        self.cam_lines = [(),(),(),()]
        self.cam_lines_updated = [(),(),(),()]
        self.dart_positions = [[],[],[],[]]
        self.factor = 1.066 #if the real dart is further from the center than it thinks, increase this value

        with open("configs/dart_positions.yaml", "r") as file:
            data = yaml.safe_load(file)
    
        cam1bounds = data["cam0_bounds"]
        cam2bounds = data["cam2_bounds"]
        cam3bounds = data["cam4_bounds"]
        cam4bounds = data["cam6_bounds"]

        cambounds = [cam1bounds, cam2bounds, cam3bounds, cam4bounds]

        for i in range(4):
            self.camera_bounds[i] = cambounds[i]
        
        # Calculate camera positions and their perpendicular viewing lines
        self.camera_positions = []
        self.camera_angles = []
        for i in range(num_cameras):
            angle = i * self.angle_spacing
            self.camera_positions.append((
                self.camera_radius * np.cos(angle),
                self.camera_radius * np.sin(angle)
            ))
            # Camera angles point inward
            self.camera_angles.append(angle + np.pi)
        #print(self.camera_positions)
        
        self.double_bull_radius = 6.35   # 12.7mm diameter
        self.bull_radius = 16          # 32mm diameter
        self.triple_inner_radius = 99   # 198mm diameter
        self.triple_outer_radius = 107   # 214mm diameter
        self.double_inner_radius = 162   # 324mm diameter
        self.double_outer_radius = 170  # 340mm diameter

        # Standard scoring segments (clockwise from top, 20 is at top)
        self.segments = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]

    def normalized_to_lateral(self, normalized_pos: float) -> float:
        """Convert normalized position (0-1) to lateral distance from camera centerline."""
        # Apply distortion correction
        corrected_pos = self.distortion_func(normalized_pos)
        # Convert from 0-1 range to actual lateral distance
        return (2 * corrected_pos - 1) * self.board_radius

    def point_in_scoring_area(self, point: Tuple[float, float]) -> bool:
        """Check if a point lies within the scoring area."""
        return np.sqrt(point[0]**2 + point[1]**2) <= self.scoring_radius
    
    def point_in_board(self, point: Tuple[float, float]) -> bool:
        """Check if a point lies within the physical board."""
        return np.sqrt(point[0]**2 + point[1]**2) <= self.board_radius

    def validate_readings(self, camera_readings: List[List[float]]) -> bool:
        """
        Validate camera readings format and values.
        
        Args:
            camera_readings: List of lists of normalized positions (0-1) from each camera
            
        Returns:
            bool: True if readings are valid
            
        Raises:
            ValueError: If readings are invalid, with explanation
        """
        # Check number of cameras
        if len(camera_readings) != self.num_cameras:
            raise ValueError(f"Expected {self.num_cameras} cameras, got {len(camera_readings)}")
            
        # Get number of darts (length of first camera's readings)
        if not camera_readings[0]:
            return True  # Empty readings are valid (no darts)
            
        num_darts = len(camera_readings[0])
        if num_darts > 3:
            raise ValueError(f"Maximum 3 darts allowed, got {num_darts}")
            
        # Check each camera's readings
        for i, readings in enumerate(camera_readings):
            # Check number of readings matches first camera
            if len(readings) != num_darts:
                raise ValueError(f"Camera {i} has {len(readings)} readings, expected {num_darts}")
                
            # Check each reading is in valid range (0 to 1)
            for j, pos in enumerate(readings):
                if not (0 <= pos <= 1):
                    raise ValueError(
                        f"Camera {i}, reading {j}: position {pos:.3f} is outside "
                        f"valid range (0 to 1)"
                    )
        
        return True

    def camera_line_equation(self, camera_idx: int, normalized_pos: float) -> Tuple[float, float, float]:
        """
        Get the line equation (ax + by + c = 0) for a camera's view line.
        
        Args:
            camera_idx: Index of the camera
            normalized_pos: Position from 0 (leftmost) to 1 (rightmost) in camera's view
            
        Returns:
            Tuple of (a, b, c) for line equation ax + by + c = 0
        """
        camera_angle = self.camera_angles[camera_idx]
        camera_pos = self.camera_positions[camera_idx]
        
        # Convert normalized position to lateral distance
        lateral_dist = self.normalized_to_lateral(normalized_pos)
        
        # Direction vector of camera's view (perpendicular to camera angle)
        dx = -np.sin(camera_angle)
        dy = np.cos(camera_angle)
        
        # Point on the view line at the given lateral distance
        point_on_line = (
            camera_pos[0] + lateral_dist * dx,
            camera_pos[1] + lateral_dist * dy
        )
        
        # Line equation coefficients
        a = dx
        b = dy
        c = -(a * point_on_line[0] + b * point_on_line[1])
        
        return (a, b, c)

    def line_intersection(self, line1: Tuple[float, float, float], 
                         line2: Tuple[float, float, float]) -> Optional[Tuple[float, float]]:
        """Find intersection of two lines given by their equations ax + by + c = 0."""
        a1, b1, c1 = line1
        a2, b2, c2 = line2
        
        if a1 == 0 and b1 == 0 and c1 == 0 or a2 == 0 and b2 == 0 and c2 == 0:
            return None
        
        det = a1 * b2 - a2 * b1
        if abs(det) < 1e-10:  # Lines are parallel
            return None
            
        x = (b1 * c2 - b2 * c1) / det
        y = (a2 * c1 - a1 * c2) / det
        
        return (x, y)

        
    def find_max_list(self, x_list):
        max_list_len = 0
        for lis in x_list:
            if len(lis) > max_list_len:
                max_list_len = len(lis)
        return max_list_len

    def get_updated_lines(self, dartxys):
        for camnum in range(0, 4):
            for i, n in enumerate(self.dart_camera_views_current[camnum]):
                if n != "N":
                    # ✅ Use corrected (scaled) coordinates instead of cam_locations
                    x = dartxys[i][0]
                    y = dartxys[i][1]

                    angle = (-1 * (n - 0.5)) * 2 * self.critical_angles[camnum] - (camnum + 1) * 36
                    slope = np.tan(angle * math.pi / 180)
                    yint = y - slope * x

                    a = slope
                    b = -1
                    c = yint
                else:
                    a = 0
                    b = 0
                    c = 0

                lines = list(self.cam_lines_updated[camnum])
                lines.append([a, b, c])
                self.cam_lines_updated[camnum] = tuple(lines)
        
    def find_dart_positions_good(self, camlines: List[List[float]], 
                          tolerance: float = 0.1) -> List[Tuple[float, float]]:
        """
        Find dart positions from camera readings.
        
        Args:
            camera_readings: List of lists of normalized positions (0-1) from each camera.
                           0 = leftmost possible position in camera's view
                           1 = rightmost possible position in camera's view
            tolerance: Maximum distance between intersection points to be considered
                      the same dart
                      
        Returns:
            List of (x, y) positions for each detected dart (maximum 3)
        """
        
        intersections = []
        num_darts = self.find_max_list(camlines)
        xqc = 0
        # For each possible dart
        for dart_idx in range(num_darts):
            # Get all pairwise intersections for this dart
            dart_intersections = []
            
            # Compare each pair of cameras
            for i in range(self.num_cameras):
                for j in range(i + 1, self.num_cameras):
                    # Get line equations for both cameras' views of this dart
                    try:
                        line1 = camlines[i][dart_idx]
                        line2 = camlines[j][dart_idx]
                        #line1 = self.camera_line_equation(i, camera_readings[i][dart_idx])
                        #line2 = self.camera_line_equation(j, camera_readings[j][dart_idx])
                        
                        # Find intersection
                        intersection = self.line_intersection(line1, line2)
                        if intersection and self.point_in_board(intersection):
                            dart_intersections.append(intersection)
                    finally:
                        #print("NA line detected")
                        xqc += 1
            # If we found valid intersections for this dart
            if dart_intersections:
                # Average all intersection points for this dart
                avg_pos = (
                    np.mean([p[0] for p in dart_intersections]),
                    np.mean([p[1] for p in dart_intersections])
                )
                if self.point_in_board(avg_pos):
                    intersections.append(avg_pos)
        
        return intersections
        
        
    def normal_x_coords(self, cam_positions, cam_bounds):
        i=0
        for coord in cam_positions:
            #print(coord)
            if coord != "N":
                cam_positions[i] = (int(coord)-int(cam_bounds[i][0])) / (int(cam_bounds[i][1])-int(cam_bounds[i][0]))
            i+=1
        return cam_positions
        
    def get_lines(self):
        for camnum in range(0,4):
            for n in self.dart_camera_views_current[camnum]:
                if n != "N":
                    x = self.cam_locations[camnum][0]
                    y = self.cam_locations[camnum][1]
                    angle = (-1 * (n-0.5)) *2*self.critical_angles[camnum] - (camnum+1)*36 
                    slope = np.tan(angle*math.pi/180)
                    yint = y - slope*x
                    a = slope
                    b = -1
                    c = yint
                else:
                    a = 0
                    b = 0
                    c = 0
                lines = list(self.cam_lines[camnum])
                lines.append([a,b,c])
                self.cam_lines[camnum] = tuple(lines)
                #print(str(round(a,6)) + "x + " + str(round(b,6)) + "y + " + str(round(c,6)) + " = 0")
                
    def three_to_one_darts(self):
        for i in range(4):
            self.dart_camera_pixels_current = [[],[],[],[]]
            self.dart_camera_views_current = [[],[],[],[]]
            self.cam_lines[i] = ()
            
    def update_dart_camera_views_current(self, cams):
        for i in range(4):
            self.dart_camera_views_current[i].append(cams[i])
            
    def change_camera_factor(self, new_factor):
        self.factor = new_factor
        
    def correct_radius(self, dart_num, dart_coordinates):
        i=0
        dartxys = []
        
        for m in range(dart_num):
            dartxys.append([])
        for dart in dart_coordinates:
            x_old = dart[0]
            y_old = dart[1]
            r_old = math.sqrt(x_old**2 + y_old**2)
            r_new = self.factor*r_old
            x_new = r_new*x_old/r_old
            y_new = r_new*y_old/r_old
            dartxys[i].append(x_new)
            dartxys[i].append(y_new)
            i+=1
        return dartxys
        
    def get_score(self, x, y):
        """
        Determine the score for a dart at given x,y coordinates.
        
        Args:
            x: X coordinate in mm from center
            y: Y coordinate in mm from center
            
        Returns:
            str: Score description (e.g., "DOUBLE 20", "TRIPLE 5", "BULL", "DOUBLE BULL")
                 or "MISS" if outside scoring area
        """
        score = 0
        multiplier = 1
        # Calculate distance from center and angle
        distance = np.sqrt(x**2 + y**2)
        # Fix mirroring by removing the negative x, and add 9 degree rotation
        angle = (np.degrees(np.arctan2(x, y)) + 9) % 360  # Convert to 0-360 degrees, 0 at top
                    
        if distance > self.double_outer_radius:
            multiplier = 0
        elif distance <= self.bull_radius:
            score = 25
            if distance <= self.double_bull_radius:
                multiplier = 2            
        else:
            segment_index = int(angle / 18)  # 360 degrees / 20 segments = 18 degrees per segment
            segment_number = self.segments[segment_index]
            score = segment_number
            # Determine multiplier (double/triple)
            if self.triple_inner_radius <= distance <= self.triple_outer_radius:
                multiplier = 3
            elif self.double_inner_radius <= distance <= self.double_outer_radius:
                multiplier = 2
        return score, multiplier
        
    def calculate_score(self, dart_count, dart_positions):
        # print("benji cde")
        # print(dart_positions)
        dart_num = dart_count % 3
        if dart_num == 0:
            dart_num = 3
        
        cams = [dart_positions["cam0"][0], dart_positions["cam1"][0], dart_positions["cam2"][0], dart_positions["cam3"][0]] # get un-normalized camera pixel coordinates of newest dart        
        if dart_num == 1:
            self.three_to_one_darts() # clear global variable storing camera dart readings (board has been cleared) 
            self.dart_camera_pixels_current = cams
        elif dart_num == 2:
            for pos in range(4):
                if cams[pos] == "N":
                    cams[pos] = self.dart_camera_pixels_current[pos]
                self.cam_lines[pos] = ()
        elif dart_num == 3:
            for pos in range(4):
                #self.dart_camera_pixels_current[pos].append(cams[pos])
                self.cam_lines[pos] = ()
        
        cams = self.normal_x_coords(cams, self.camera_bounds) # normalize dart coordinate to 0-1
        self.update_dart_camera_views_current(cams) # update global variable storing camera dart readings with nth dart
        self.get_lines() # add lines from each camera to dart to global variable storing such lines
        intersections = self.find_dart_positions_good(self.cam_lines) # get intersections of all lines and corresponding predicted dart positions from all globabl lines
         
        intersections = self.correct_radius(dart_num, intersections)
        self.get_updated_lines(intersections)
        x = intersections[dart_num - 1][0]
        y = intersections[dart_num - 1][1]
        r = math.sqrt(x**2 + y**2)
        theta = math.degrees(math.atan(y/x))
        score, multiplier = self.get_score(x,y)
        return score, multiplier, r, theta, x, y
        
    def set_bounds(self, bounds):
        for i in range(4):
            self.camera_bounds[i] = bounds[i]
            

# Example usage with 3 darts and optional distortion
if __name__ == "__main__":
    # Example of a barrel distortion function (disabled by default)
    def barrel_distortion(x: float, strength: float = 0.2) -> float:
        """
        Apply barrel distortion to normalized position.
        strength = 0: no distortion
        strength > 0: barrel distortion
        """
        return x + strength * (x - 0.5) * (x - 1) * x
    
    # Create finder instance with no distortion (using real dartboard measurements)
    finder = DartPositionFinder(
        board_radius=225.5,    # 451mm diameter / 2
        scoring_radius=170,  # 340mm diameter / 2
        camera_distance_factor=1.9,
        camera_distance = 508,
        # distortion_func=lambda x: barrel_distortion(x, 0.2)  # Enable to test distortion
    )
    
    with open("configs/dart_positions.yaml", "r") as file:
        data = yaml.safe_load(file)
    
    cam1bounds = data["cam0_bounds"]
    cam2bounds = data["cam2_bounds"]
    cam3bounds = data["cam4_bounds"]
    cam4bounds = data["cam6_bounds"]


    with open("configs/scores.yaml", "r") as file:
        data_darts = yaml.safe_load(file)

    cams = data_darts['dart_1']

    cam_keys = list(cams.keys())

    darts = {}
    for i in range(len(cam_keys)):
        darts[cam_keys[i]] = cams[cam_keys[i]]
    
    print(darts)

    cambounds = [cam1bounds, cam2bounds, cam3bounds, cam4bounds]
    finder.set_bounds(cambounds)
    score, multiplier, r, theta, x, y = finder.calculate_score(1, darts)

    plotter = DartboardScoringVisualizer(finder.cam_lines_updated, [(x,y)])
    plotter.visualize_lines()