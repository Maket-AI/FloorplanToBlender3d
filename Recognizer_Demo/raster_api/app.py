from flask import Flask, request, render_template, jsonify
from flask_cors import CORS
import os
import base64
import requests
import json
from PIL import Image
import io
import numpy as np
import math
from dotenv import load_dotenv
from io import BytesIO
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Get API credentials from environment variables
API_KEY = os.environ.get("RAPIDAPI_KEY", "b7c406c722mshbd9563256cc9954p1fc084jsn50461ade5253")
API_URL = "https://floor-plan-digitalization.p.rapidapi.com/raster-to-vector-base64"

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def process_floorplan(image_data):
    """Process floor plan image using the RapidAPI."""
    # Use the URL from environment variables
    url = API_URL
    
    # Get API key from environment variable
    api_key = API_KEY
    
    headers = {
        "Content-Type": "application/json",
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "floor-plan-digitalization.p.rapidapi.com"
    }
    
    # Prepare the request payload
    payload = {
        "image": image_data
    }
    
    # Make the API request
    try:
        logger.debug(f"Sending request to {url}")
        response = requests.post(url, headers=headers, json=payload)
        logger.debug(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.debug(f"API response: {json.dumps(result, indent=2)}")
            
            # Check if the response has the expected structure
            if not isinstance(result, dict):
                logger.error(f"Unexpected response format: {result}")
                return {"error": "Unexpected response format from API"}
                
            # Ensure the response has the required fields
            if "rooms" not in result:
                logger.warning("Response does not contain 'rooms' field")
                result["rooms"] = []
            else:
                logger.debug(f"Rooms structure: {type(result['rooms'])}, count: {len(result['rooms'])}")
                
            if "walls" not in result:
                logger.warning("Response does not contain 'walls' field")
                result["walls"] = []
            else:
                logger.debug(f"Walls structure: {type(result['walls'])}, count: {len(result['walls'])}")
                
            if "doors" not in result:
                logger.warning("Response does not contain 'doors' field")
                # Create sample doors based on walls for testing if needed
                result["doors"] = []
                # Find potential door locations at wall gaps
                if len(result.get("walls", [])) > 0:
                    potential_doors = find_potential_doors(result["walls"])
                    if potential_doors:
                        result["doors"] = potential_doors
                        logger.debug(f"Generated {len(potential_doors)} potential doors")
            else:
                logger.debug(f"Doors structure: {type(result['doors'])}, count: {len(result['doors'])}")
                
            # Process the results to make them ready for frontend rendering
            return process_result_for_frontend(result)
        else:
            error_msg = f"API Error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return {"error": error_msg}
    except Exception as e:
        error_msg = f"Exception during API request: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

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
    
    # Ensure doors have the correct format
    processed_result["doors"] = []
    for door in doors_and_windows["doors"]:
        if "points" in door and len(door["points"]) >= 2:
            # Calculate the midpoint of the door
            mid_x = (door["points"][0][0] + door["points"][1][0]) / 2
            mid_y = (door["points"][0][1] + door["points"][1][1]) / 2
            processed_result["doors"].append({
                "position": [mid_x, mid_y]
            })
    
    # Ensure windows have the correct format
    processed_result["windows"] = []
    for window in doors_and_windows["windows"]:
        if "points" in window and len(window["points"]) >= 2:
            # Calculate the midpoint of the window
            mid_x = (window["points"][0][0] + window["points"][1][0]) / 2
            mid_y = (window["points"][0][1] + window["points"][1][1]) / 2
            processed_result["windows"].append({
                "position": [mid_x, mid_y]
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
            
        aligned_points = align_to_wall(bbox, nearest_wall)
        intersections = [
            find_wall_intersection(aligned_points[0], nearest_wall),
            find_wall_intersection(aligned_points[1], nearest_wall)
        ]
        
        aligned_item = {
            "points": intersections,
            "wall": nearest_wall
        }
        
        # Classify as door or window based on aspect ratio
        if ratio > 2.5 or ratio < 0.4:
            # Likely a window
            processed_windows.append(aligned_item)
        else:
            # Likely a door
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
    return ((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)**0.5

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Read and encode the image
        image_data = base64.b64encode(file.read()).decode('utf-8')
        
        # Process the floor plan
        result = process_floorplan(image_data)
        
        if 'error' in result:
            return jsonify(result), 400
            
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/floorplan-data')
def get_floorplan_data():
    # For now, return a sample data structure
    # In a real application, this would fetch from a database or session
    return jsonify({
        "walls": [],
        "doors": [],
        "windows": []
    })

if __name__ == '__main__':
    app.run(debug=True, port=5004) 