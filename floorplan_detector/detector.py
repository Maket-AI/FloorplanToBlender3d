from shapely.geometry import Polygon
import json
from call_blender3d import norm_blender3d
from floorplan_detector.utils.merge_walls import merge_wall_processing
from utils.rectangularized import rectangularized
import matplotlib.pyplot as plt
import numpy as np
import boto3
import datetime
import os
from urllib.parse import urlparse

def plot_rooms(data):
    """
    Plot the rooms from the given data.

    :param data: Data format from process_room_data()
    """
    plt.figure(figsize=(10, 10))
    for room_list in data['data']['plans']:
        for room in room_list:
            corners = np.array(room["corners"])
            plt.plot(*corners.T, label=f"{room['label']} ({room['type']})")
            plt.scatter(*corners.T)
    plt.gca().set_aspect('equal', adjustable='box')
    plt.legend()
    plt.title('Rectilinear Approximation of Rooms')
    plt.xlabel('X coordinate')
    plt.ylabel('Y coordinate')
    plt.grid(True)
    plt.show()


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


def calculate_dimensions(polygon, scale):
    minx, miny, maxx, maxy = polygon.bounds
    width = (maxx - minx) * scale
    height = (maxy - miny) * scale
    return width, height


def calculate_dimensions(polygon, scale):
    # Assuming this function calculates the width and height from a scaled polygon
    bounds = polygon.bounds
    width = (bounds[2] - bounds[0]) * scale
    height = (bounds[3] - bounds[1]) * scale
    return width, height

def process_room_data(assigned_rooms, scale):
    room_data = []
    for index, room in enumerate(assigned_rooms):
        width, height = calculate_dimensions(room['polygon'], scale)
        room_data.append({
            "corners": [[x * scale, y * scale] for x, y in room['polygon'].exterior.coords[:-1]],  
            "width": width,
            "height": height,
            "id": index,
            "label": room['type'] + "_" + str(index),
            "type": room['type']
        })
    plan_data = {
        "data": {
            "userID": "local-test-visualizer",
            "source": "local-editor",
            "plans": [room_data],
            "options": {
                "save_image": True,
                "add_closet": False,
                "add_deck": False,
                "add_walkin": False
            }
        }
    }
    return plan_data

def room_polygon_processing(rooms_polygons, max_base):
    processed_rooms = []
    for poly in rooms_polygons:
        if poly.area >= max_base / 10:
            room_type = 'corridor' if poly.area < max_base / 4 else 'room'
            processed_rooms.append({'type': room_type, 'polygon': poly})
    return processed_rooms

def parse_json_to_visualizer(room_corners):
    scale = 0.1
    filtered_polygons = [Polygon(corners) for corners in room_corners if Polygon(corners).area > 0]
    sorted_polygons = sorted(filtered_polygons, key=lambda p: p.area, reverse=True)

    # Calculate the max base if there are at least two rooms, otherwise use the area of the single room
    max_base = (sorted_polygons[0].area + sorted_polygons[1].area) / 2 if len(sorted_polygons) > 1 else sorted_polygons[0].area

    # Process the polygons to determine room types and remove any that are too small
    rooms_polygons = room_polygon_processing(sorted_polygons, max_base)
    # print([poly['polygon'].area for poly in rooms_polygons])  # Debug print to check areas

    # Adjust the room_types list based on the number of processed rooms, ensuring we don't run out of predefined types
    predefined_types = ['living', 'dining', 'kitchen', 'bathroom']
    room_types = predefined_types + ['bedroom'] * (len(rooms_polygons) - len(predefined_types))
    assigned_rooms = [{'type': rtype if index < len(predefined_types) else room['type'], 'polygon': room['polygon']}
                      for index, (rtype, room) in enumerate(zip(room_types, rooms_polygons))]

    # Create the JSON structure with the processed room data
    json_structure = process_room_data(assigned_rooms, scale)
    return json_structure


def call_visualizer(invoke_payload, lambda_client):
    try:
        response = lambda_client.invoke(
            FunctionName="test-asyncPlanGenStack-VisualizePlanFunction-GbKUbaR4g7fl",
            InvocationType="RequestResponse",
            Payload=json.dumps(invoke_payload),
        )
    except Exception as e:
        print(f"Error during Visualizer Lambda invocation: {e}, with payload {invoke_payload}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': str(e)})
        }

    # Assume the invoked Lambda returns a response formatted for API Gateway
    response_payload = json.loads(response['Payload'].read())

    # Directly return this payload assuming it's formatted correctly
    return response_payload


def storage_image(image_url,room_number):
    s3_client = boto3.client('s3')
    # Parse the URL to get the bucket name and the key
    parsed_url = urlparse(image_url)
    bucket_name = parsed_url.netloc.split('.')[0]
    object_key = parsed_url.path.lstrip('/')
    
    current_date = datetime.datetime.now().strftime('%Y-%m-%d')
    file_name = os.path.basename(object_key)
    destination_key = f'storage-floorplan/{current_date}_{room_number}_{file_name}'
    
    try:
        # Copy the object within the same bucket
        copy_response = s3_client.copy_object(
            Bucket=bucket_name,
            CopySource={'Bucket': bucket_name, 'Key': object_key},
            Key=destination_key
        )
        
        # Check if the copy operation was successful
        if copy_response['ResponseMetadata']['HTTPStatusCode'] == 200:
            print(f"File copied successfully to {destination_key}")
        else:
            print("Error occurred during the copy operation.")
    
    except Exception as e:
        print(f"An error occurred: {e}")



def detect_floorplan_image(path, save_image_path, lambda_client, image_url):
    """
    Process the floorplan image to detect walls, floors, and rooms,
    and save the processed image to the specified path.
    """
    # Read floorplan image
    print(f"open_iamge in {path}")
    # detect room contour by Blender3D API.
    outer_contour_corners, room_corners = norm_blender3d(path, save_image_path)
    storage_image(image_url, len(room_corners))
    # Merge the wall gaps (output: non-rectangular, rooms not glued)
    # print(f"debug:{len(room_corners)}:{room_corners}")
    merged_rooms = merge_wall_processing(outer_contour_corners, room_corners)
    # print(f"debug:{len(merged_rooms)}:{merged_rooms}")
    data_for_payload = parse_json_to_visualizer(merged_rooms)
    data_for_payload = rectangularized(data_for_payload)
    print(f"payload for visualizer:{data_for_payload}")
    lambda_response = call_visualizer(data_for_payload, lambda_client)
    # Return the same structure as the Lambda function
    return lambda_response
