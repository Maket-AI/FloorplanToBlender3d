import math
import logging
import json
import matplotlib.pyplot as plt
import numpy as np
import os
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import nearest_points
from shapely.affinity import rotate, translate

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ElementProcessor:
    """
    Main class for processing floorplan elements from API results.
    Handles the conversion of raw API data to structured frontend-ready format using Shapely.
    """
    
    @staticmethod
    def process_result_for_frontend(api_result):
        """
        Process API results to make them ready for frontend rendering.
        This includes:
        1. Detecting walls, rooms, doors, windows
        2. Processing doors/windows to align with walls
        3. Generating measurements
        4. Creating a detailed visualization JSON for verification
        """
        processed_result = {}
        
        # Copy over base fields
        processed_result["message"] = api_result.get("message", "")
        processed_result["status"] = api_result.get("status", "")
        
        # Process walls - already in correct format
        processed_result["walls"] = api_result.get("walls", [])
        
        # Process rooms - already in correct format
        processed_result["rooms"] = api_result.get("rooms", [])
        
        # Calculate boundary dimensions
        boundary = BoundaryCalculator.calculate_boundary(processed_result["walls"])
        processed_result["boundary"] = boundary
        
        # Get walls and doors from API result
        walls = processed_result["walls"]
        doors = api_result.get("doors", [])
        
        # Process doors and windows directly (similar to visualization function)
        processed_result["doors"] = []
        processed_result["windows"] = []
        processed_result["original_bboxes"] = []  # Store original bounding boxes for verification
        
        # Save detailed door/window info for debugging
        detailed_data = {
            "walls": walls,
            "original_doors": doors,
            "processed_doors": [],
            "processed_windows": []
        }
        
        for i, door in enumerate(doors):
            bbox = door.get("bbox", [])
            if bbox and len(bbox) >= 4:
                # Store original bbox for verification
                processed_result["original_bboxes"].append({
                    "points": bbox,
                    "id": i
                })
                
                # Create Shapely objects for calculations
                bbox_polygon = Polygon(bbox)
                center_point = Point(bbox_polygon.centroid)
                
                # Calculate dimensions
                width = bbox[2][0] - bbox[0][0]
                height = bbox[2][1] - bbox[0][1]
                ratio = width / height
                
                # Find nearest wall
                nearest_wall = GeometryHelper.find_nearest_wall([center_point.x, center_point.y], walls)
                
                if nearest_wall:
                    wall_p1, wall_p2 = nearest_wall["position"]
                    wall_line = LineString([wall_p1, wall_p2])
                    wall_angle = math.atan2(wall_p2[1] - wall_p1[1], wall_p2[0] - wall_p1[0])
                    
                    # Project center point onto wall
                    projected_point = GeometryHelper.find_wall_intersection([center_point.x, center_point.y], nearest_wall)
                    
                    # Determine door width based on orientation relative to wall
                    wall_direction = math.atan2(wall_p2[1] - wall_p1[1], wall_p2[0] - wall_p1[0])
                    bbox_direction = math.atan2(bbox[2][1] - bbox[0][1], bbox[2][0] - bbox[0][0])
                    angle_diff = abs(wall_direction - bbox_direction) % math.pi
                    
                    # Use width or height based on alignment with wall
                    if angle_diff < math.pi/4 or angle_diff > 3*math.pi/4:
                        door_width = width
                    else:
                        door_width = height
                    
                    # Ensure minimum door width
                    door_width = max(door_width, 30)
                    half_width = door_width / 2
                    
                    # Calculate door endpoints along the wall using wall unit vector
                    wall_vector = [wall_p2[0] - wall_p1[0], wall_p2[1] - wall_p1[1]]
                    wall_length = wall_line.length
                    wall_unit_vector = [wall_vector[0]/wall_length, wall_vector[1]/wall_length]
                    
                    door_start = [
                        projected_point[0] - half_width * wall_unit_vector[0],
                        projected_point[1] - half_width * wall_unit_vector[1]
                    ]
                    door_end = [
                        projected_point[0] + half_width * wall_unit_vector[0],
                        projected_point[1] + half_width * wall_unit_vector[1]
                    ]
                    
                    # Check if this is a door or window based on aspect ratio
                    is_door = 0.5 <= ratio <= 2.0
                    
                    if is_door:
                        # This is a door
                        processed_door = {
                            "position": [door_start, door_end],
                            "wallId": walls.index(nearest_wall),
                            "wallAngle": wall_angle,
                            "width": door_width,
                            "thickness": 6,  # Default door thickness
                            "id": i,
                            "type": "door"
                        }
                        processed_result["doors"].append(processed_door)
                        detailed_data["processed_doors"].append(processed_door)
                    else:
                        # This is a window
                        processed_window = {
                            "position": [door_start, door_end],
                            "wallId": walls.index(nearest_wall),
                            "wallAngle": wall_angle,
                            "width": door_width,
                            "lineSpacing": 4,  # Default window line spacing
                            "id": i,
                            "type": "window"
                        }
                        processed_result["windows"].append(processed_window)
                        detailed_data["processed_windows"].append(processed_window)
        
        # Generate measurements
        processed_result["measurements"] = MeasurementGenerator.generate_measurements(boundary)
        
        # Save the processed data to a JSON file for inspection
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, 'outputs', 'processed_elements.json')
        detailed_path = os.path.join(script_dir, 'outputs', 'detailed_processing.json')
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save the frontend-ready result
        with open(output_path, 'w') as f:
            json.dump(processed_result, f, indent=2)
        print(f"\nProcessed data saved to: {output_path}")
        
        # Save detailed processing data for debugging
        with open(detailed_path, 'w') as f:
            json.dump(detailed_data, f, indent=2)
        print(f"Detailed processing data saved to: {detailed_path}")
        
        return processed_result

class BoundaryCalculator:
    """Class to handle boundary calculations for the floor plan using Shapely."""
    
    @staticmethod
    def calculate_boundary(walls):
        """Calculate the boundary (min/max x,y coordinates) from walls using Shapely."""
        if not walls:
            return {"minX": 0, "minY": 0, "maxX": 0, "maxY": 0, "width": 0, "height": 0}
        
        # Create a MultiLineString from all walls
        wall_lines = []
        for wall in walls:
            if "position" in wall and len(wall["position"]) >= 2:
                p1, p2 = wall["position"]
                wall_lines.append(LineString([p1, p2]))
        
        if not wall_lines:
            return {"minX": 0, "minY": 0, "maxX": 0, "maxY": 0, "width": 0, "height": 0}
        
        # Get the bounds of all walls
        bounds = wall_lines[0].bounds
        for line in wall_lines[1:]:
            line_bounds = line.bounds
            bounds = (
                min(bounds[0], line_bounds[0]),  # minX
                min(bounds[1], line_bounds[1]),  # minY
                max(bounds[2], line_bounds[2]),  # maxX
                max(bounds[3], line_bounds[3])   # maxY
            )
        
        return {
            "minX": bounds[0],
            "minY": bounds[1],
            "maxX": bounds[2],
            "maxY": bounds[3],
            "width": bounds[2] - bounds[0],
            "height": bounds[3] - bounds[1]
        }

class MeasurementGenerator:
    """Class to handle generation of measurement data for the floor plan."""
    
    @staticmethod
    def generate_measurements(boundary):
        """Generate measurement data for the floor plan."""
        return {
            "width": {
                "value": boundary["width"],
                "unit": "px",
                "start": [boundary["minX"], boundary["maxY"] + 30],
                "end": [boundary["maxX"], boundary["maxY"] + 30]
            },
            "height": {
                "value": boundary["height"],
                "unit": "px",
                "start": [boundary["maxX"] + 30, boundary["minY"]],
                "end": [boundary["maxX"] + 30, boundary["maxY"]]
            }
        }

class DoorWindowProcessor:
    """Class to handle the processing of doors and windows."""
    
    def process_doors_and_windows(self, doors, walls):
        """
        Process doors and windows, classifying them and aligning them to walls.
        
        This processes all door and window calculations so that the frontend doesn't need to
        perform any additional calculations for alignment or positioning.
        
        Classification rules:
        1. If bbox length ratio between 0.5 and 2: classify as door and find wall intersection
        2. If bbox length ratio > 2 or < 0.5: classify as window and find wall overlap
        """
        processed_doors = []
        processed_windows = []
        
        for door in doors:
            if "bbox" not in door:
                continue
                
            bbox = door["bbox"]
            width = bbox[2][0] - bbox[0][0]
            height = bbox[2][1] - bbox[0][1]
            ratio = width / height
            
            # Get center point
            center_x = (bbox[0][0] + bbox[2][0]) / 2
            center_y = (bbox[0][1] + bbox[2][1]) / 2
            center_point = [center_x, center_y]
            
            # Find nearest wall and align to it
            nearest_wall = GeometryHelper.find_nearest_wall(center_point, walls)
            if not nearest_wall:
                continue
            
            # Check if this is a door or window based on aspect ratio
            is_door = 0.5 <= ratio <= 2.0
            
            if not is_door:
                # This is a window
                aligned_points = GeometryHelper.align_to_wall(bbox, nearest_wall)
                intersections = [
                    GeometryHelper.find_wall_intersection(aligned_points[0], nearest_wall),
                    GeometryHelper.find_wall_intersection(aligned_points[1], nearest_wall)
                ]
                
                # Get wall angle for frontend alignment
                wall_p1, wall_p2 = nearest_wall["position"]
                wall_angle = math.atan2(wall_p2[1] - wall_p1[1], wall_p2[0] - wall_p1[0])
                
                # Add fully processed window information
                aligned_item = {
                    "points": intersections,
                    "wallId": walls.index(nearest_wall),
                    "wallAngle": wall_angle,
                    "width": 30,  # Default window width
                    "lineSpacing": 4  # Spacing between window lines
                }
                processed_windows.append(aligned_item)
            else:
                # This is a door
                wall_p1, wall_p2 = nearest_wall["position"]
                
                # Project door bbox corners onto the wall
                bbox_corners = [
                    [bbox[0][0], bbox[0][1]],  # top-left
                    [bbox[1][0], bbox[1][1]],  # top-right
                    [bbox[2][0], bbox[2][1]],  # bottom-right
                    [bbox[3][0], bbox[3][1]]   # bottom-left
                ]
                
                # Project all corners to the wall
                projected_points = [GeometryHelper.find_wall_intersection(corner, nearest_wall) for corner in bbox_corners]
                
                # Find the two points that are farthest apart - these will be the door endpoints
                max_distance = 0
                door_endpoints = None
                
                for i in range(len(projected_points)):
                    for j in range(i+1, len(projected_points)):
                        p1 = projected_points[i]
                        p2 = projected_points[j]
                        dist = GeometryHelper.distance(p1, p2)
                        
                        if dist > max_distance:
                            max_distance = dist
                            door_endpoints = [p1, p2]
                
                # Calculate wall angle for frontend alignment
                wall_angle = math.atan2(wall_p2[1] - wall_p1[1], wall_p2[0] - wall_p1[0])
                
                # Make sure the door length is reasonable (not too small or large)
                door_length = max_distance
                if door_length < 10:  # If too small, create a default sized door
                    # Use a default door length of 30
                    door_length = 30
                    # Calculate the midpoint of the projected door
                    midpoint = GeometryHelper.mid_point(door_endpoints) if door_endpoints else center_point
                    
                    # Create new endpoints based on the wall direction
                    door_endpoints = [
                        [midpoint[0] - (door_length/2) * math.cos(wall_angle), 
                         midpoint[1] - (door_length/2) * math.sin(wall_angle)],
                        [midpoint[0] + (door_length/2) * math.cos(wall_angle), 
                         midpoint[1] + (door_length/2) * math.sin(wall_angle)]
                    ]
                
                # Add fully processed door information
                aligned_item = {
                    "points": door_endpoints,
                    "wallId": walls.index(nearest_wall),
                    "wallAngle": wall_angle,
                    "width": door_length,
                    "thickness": 6  # Default door thickness
                }
                processed_doors.append(aligned_item)
        
        return {
            "doors": processed_doors,
            "windows": processed_windows
        }

class GeometryHelper:
    """Utility class for geometric calculations and transformations using Shapely."""
    
    @staticmethod
    def find_nearest_wall(point, walls):
        """Find the wall closest to a given point using Shapely."""
        if not walls:
            return None
            
        point_obj = Point(point)
        nearest_wall = None
        min_dist = float('inf')
        
        for wall in walls:
            if "position" not in wall or len(wall["position"]) < 2:
                continue
                
            p1, p2 = wall["position"]
            wall_line = LineString([p1, p2])
            dist = point_obj.distance(wall_line)
            
            if dist < min_dist:
                min_dist = dist
                nearest_wall = wall
        
        return nearest_wall
    
    @staticmethod
    def point_to_line_distance(point, line_start, line_end):
        """Calculate the shortest distance from a point to a line segment using Shapely."""
        point_obj = Point(point)
        line = LineString([line_start, line_end])
        return point_obj.distance(line)
    
    @staticmethod
    def align_to_wall(bbox, wall):
        """Align a door/window to a wall by adjusting its orientation using Shapely."""
        if "position" not in wall or len(wall["position"]) < 2:
            return [[bbox[0][0], bbox[0][1]], [bbox[2][0], bbox[2][1]]]
            
        p1, p2 = wall["position"]
        wall_line = LineString([p1, p2])
        wall_angle = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        
        # Create a line from bbox corners
        bbox_line = LineString([bbox[0], bbox[2]])
        length = bbox_line.length
        
        # Calculate center point of bbox
        center = Point((bbox[0][0] + bbox[2][0]) / 2, (bbox[0][1] + bbox[2][1]) / 2)
        
        # Create a new line centered at the bbox center
        half_length = length / 2
        start_x = center.x - half_length * math.cos(wall_angle)
        start_y = center.y - half_length * math.sin(wall_angle)
        end_x = center.x + half_length * math.cos(wall_angle)
        end_y = center.y + half_length * math.sin(wall_angle)
        
        return [[start_x, start_y], [end_x, end_y]]
    
    @staticmethod
    def find_wall_intersection(point, wall):
        """Find the intersection point between a point and a wall using Shapely."""
        if "position" not in wall or len(wall["position"]) < 2:
            return point
            
        point_obj = Point(point)
        p1, p2 = wall["position"]
        wall_line = LineString([p1, p2])
        
        # Get the nearest point on the wall line
        nearest_point = nearest_points(point_obj, wall_line)[1]
        return [nearest_point.x, nearest_point.y]
    
    @staticmethod
    def distance(p1, p2):
        """Calculate Euclidean distance between two points using Shapely."""
        return Point(p1).distance(Point(p2))
    
    @staticmethod
    def mid_point(points):
        """Calculate the midpoint between two points using Shapely."""
        line = LineString(points)
        return [line.centroid.x, line.centroid.y]

class DoorDetector:
    """Class for detecting potential doors from walls using Shapely."""
    
    @staticmethod
    def find_potential_doors(walls):
        """Generate potential doors based on walls using Shapely."""
        if not walls or len(walls) < 2:
            return []
            
        doors = []
        for i, wall1 in enumerate(walls):
            for j, wall2 in enumerate(walls[i+1:], i+1):
                # Create Shapely LineString objects for the walls
                p1, p2 = wall1["position"]
                p3, p4 = wall2["position"]
                line1 = LineString([p1, p2])
                line2 = LineString([p3, p4])
                
                # Check if walls are parallel and close
                if DoorDetector.is_parallel(line1, line2) and DoorDetector.is_close(line1, line2, threshold=50):
                    # Create a door between these walls
                    door_center = nearest_points(line1, line2)[0]
                    width = 40  # Typical door width
                    height = 10  # Thickness
                    
                    # Create door bbox
                    door = {
                        "bbox": [
                            [door_center.x - width/2, door_center.y - height/2],
                            [door_center.x + width/2, door_center.y - height/2],
                            [door_center.x + width/2, door_center.y + height/2],
                            [door_center.x - width/2, door_center.y + height/2]
                        ]
                    }
                    doors.append(door)
                    
        return doors[:5]  # Limit to 5 doors for testing
    
    @staticmethod
    def is_parallel(line1, line2, threshold=0.2):
        """Check if two line segments are roughly parallel using Shapely."""
        # Get the angles of both lines
        angle1 = math.atan2(line1.coords[1][1] - line1.coords[0][1],
                           line1.coords[1][0] - line1.coords[0][0])
        angle2 = math.atan2(line2.coords[1][1] - line2.coords[0][1],
                           line2.coords[1][0] - line2.coords[0][0])
        
        # Calculate the angle difference
        angle_diff = abs(angle1 - angle2) % math.pi
        return angle_diff < threshold or abs(angle_diff - math.pi) < threshold
    
    @staticmethod
    def is_close(line1, line2, threshold=50):
        """Check if two line segments are close to each other using Shapely."""
        return line1.distance(line2) < threshold
    
    @staticmethod
    def closest_points(line1, line2):
        """Find the closest points between two line segments using Shapely."""
        return nearest_points(line1, line2)

class Visualizer:
    """Class for visualizing floor plan elements."""
    
    @staticmethod
    def plot_floorplan_elements(walls, doors, title, ax=None):
        """Helper function to plot walls, doors, and windows."""
        if ax is None:
            ax = plt.gca()
        
        # Plot walls
        for wall in walls:
            p1, p2 = wall["position"]
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 'k-', linewidth=2, label='Wall')
        
        # Plot doors/windows
        for door in doors:
            if "bbox" in door:  # Original format
                bbox = door["bbox"]
                # Plot the bounding box
                ax.plot([bbox[0][0], bbox[1][0]], [bbox[0][1], bbox[1][1]], 'r-', linewidth=2)  # Top
                ax.plot([bbox[1][0], bbox[2][0]], [bbox[1][1], bbox[2][1]], 'r-', linewidth=2)  # Right
                ax.plot([bbox[2][0], bbox[3][0]], [bbox[2][1], bbox[3][1]], 'r-', linewidth=2)  # Bottom
                ax.plot([bbox[3][0], bbox[0][0]], [bbox[3][1], bbox[0][1]], 'r-', linewidth=2)  # Left
            elif "points" in door:  # Processed format
                p1, p2 = door["points"]
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 'r-', linewidth=2)
                # Draw door arc
                center_x = (p1[0] + p2[0]) / 2
                center_y = (p1[1] + p2[1]) / 2
                angle = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
                door_width = door.get("width", 30)
                arc_radius = door_width / 2
                
                # Create arc points
                t = np.linspace(0, np.pi, 50)
                x = center_x + arc_radius * np.cos(t + angle)
                y = center_y + arc_radius * np.sin(t + angle)
                ax.plot(x, y, 'r--', linewidth=1)
        
        ax.set_title(title)
        ax.set_aspect('equal')
        ax.grid(True)
    
    @staticmethod
    def test_door_window_processing():
        """Test function to visualize doors and windows before and after processing."""
        # Load test data
        try:
            with open('process_results_from_raster.json', 'r') as f:
                test_data = json.load(f)
        except FileNotFoundError:
            logger.error("Test data file not found. Using sample data.")
            # Use sample data from the API response
            test_data = {
                "walls": [
                    {"position": [[0, 0], [100, 0]]},
                    {"position": [[100, 0], [100, 100]]},
                    {"position": [[100, 100], [0, 100]]},
                    {"position": [[0, 100], [0, 0]]}
                ],
                "doors": [
                    {
                        "bbox": [[40, -5], [60, -5], [60, 5], [40, 5]]
                    }
                ]
            }
        
        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7))
        
        # Plot original data
        Visualizer.plot_floorplan_elements(test_data["walls"], test_data["doors"], "Original Door/Window Positions", ax1)
        
        # Process the data
        processor = ElementProcessor()
        processed_data = processor.process_result_for_frontend(test_data)
        
        # Plot processed data
        Visualizer.plot_floorplan_elements(processed_data["walls"], processed_data["doors"], "Processed Door/Window Positions", ax2)
        
        plt.tight_layout()
        plt.show()
    
    @staticmethod
    def test_visualization():
        """
        Test function to visualize door and window positions in a floor plan.
        Creates two subplots: original positions and processed positions.
        """
        # Sample test data
        sample_data = {
            "walls": [
                {"position": [[0, 0], [100, 0]]},
                {"position": [[100, 0], [100, 100]]},
                {"position": [[100, 100], [0, 100]]},
                {"position": [[0, 100], [0, 0]]}
            ],
            "doors": [
                {"bbox": [[20, -5], [40, -5], [40, 5], [20, 5]]},
                {"bbox": [[95, 20], [105, 20], [105, 40], [95, 40]]}
            ]
        }

        # Try to load test data from file, use sample data if file not found
        try:
            with open('process_results_from_raster.json', 'r') as f:
                test_data = json.load(f)
        except FileNotFoundError:
            test_data = sample_data

        # Create figure with two subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 7))
        
        # Plot original positions
        ax1.set_title('Original Positions')
        # Plot walls
        for wall in test_data["walls"]:
            p1, p2 = wall["position"]
            ax1.plot([p1[0], p2[0]], [p1[1], p2[1]], 'k-', linewidth=2)
        
        # Plot original door/window positions
        for door in test_data.get("doors", []):
            bbox = door["bbox"]
            xs = [p[0] for p in bbox + [bbox[0]]]  # Add first point to close the box
            ys = [p[1] for p in bbox + [bbox[0]]]
            ax1.plot(xs, ys, 'r-', linewidth=1)

        # Process and plot aligned positions
        ax2.set_title('Processed Positions')
        # Plot walls again
        for wall in test_data["walls"]:
            p1, p2 = wall["position"]
            ax2.plot([p1[0], p2[0]], [p1[1], p2[1]], 'k-', linewidth=2)
        
        # Process and plot aligned doors/windows
        door_window_processor = DoorWindowProcessor()
        processed = door_window_processor.process_doors_and_windows(test_data.get("doors", []), test_data["walls"])
        
        # Plot processed doors
        for door in processed["doors"]:
            p1, p2 = door["points"]
            ax2.plot([p1[0], p2[0]], [p1[1], p2[1]], 'r-', linewidth=2)
            
            # Draw door swing arc
            center = p1  # Use first point as hinge
            radius = GeometryHelper.distance(p1, p2)
            angle = door["wallAngle"]
            arc = plt.matplotlib.patches.Arc(
                center, radius*2, radius*2,
                angle=math.degrees(angle), 
                theta1=0, theta2=90,
                color='r', linestyle='--'
            )
            ax2.add_patch(arc)
        
        # Plot processed windows
        for window in processed["windows"]:
            p1, p2 = window["points"]
            ax2.plot([p1[0], p2[0]], [p1[1], p2[1]], 'r-', linewidth=2)
            
            # Add parallel lines for window representation
            spacing = window["lineSpacing"]
            angle = window["wallAngle"]
            length = GeometryHelper.distance(p1, p2)
            
            # Draw parallel lines
            for offset in [-spacing, spacing]:
                dx = -offset * math.sin(angle)
                dy = offset * math.cos(angle)
                ax2.plot(
                    [p1[0] + dx, p2[0] + dx],
                    [p1[1] + dy, p2[1] + dy],
                    'r-', linewidth=1
                )

        # Set equal aspect ratio and add grid for both plots
        ax1.set_aspect('equal')
        ax2.set_aspect('equal')
        ax1.grid(True)
        ax2.grid(True)
        
        plt.tight_layout()
        plt.show()

class FloorplanVisualizer:
    """Class for visualizing a complete floor plan with all elements."""
    
    @staticmethod
    def plot_complete_floorplan(data, title="Floor Plan Visualization"):
        """
        Plot a complete floor plan with all elements (walls, rooms, doors, windows).
        
        Args:
            data (dict): The processed floor plan data containing walls, rooms, doors, and windows
            title (str): Title for the plot
        """
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Plot rooms with different colors
        if "rooms" in data and data["rooms"]:
            for i, room in enumerate(data["rooms"]):
                if len(room) >= 3:  # Need at least 3 points for a room
                    # Extract x and y coordinates
                    x_coords = [point["x"] for point in room]
                    y_coords = [point["y"] for point in room]
                    
                    # Close the polygon by adding the first point at the end
                    x_coords.append(x_coords[0])
                    y_coords.append(y_coords[0])
                    
                    # Plot room with semi-transparent fill
                    color = plt.cm.Set3(i % 12)  # Use a color map for different rooms
                    ax.fill(x_coords, y_coords, alpha=0.3, color=color)
                    ax.plot(x_coords, y_coords, color=color, linewidth=1)
                    
                    # Add room label
                    center_x = sum(x_coords[:-1]) / len(x_coords[:-1])
                    center_y = sum(y_coords[:-1]) / len(y_coords[:-1])
                    ax.text(center_x, center_y, f'Room {i+1}', 
                           ha='center', va='center', fontsize=8)
        
        # Plot walls
        if "walls" in data and data["walls"]:
            for wall in data["walls"]:
                p1, p2 = wall["position"]
                ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 'k-', linewidth=2)
        
        # Plot doors
        if "doors" in data and data["doors"]:
            for door in data["doors"]:
                if "points" in door:
                    p1, p2 = door["points"]
                    # Draw door line
                    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 'b-', linewidth=2)
                    
                    # Draw door arc
                    center_x = (p1[0] + p2[0]) / 2
                    center_y = (p1[1] + p2[1]) / 2
                    angle = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
                    door_width = door.get("width", 30)
                    arc_radius = door_width / 2
                    
                    # Create arc points
                    t = np.linspace(0, np.pi, 50)
                    x = center_x + arc_radius * np.cos(t + angle)
                    y = center_y + arc_radius * np.sin(t + angle)
                    ax.plot(x, y, 'b--', linewidth=1)
        
        # Plot windows
        if "windows" in data and data["windows"]:
            for window in data["windows"]:
                if "points" in window:
                    p1, p2 = window["points"]
                    # Draw window frame
                    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], 'g-', linewidth=2)
                    
                    # Draw window lines
                    window_width = window.get("width", 30)
                    line_spacing = window.get("lineSpacing", 4)
                    angle = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
                    
                    # Calculate perpendicular offset
                    dx = -line_spacing * math.sin(angle)
                    dy = line_spacing * math.cos(angle)
                    
                    # Draw parallel lines
                    ax.plot([p1[0] + dx, p2[0] + dx], 
                           [p1[1] + dy, p2[1] + dy], 'g-', linewidth=1)
                    ax.plot([p1[0] - dx, p2[0] - dx], 
                           [p1[1] - dy, p2[1] - dy], 'g-', linewidth=1)
        
        # Add measurements if available
        if "measurements" in data:
            measurements = data["measurements"]
            for key, measurement in measurements.items():
                start = measurement["start"]
                end = measurement["end"]
                value = measurement["value"]
                unit = measurement["unit"]
                
                # Draw measurement line
                ax.plot([start[0], end[0]], [start[1], end[1]], 'k--', linewidth=1)
                
                # Add measurement text
                mid_x = (start[0] + end[0]) / 2
                mid_y = (start[1] + end[1]) / 2
                ax.text(mid_x, mid_y, f'{value:.0f}{unit}', 
                       ha='center', va='center', fontsize=8)
        
        # Set plot properties
        ax.set_title(title)
        ax.set_aspect('equal')
        ax.grid(True)
        
        # Add legend
        legend_elements = [
            plt.Line2D([0], [0], color='k', label='Walls'),
            plt.Line2D([0], [0], color='b', label='Doors'),
            plt.Line2D([0], [0], color='g', label='Windows')
        ]
        ax.legend(handles=legend_elements, loc='upper right')
        
        plt.tight_layout()
        return fig, ax
    
    @staticmethod
    def test_floorplan_visualization():
        """
        Test function to visualize a complete floor plan with all elements.
        """
        # Try to load test data from file
        try:
            with open('outputs/example_simple_result.json', 'r') as f:
                test_data = json.load(f)
        except FileNotFoundError:
            logger.error("Test data file not found. Using sample data.")
            return
        
        # Process the data
        processor = ElementProcessor()
        processed_data = processor.process_result_for_frontend(test_data)
        
        # Plot the complete floor plan
        fig, ax = FloorplanVisualizer.plot_complete_floorplan(processed_data)
        plt.show()
    
    @staticmethod
    def test_door_window_processing_with_visualization():
        """
        Test function to visualize metadata (bounding boxes) from the API response.
        Uses the example_simple_result.json file to display both raw bounding boxes and processed doors.
        """
        # Load example data from file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        example_file = os.path.join(script_dir, 'outputs', 'example_simple_result.json')
        try:
            with open(example_file, 'r') as f:
                example_data = json.load(f)
        except FileNotFoundError:
            print(f"Error: {example_file} not found")
            return

        # Get walls and doors from example data
        walls = example_data.get("walls", [])
        doors = example_data.get("doors", [])
        
        # Create visualization with higher resolution
        plt.figure(figsize=(20, 20))
        
        # Plot walls with thicker lines
        for wall in walls:
            p1, p2 = wall["position"]
            plt.plot([p1[0], p2[0]], [p1[1], p2[1]], 'k-', linewidth=3, label='Wall' if wall == walls[0] else "")
        
        # Plot doors and their original bboxes
        for i, door in enumerate(doors):
            bbox = door.get("bbox", [])
            if bbox and len(bbox) >= 4:
                # Plot original bbox with dashed lines
                x = [p[0] for p in bbox + [bbox[0]]]  # Add first point to close the box
                y = [p[1] for p in bbox + [bbox[0]]]
                plt.plot(x, y, 'g--', linewidth=1, label='Original Bbox' if i == 0 else "")
                
                # Calculate center and dimensions
                center_x = (bbox[0][0] + bbox[2][0]) / 2
                center_y = (bbox[0][1] + bbox[2][1]) / 2
                width = bbox[2][0] - bbox[0][0]
                height = bbox[2][1] - bbox[0][1]
                ratio = width / height
                
                # Find nearest wall
                center_point = [center_x, center_y]
                nearest_wall = GeometryHelper.find_nearest_wall(center_point, walls)
                
                if nearest_wall:
                    wall_p1, wall_p2 = nearest_wall["position"]
                    wall_vector = [wall_p2[0] - wall_p1[0], wall_p2[1] - wall_p1[1]]
                    wall_length = math.sqrt(wall_vector[0]**2 + wall_vector[1]**2)
                    wall_unit_vector = [wall_vector[0]/wall_length, wall_vector[1]/wall_length]
                    wall_angle = math.atan2(wall_vector[1], wall_vector[0])
                    
                    # Project center point onto wall
                    projected_point = GeometryHelper.find_wall_intersection(center_point, nearest_wall)
                    
                    # Determine door width based on orientation relative to wall
                    wall_direction = math.atan2(wall_p2[1] - wall_p1[1], wall_p2[0] - wall_p1[0])
                    bbox_direction = math.atan2(bbox[2][1] - bbox[0][1], bbox[2][0] - bbox[0][0])
                    angle_diff = abs(wall_direction - bbox_direction) % math.pi
                    
                    # Use width or height based on alignment with wall
                    if angle_diff < math.pi/4 or angle_diff > 3*math.pi/4:
                        door_width = width
                    else:
                        door_width = height
                    
                    # Ensure minimum door width
                    door_width = max(door_width, 30)
                    half_width = door_width / 2
                    
                    # Calculate door endpoints along the wall using wall unit vector
                    door_start = [
                        projected_point[0] - half_width * wall_unit_vector[0],
                        projected_point[1] - half_width * wall_unit_vector[1]
                    ]
                    door_end = [
                        projected_point[0] + half_width * wall_unit_vector[0],
                        projected_point[1] + half_width * wall_unit_vector[1]
                    ]
                    
                    # Draw door as a simple line
                    plt.plot([door_start[0], door_end[0]], [door_start[1], door_end[1]], 
                            'r-', linewidth=2, label='Door Line' if i == 0 else "")
                    
                    # Add door ID at the projected center point
                    plt.text(projected_point[0], projected_point[1], f'D{i}', color='black', 
                            ha='center', va='center', fontweight='bold', fontsize=12)
                    
                    # Print dimensions for debugging
                    print(f"\nDoor {i} dimensions:")
                    print(f"Width: {door_width:.2f} pixels")
                    print(f"Wall angle: {math.degrees(wall_angle):.2f} degrees")
                    print(f"Door orientation relative to wall: {math.degrees(angle_diff):.2f} degrees")
                
                # Draw original bbox with transparency for reference
                if not (0.5 <= ratio <= 2.0):  # This is likely a window
                    x1, y1 = bbox[0]
                    x2, y2 = bbox[2]
                    plt.fill([x1, x2, x2, x1, x1], [y1, y1, y2, y2, y1], 
                            color='blue', alpha=0.3, label='Window' if i == 0 else "")
        
        plt.title('Floor Plan Visualization with Original Bounding Boxes', fontsize=14)
        plt.legend(fontsize=12)
        plt.grid(True)
        plt.axis('equal')
        
        # Save the plot with high resolution
        output_path = os.path.join(script_dir, 'outputs', 'metadata_visualization.png')
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()  # Close the figure to free memory
        print(f"\nPlot saved as: {output_path}")

# Add the main execution code
if __name__ == "__main__":
    FloorplanVisualizer.test_door_window_processing_with_visualization() 