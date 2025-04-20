import math
import logging
import json
import matplotlib.pyplot as plt
import numpy as np

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def process_result_for_frontend(api_result):
    """
    Process API results to make them ready for frontend rendering.
    This includes:
    1. Detecting walls, rooms, doors, windows
    2. Processing doors/windows to align with walls
    3. Generating measurements
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
    boundary = calculate_boundary(processed_result["walls"])
    processed_result["boundary"] = boundary
    
    # Process doors and windows
    doors_and_windows = process_doors_and_windows(
        api_result.get("doors", []), 
        processed_result["walls"]
    )
    
    # Ensure doors have the correct format with all calculation done on the backend
    processed_result["doors"] = []
    for door in doors_and_windows["doors"]:
        processed_result["doors"].append({
            "position": door["points"],
            "wallId": door["wallId"],
            "wallAngle": door["wallAngle"],
            "width": door["width"],
            "thickness": door["thickness"]
        })
    
    # Ensure windows have the correct format with all calculation done on the backend
    processed_result["windows"] = []
    for window in doors_and_windows["windows"]:
        processed_result["windows"].append({
            "position": window["points"],
            "wallId": window["wallId"],
            "wallAngle": window["wallAngle"],
            "width": window["width"],
            "lineSpacing": window["lineSpacing"]
        })
    
    # Generate measurements
    processed_result["measurements"] = generate_measurements(boundary)
    
    return processed_result

def calculate_boundary(walls):
    """Calculate the boundary (min/max x,y coordinates) from walls."""
    if not walls:
        return {"minX": 0, "minY": 0, "maxX": 0, "maxY": 0, "width": 0, "height": 0}
    
    minX = float('inf')
    minY = float('inf')
    maxX = float('-inf')
    maxY = float('-inf')
    
    for wall in walls:
        points = wall["position"]
        for point in points:
            minX = min(minX, point[0])
            minY = min(minY, point[1])
            maxX = max(maxX, point[0])
            maxY = max(maxY, point[1])
    
    return {
        "minX": minX,
        "minY": minY,
        "maxX": maxX,
        "maxY": maxY,
        "width": maxX - minX,
        "height": maxY - minY
    }

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

def process_doors_and_windows(doors, walls):
    """
    Process doors and windows, classifying them and aligning them to walls.
    
    This processes all door and window calculations so that the frontend doesn't need to
    perform any additional calculations for alignment or positioning.
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
        nearest_wall = find_nearest_wall(center_point, walls)
        if not nearest_wall:
            continue
        
        # Check if this is a door or window based on aspect ratio
        if ratio > 2.5 or ratio < 0.4:
            # Likely a window
            aligned_points = align_to_wall(bbox, nearest_wall)
            intersections = [
                find_wall_intersection(aligned_points[0], nearest_wall),
                find_wall_intersection(aligned_points[1], nearest_wall)
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
            # For doors, find the actual line segment where the door intersects with the wall
            wall_p1, wall_p2 = nearest_wall["position"]
            
            # Project door bbox corners onto the wall line
            bbox_corners = [
                [bbox[0][0], bbox[0][1]],  # top-left
                [bbox[1][0], bbox[1][1]],  # top-right
                [bbox[2][0], bbox[2][1]],  # bottom-right
                [bbox[3][0], bbox[3][1]]   # bottom-left
            ]
            
            # Project all corners to the wall
            projected_points = [find_wall_intersection(corner, nearest_wall) for corner in bbox_corners]
            
            # Find the two points that are farthest apart - these will be the door endpoints
            max_distance = 0
            door_endpoints = None
            
            for i in range(len(projected_points)):
                for j in range(i+1, len(projected_points)):
                    p1 = projected_points[i]
                    p2 = projected_points[j]
                    dist = distance(p1, p2)
                    
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
                midpoint = mid_point(door_endpoints) if door_endpoints else center_point
                
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

def find_nearest_wall(point, walls):
    """Find the wall closest to a given point."""
    if not walls:
        return None
        
    nearest_wall = None
    min_dist = float('inf')
    
    for wall in walls:
        if "position" not in wall or len(wall["position"]) < 2:
            continue
            
        p1, p2 = wall["position"]
        dist = point_to_line_distance(point, p1, p2)
        
        if dist < min_dist:
            min_dist = dist
            nearest_wall = wall
    
    return nearest_wall

def point_to_line_distance(point, line_start, line_end):
    """Calculate the shortest distance from a point to a line segment."""
    A = point[0] - line_start[0]
    B = point[1] - line_start[1]
    C = line_end[0] - line_start[0]
    D = line_end[1] - line_start[1]
    
    dot = A * C + B * D
    len_sq = C * C + D * D
    param = -1
    
    if len_sq != 0:
        param = dot / len_sq
    
    if param < 0:
        xx = line_start[0]
        yy = line_start[1]
    elif param > 1:
        xx = line_end[0]
        yy = line_end[1]
    else:
        xx = line_start[0] + param * C
        yy = line_start[1] + param * D
    
    dx = point[0] - xx
    dy = point[1] - yy
    
    return math.sqrt(dx * dx + dy * dy)

def align_to_wall(bbox, wall):
    """Align a door/window to a wall by adjusting its orientation."""
    if "position" not in wall or len(wall["position"]) < 2:
        return [[bbox[0][0], bbox[0][1]], [bbox[2][0], bbox[2][1]]]
        
    p1, p2 = wall["position"]
    angle = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    
    length = math.sqrt(
        (bbox[2][0] - bbox[0][0])**2 + 
        (bbox[2][1] - bbox[0][1])**2
    )
    
    # Calculate center point of bbox
    center_x = (bbox[0][0] + bbox[2][0]) / 2
    center_y = (bbox[0][1] + bbox[2][1]) / 2
    
    # Calculate new endpoints based on wall angle
    half_length = length / 2
    start_x = center_x - half_length * math.cos(angle)
    start_y = center_y - half_length * math.sin(angle)
    end_x = center_x + half_length * math.cos(angle)
    end_y = center_y + half_length * math.sin(angle)
    
    return [[start_x, start_y], [end_x, end_y]]

def find_wall_intersection(point, wall):
    """Find the intersection point between a point and a wall."""
    if "position" not in wall or len(wall["position"]) < 2:
        return point
        
    p1, p2 = wall["position"]
    wall_angle = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    
    # Calculate perpendicular distance
    dist = point_to_line_distance(point, p1, p2)
    
    # Calculate intersection point
    intersection_x = point[0] - dist * math.cos(wall_angle + math.pi/2)
    intersection_y = point[1] - dist * math.sin(wall_angle + math.pi/2)
    
    return [intersection_x, intersection_y]

def find_potential_doors(walls):
    """Generate potential doors based on walls."""
    if not walls or len(walls) < 2:
        return []
        
    doors = []
    for i, wall1 in enumerate(walls):
        for j, wall2 in enumerate(walls[i+1:], i+1):
            # Find walls that are close to each other but not connected
            p1 = wall1["position"][0]
            p2 = wall1["position"][1]
            p3 = wall2["position"][0]
            p4 = wall2["position"][1]
            
            # Check if walls are parallel and close
            # This is a simple heuristic and can be improved
            if is_parallel(p1, p2, p3, p4) and is_close(p1, p2, p3, p4, threshold=50):
                # Create a door between these walls
                door_center = mid_point(closest_points(p1, p2, p3, p4))
                width = 40  # Typical door width
                height = 10  # Thickness
                
                # Create door bbox
                door = {
                    "bbox": [
                        [door_center[0] - width/2, door_center[1] - height/2],
                        [door_center[0] + width/2, door_center[1] - height/2],
                        [door_center[0] + width/2, door_center[1] + height/2],
                        [door_center[0] - width/2, door_center[1] + height/2]
                    ]
                }
                doors.append(door)
                
    return doors[:5]  # Limit to 5 doors for testing

def is_parallel(p1, p2, p3, p4, threshold=0.2):
    """Check if two line segments are roughly parallel."""
    vec1 = [p2[0] - p1[0], p2[1] - p1[1]]
    vec2 = [p4[0] - p3[0], p4[1] - p3[1]]
    
    len1 = (vec1[0]**2 + vec1[1]**2)**0.5
    len2 = (vec2[0]**2 + vec2[1]**2)**0.5
    
    if len1 == 0 or len2 == 0:
        return False
        
    # Normalize
    vec1 = [vec1[0]/len1, vec1[1]/len1]
    vec2 = [vec2[0]/len2, vec2[1]/len2]
    
    # Dot product should be close to 1 or -1
    dot = abs(vec1[0]*vec2[0] + vec1[1]*vec2[1])
    return abs(dot - 1.0) < threshold

def is_close(p1, p2, p3, p4, threshold=50):
    """Check if two line segments are close to each other."""
    dist1 = min(distance(p1, p3), distance(p1, p4))
    dist2 = min(distance(p2, p3), distance(p2, p4))
    return dist1 < threshold or dist2 < threshold

def distance(p1, p2):
    """Calculate Euclidean distance between two points."""
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

def closest_points(p1, p2, p3, p4):
    """Find the closest points between two line segments."""
    distances = [
        (distance(p1, p3), p1, p3),
        (distance(p1, p4), p1, p4),
        (distance(p2, p3), p2, p3),
        (distance(p2, p4), p2, p4)
    ]
    min_dist, pa, pb = min(distances, key=lambda x: x[0])
    return (pa, pb)

def mid_point(points):
    """Calculate the midpoint between two points."""
    p1, p2 = points
    return [(p1[0] + p2[0])/2, (p1[1] + p2[1])/2]

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
    plot_floorplan_elements(test_data["walls"], test_data["doors"], "Original Door/Window Positions", ax1)
    
    # Process the data
    processed_data = process_result_for_frontend(test_data)
    
    # Plot processed data
    plot_floorplan_elements(processed_data["walls"], processed_data["doors"], "Processed Door/Window Positions", ax2)
    
    plt.tight_layout()
    plt.show()

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
    processed = process_doors_and_windows(test_data.get("doors", []), test_data["walls"])
    
    # Plot processed doors
    for door in processed["doors"]:
        p1, p2 = door["points"]
        ax2.plot([p1[0], p2[0]], [p1[1], p2[1]], 'r-', linewidth=2)
        
        # Draw door swing arc
        center = p1  # Use first point as hinge
        radius = distance(p1, p2)
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
        length = distance(p1, p2)
        
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
        # Use sample data
        test_data = {
            "walls": [
                {"position": [[0, 0], [100, 0]]},
                {"position": [[100, 0], [100, 100]]},
                {"position": [[100, 100], [0, 100]]},
                {"position": [[0, 100], [0, 0]]}
            ],
            "rooms": [
                [
                    {"id": "1", "x": 0, "y": 0},
                    {"id": "2", "x": 100, "y": 0},
                    {"id": "3", "x": 100, "y": 100},
                    {"id": "4", "x": 0, "y": 100}
                ]
            ],
            "doors": [
                {
                    "points": [[40, 0], [60, 0]],
                    "width": 20,
                    "thickness": 5
                }
            ],
            "windows": [
                {
                    "points": [[20, 100], [40, 100]],
                    "width": 20,
                    "lineSpacing": 4
                }
            ]
        }
    
    # Process the data
    processed_data = process_result_for_frontend(test_data)
    
    # Plot the complete floor plan
    fig, ax = plot_complete_floorplan(processed_data)
    plt.show()

if __name__ == "__main__":
    test_floorplan_visualization() 