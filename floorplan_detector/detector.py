"""
Small demo program of detections
If someone want to just use the same detections
"""
from shapely.geometry import Polygon
import json
import cv2
import numpy as np
import sys
import os
from merge_walls import merge_wall_processing


floorplan_lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
try:
    sys.path.insert(0, floorplan_lib_path)
    from FloorplanToBlenderLib import *  # floorplan to blender lib
except ImportError:
    from FloorplanToBlenderLib import *  # floorplan to blender lib
from subprocess import check_output


def extract_room_corners(boxes):
    """
    Extract corners from the contours of rooms.

    :param boxes: List of contours, where each contour is a list of points.
    :return: List of lists containing room corners. Each inner list contains [x, y] coordinates.
    """
    room_corners = []  # List to hold all rooms' corners

    for box in boxes:
        corners = []  # List to hold corners of the current room
        for point in box:
            x, y = point[0]  # Extract x, y coordinates
            corners.append([x, y])
        if corners[0] != corners[-1]:
            corners.append(corners[0])  # Close the loop if not closed
        room_corners.append(corners)

    return room_corners


def deserialize_nested_string(value):
    if not value:
        return value  # if the string is empty, just return it

    try:
        # Try to deserialize the value
        return json.loads(value)
    except json.JSONDecodeError:
        # If it's not a valid JSON, return the original value
        return value


def get_response_as_json(response):
    response_payload = json.loads(response["Payload"].read().decode("utf-8"))
    # print(type(response_payload))
    for k in response_payload:
        if type(response_payload[k]) == str and "first" in k:
            response_payload[k] = deserialize_nested_string(response_payload[k])
    return response_payload


def extract_contour_corners(contour):
    """
    Extract corners from a single contour.

    :param contour: A single contour.
    :return: List containing [x, y] coordinates of the contour's corners.
    """
    corners = []
    if contour is not None and len(contour) > 0:
        for point in contour:
            x, y = point[0]
            corners.append([x, y])
        if corners[0] != corners[-1]:
            corners.append(corners[0])  # Close the loop if not closed
    return corners


def calculate_dimensions(polygon, scale):
    minx, miny, maxx, maxy = polygon.bounds
    width = (maxx - minx) * scale
    height = (maxy - miny) * scale
    return width, height


# Process the room data into JSON format
def process_room_data(assigned_rooms, scale):
    room_data = []
    for index, room in enumerate(assigned_rooms):
        width, height = calculate_dimensions(room['polygon'], scale)
        room_data.append({
            "corners": [[x * scale, y * scale] for x, y in room['polygon'].exterior.coords[:-1]],  # Convert each corner to feet, exclude the duplicate closing point
            "width": width,
            "height": height,
            "id": index,
            "label": room['type'] + "_" + str(index),
            "type": room['type']
        })
    plan_data = {
        "data": {
            "userID": "local-test-izualizer",
            "source": "local-editor",
            "plans": [room_data],
            "options": {
                "save_image": True,
                "add_closet": True,
                "add_deck": True,
                "add_walkin": True
            }
        }
    }
    return plan_data


def prase_json_to_visualizer(room_corners):
    scale = 0.1
    rooms_polygons = sorted([Polygon(corners) for corners in room_corners], key=lambda p: p.area, reverse=True)

    # Assign room types
    room_types = ['living', 'dining', 'kitchen', 'bathroom'] + ['bedroom'] * (len(rooms_polygons) - 4)
    assigned_rooms = [{'type': room_type, 'polygon': room} for room_type, room in zip(room_types, rooms_polygons)]
    # Create the JSON structure
    json_structure = process_room_data(assigned_rooms, scale)
    return json_structure


def call_visualizer(invoke_payload, lambda_client):
    try:
        response = lambda_client.invoke(
            FunctionName="dev-asyncPlanGenStack-VisualizePlanFunction-bsjluq2PlvgR",
            InvocationType="RequestResponse",
            Payload=json.dumps(invoke_payload),
        )
    except Exception as e:
        print(f"Error during Lambda invocation: {e}, with payload {invoke_payload}")
        exit()

    # Parse and return the response from the Lambda function
    response_payload = json.loads(response['Payload'].read())
    response_body = json.loads(response_payload['body'])
    return response_body


def detect_floorplan_image(path, save_image_path, lambda_client):
    """
    Process the floorplan image to detect walls, floors, and rooms,
    and save the processed image to the specified path.
    """
    # Read floorplan image
    print(f"open_iamge in {path}")
    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"Image not found at path: {path}")

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Resulting image
    height, width, channels = img.shape
    blank_image = np.zeros((height, width, 3), np.uint8)  # Output image

    # Create wall image (filter out small objects from image)
    wall_img = detect.wall_filter(gray)
    wall_temp = wall_img

    # Detect walls
    boxes, img = detect.precise_boxes(wall_img, blank_image)

    # Detect outer contours (simple floor or roof solution)
    contour, img = detect.outer_contours(gray, blank_image, color=(255, 0, 0)) 
    outer_contour_corners = extract_contour_corners(contour)
    # Example: Print the corners of the outer contour
    print("Corners of the outer contour:", outer_contour_corners)

    # Invert wall image for room detection
    gray = ~wall_temp

    # Detect rooms
    rooms, colored_rooms = detect.find_rooms(gray.copy())

    gray_rooms = cv2.cvtColor(colored_rooms, cv2.COLOR_BGR2GRAY)
    boxes, blank_image = detect.precise_boxes(
        gray_rooms, blank_image, color=(255, 215, 0)
    ) 

    room_corners = extract_room_corners(boxes)

    # Example: Print the corners of the first room
    if room_corners:
        print(f"there are {len(room_corners)} rooms")
        for corner in room_corners:
            print("Corner", corner)

    merged_rooms = merge_wall_processing(outer_contour_corners, room_corners)
    # Detect details
    # doors, colored_doors = detect.find_details(gray.copy())
    # gray_details = cv2.cvtColor(colored_doors, cv2.COLOR_BGR2GRAY)
    # boxes, blank_image = detect.precise_boxes(
    #     gray_details, blank_image, color=(0, 200, 100)
    # ) #green

    # Save the processed image
    cv2.imwrite(save_image_path, blank_image)
    print(f"Processed image saved as {save_image_path}")
    payload = prase_json_to_visualizer(merged_rooms)
    lambda_response = call_visualizer(payload, lambda_client)
    # Return the same structure as the Lambda function
    return lambda_response
