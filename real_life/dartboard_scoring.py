import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from matplotlib.patches import *
import json

class DartboardScoringVisualizer:
    def __init__(self, lines=None, pos=None):
        self.dart_positions = pos
        self.cam_lines = lines
        # Dartboard dimensions (mm)
        self.double_bull_radius = 6.35
        self.bull_radius = 16
        self.triple_inner_radius = 99
        self.triple_outer_radius = 107
        self.double_inner_radius = 162
        self.double_outer_radius = 170
        self.segments = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17,
                         3, 19, 7, 16, 8, 11, 14, 9, 12, 5]

    def get_score(self, x: float, y: float) -> str:
        """
        Determine the score for a dart at given x,y coordinates.
        
        Args:
            x: X coordinate in mm from center
            y: Y coordinate in mm from center
            
        Returns:
            str: Score description (e.g., "DOUBLE 20", "TRIPLE 5", "BULL", "DOUBLE BULL")
                 or "MISS" if outside scoring area
        """
        # Calculate distance from center and angle
        distance = np.sqrt(x**2 + y**2)
        # Fix mirroring by removing the negative x, and add 9 degree rotation
        angle = (np.degrees(np.arctan2(x, y)) + 9) % 360  # Convert to 0-360 degrees, 0 at top
        
        # Check if it's a miss (outside double ring)
        if distance > self.double_outer_radius:
            return "MISS"
            
        # Check for double bull (center)
        if distance <= self.double_bull_radius:
            return "DOUBLE BULL"
            
        # Check for bull (outer bull)
        if distance <= self.bull_radius:
            return "BULL"
            
        # Determine which segment (1-20) was hit
        segment_index = int(angle / 18)  # 360 degrees / 20 segments = 18 degrees per segment
        segment_number = self.segments[segment_index]
        
        # Determine multiplier (double/triple)
        if self.triple_inner_radius <= distance <= self.triple_outer_radius:
            return f"TRIPLE {segment_number}"
        elif self.double_inner_radius <= distance <= self.double_outer_radius:
            return f"DOUBLE {segment_number}"
        else:
            return str(segment_number)

    def get_score_value(self, score_str: str) -> int:
        """Convert score string to numerical value."""
        if score_str == "MISS":
            return 0
        elif score_str == "DOUBLE BULL":
            return 50
        elif score_str == "BULL":
            return 25
        else:
            parts = score_str.split()
            if len(parts) == 1:  # Single
                return int(parts[0])
            elif parts[0] == "DOUBLE":
                return 2 * int(parts[1])
            else:  # TRIPLE
                return 3 * int(parts[1])

    def visualize_lines(self, save_path: str = '../output/dartboard_scoring.png'):
        """Visualize dartboard, dart positions, and camera lines with square markers."""
        fig, ax = plt.subplots(figsize=(12, 12))

        # Draw dartboard scoring rings
        circles = [
            (self.double_outer_radius, 'black', 'Double Ring'),
            (self.double_inner_radius, 'black', ''),
            (self.triple_outer_radius, 'black', 'Triple Ring'),
            (self.triple_inner_radius, 'black', ''),
            (self.bull_radius, 'green', 'Bull'),
            (self.double_bull_radius, 'red', 'Double Bull')
        ]
        for radius, color, label in circles:
            ax.add_patch(Circle((0, 0), radius, fill=False, color=color, linewidth=3,
                                label=label if label else None))

        # Draw segment lines and labels
        for i in range(20):
            angle = np.radians(i * 18 - 9)
            dx = np.sin(angle) * self.double_outer_radius
            dy = np.cos(angle) * self.double_outer_radius
            ax.plot([0, dx], [0, dy], 'k-', linewidth=0.5)

            text_angle = np.radians(i * 18)
            text_r = self.double_outer_radius + 10
            tx = np.sin(text_angle) * text_r
            ty = np.cos(text_angle) * text_r
            ax.text(tx, ty, str(self.segments[i]), ha='center', va='center')

        # Plot dart positions
        if self.dart_positions:
            for i, (x, y) in enumerate(self.dart_positions):
                score = self.get_score(x, y)
                ax.plot(x, y, 'ro', markersize=5, label=f'Dart {i+1}: {score}')

        # Camera positions based on target segments
        target_segments = [9, 5, 1, 4]  # Camera targets
        segment_indices = [self.segments.index(s) for s in target_segments]
        cam_distance = self.double_outer_radius + 350  # mm from center
        cam_colors = ['red', 'green', 'blue', 'orange']

        cam_positions = []
        for index in segment_indices:
            angle_rad = np.radians(index * 18)
            cam_x = cam_distance * np.sin(angle_rad)
            cam_y = cam_distance * np.cos(angle_rad)
            cam_positions.append((cam_x, cam_y))

        # Plot camera squares and camera lines
        for cam_idx, (cam_x, cam_y) in enumerate(cam_positions):
            color = cam_colors[cam_idx % len(cam_colors)]

            # Plot all lines from this camera
            if cam_idx < len(self.cam_lines):
                for line_idx, (a, b, c) in enumerate(self.cam_lines[cam_idx]):
                    if a == 0 and b == 0:
                        continue  # Skip dummy line

                    x_vals = np.linspace(-600, 600, 400) #edit line length
                    if b != 0:
                        y_vals = (-a * x_vals - c) / b
                    else:
                        x_vals = np.full(500, -c / a)
                        y_vals = np.linspace(-300, 300, 500)

                    ax.plot(x_vals, y_vals, linestyle='--', color=color, alpha=0.4, linewidth=4, 
                            label=f'Cam {cam_idx+1} Line {line_idx+1}' if line_idx == 0 else "")

        # Final formatting
        ax.set_aspect('equal')
        ax.grid(True)
        ax.set_title('Dartboard Score Visualization')
        ax.set_xlabel('X Position (mm)')
        ax.set_ylabel('Y Position (mm)')

        limit = self.double_outer_radius + 100
        ax.set_xlim(-limit, limit)
        ax.set_ylim(-200, limit)

        # Clean legend
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), loc='upper right', bbox_to_anchor=(1.25, 1.0))

        plt.legend()
        plt.savefig(save_path)
        plt.close()
        print(f"Plot saved: '{save_path}'")



    

    def visualize_board(self, dart_positions: list[tuple[float, float]] = None,
        save_path: str = 'dartboard_scoring.png'):
        """Visualize dartboard with optional dart positions."""
        plt.figure(figsize=(12, 12))
        
        # Draw circles for different scoring regions
        circles = [
            (self.double_outer_radius, 'black', 'Double Ring'),
            (self.double_inner_radius, 'black', 'Double inner Ring'),
            (self.triple_outer_radius, 'black', 'Triple Ring'),
            (self.triple_inner_radius, 'black', 'Triple inner ring'),
            (self.bull_radius, 'green', 'Bull'),
            (self.double_bull_radius, 'red', 'Double Bull')
        ]
        
        for radius, color, label in circles:
            circle = plt.Circle((0, 0), radius, fill=False, color=color,
                              label=label if label else None)
            plt.gca().add_artist(circle)
        
        # Draw segment lines and numbers with 9 degree offset
        for i in range(20):
            angle = np.radians(i * 18 - 9)  # 18 degrees per segment, -9 for correct orientation
            dx = np.sin(angle) * self.double_outer_radius
            dy = np.cos(angle) * self.double_outer_radius
            plt.plot([0, dx], [0, dy], 'k-', linewidth=0.5)
            
            # Add segment numbers
            text_radius = self.triple_inner_radius  # Place numbers between triple and double
            text_x = np.sin(angle + np.radians(9)) * text_radius  # +9 degrees for center of segment
            text_y = np.cos(angle + np.radians(9)) * text_radius
            plt.text(text_x, text_y, str(self.segments[i]), 
                    ha='center', va='center')
        
        # Plot dart positions if provided
        if dart_positions:
            for i, (x, y) in enumerate(dart_positions):
                score = self.get_score(x, y)
                plt.plot(x, y, 'ro', markersize=10, label=f'Dart {i+1}: {score}')
        
        plt.axis('equal')
        plt.grid(True)
        plt.title('Dartboard Scoring Regions')
        plt.xlabel('X Position (mm)')
        plt.ylabel('Y Position (mm)')
        
        # Set axis limits to show full board with some padding
        limit = self.double_outer_radius * 1.1
        #plt.xlim(-limit, limit)
        #plt.ylim(-limit, limit)
        
        plt.legend()
        plt.show()
        #plt.savefig(save_path)
        #plt.close()
        #print(f"Plot saved as '{save_path}'")

    def visualize_fov(self,save_path: str = '../output/dartboard_scoring.png'):
        fig, ax = plt.subplots(figsize=(10, 10))

        # Draw scoring rings
        circles = [
            (self.double_outer_radius, 'black', 'Double Ring'),
            (self.double_inner_radius, 'white', ''),
            (self.triple_outer_radius, 'black', 'Triple Ring'),
            (self.triple_inner_radius, 'white', ''),
            (self.bull_radius, 'green', 'Bull'),
            (self.double_bull_radius, 'red', 'Double Bull')
        ]
        for r, color, label in circles:
            ax.add_patch(Circle((0, 0), r, fill=False, color=color, linewidth=2, label=label))

        # Segment lines and numbers
        for i in range(20):
            angle = np.radians(i * 18 - 9)
            x = np.sin(angle) * self.double_outer_radius
            y = np.cos(angle) * self.double_outer_radius
            ax.plot([0, x], [0, y], 'k-', linewidth=0.5)

            text_angle = np.radians(i * 18)
            text_r = self.triple_inner_radius + 10
            tx = np.sin(text_angle) * text_r
            ty = np.cos(text_angle) * text_r
            ax.text(tx, ty, str(self.segments[i]), ha='center', va='center')
  
        

        # Camera targets based on segment center angles
        target_segments = [9, 5, 1, 4]
        segment_indices = [self.segments.index(s) for s in target_segments]
        cam_distance = self.double_outer_radius +500  # mm from center
        fov_half_angle = 27.5                         # degrees (half of 55° FOV)
        fov_length = 600                              # how far the FOV lines extend
        cam_colors = ['red', 'green', 'blue', 'orange']  # One for each camera
        
        cam_positions = []
        for index in segment_indices:
            angle_rad = np.radians(index * 18)
            cam_x = cam_distance * np.sin(angle_rad)
            cam_y = cam_distance * np.cos(angle_rad)
            cam_positions.append((cam_x, cam_y))

        for i, seg_index in enumerate(segment_indices):
            color = cam_colors[i % len(cam_colors)]  
            center_angle_deg = seg_index * 18
            center_rad = np.radians(center_angle_deg)

            cam_x = cam_distance * np.sin(center_rad)
            cam_y = cam_distance * np.cos(center_rad)

            # Plot camera as triangle
            square = RegularPolygon(
                (cam_x, cam_y), numVertices=4, radius=20,
                orientation=center_rad + np.pi, color=color
            )
            ax.add_patch(square)

            # FOV edge lines
            for offset in [-fov_half_angle, fov_half_angle]:
                edge_angle = np.radians(center_angle_deg + offset)
                edge_x = cam_x - fov_length * np.sin(edge_angle)
                edge_y = cam_y - fov_length * np.cos(edge_angle)
                ax.plot([cam_x, edge_x], [cam_y, edge_y], color=color,linestyle='dotted', linewidth=1)

                # Plot camera squares and camera lines
        for cam_idx, (cam_x, cam_y) in enumerate(cam_positions):
            color = cam_colors[cam_idx % len(cam_colors)]

            # Plot all lines from this camera
            if cam_idx < len(self.cam_lines):
                for line_idx, (a, b, c) in enumerate(self.cam_lines[cam_idx]):
                    if a == 0 and b == 0:
                        continue  # Skip dummy line

                    x_vals = np.linspace(-600, 600, 600) #edit line length
                    if b != 0:
                        y_vals = (-a * x_vals - c) / b
                    else:
                        x_vals = np.full(500, -c / a)
                        y_vals = np.linspace(-300, 300, 500)

                    ax.plot(x_vals, y_vals, linestyle='--', color=color, alpha=0.4,
                            label=f'Cam {cam_idx+1} Line {line_idx+1}' if line_idx == 0 else "")
        # Final formatting
        ax.set_aspect('equal')
        ax.set_xlim(-400, 400)
        ax.set_ylim(-400, 400)
        ax.set_xlabel('X Position (mm)')
        ax.set_ylabel('Y Position (mm)')
        ax.set_title('Dartboard with Camera FOVs and Scoring Zones')

        # Clean legend
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        ax.legend(by_label.values(), by_label.keys(), loc='upper right')

        ax.grid(True)
        plt.show()

if __name__ == "__main__":
    
    #with open('dart_positions.json', 'r') as f:
    #    dart_positions = json.load(f)
        
    # Create scoring instance
    scoring = DartboardScoringVisualizer()
        
    #Example dart positions (x, y) in mm from center
    dart_positions = [
       (-42.6039,135.0568),(32.9213,-110.3708)
    ]
    
    # Get scores for each dart
    for i, pos in enumerate(dart_positions):
        score = scoring.get_score(pos[0], pos[1])
        value = scoring.get_score_value(score)
        print(f"Dart {i+1} at position {pos}: {score} ({value} points)")
        print(str(np.sqrt(pos[0]*pos[0]+pos[1]*pos[1])))

