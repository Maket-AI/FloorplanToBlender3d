from shapely.geometry import Polygon, MultiPoint
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
import math

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


def calculate_dimensions_from_points(points, scale):
    # Calculate dimensions from a list of points
    if len(points) >= 2:  # At least two points needed to define a rectangle
        multi_point = MultiPoint(points)
        bounds = multi_point.bounds
        width = (bounds[2] - bounds[0]) * scale
        height = (bounds[3] - bounds[1]) * scale
        return width, height
    else:
        # Default to zero if there aren't enough points to define a rectangle
        return 0, 0
    

def calculate_dimensions(geometry, scale):
    # print(geometry, type(geometry))
    if isinstance(geometry, Polygon):
        # Check if the polygon has enough points to form a LinearRing
        if len(geometry.exterior.coords) >= 4:
            bounds = geometry.bounds
        else:
            # Fallback if the Polygon is invalid; consider bounds as zeros
            bounds = (0, 0, 0, 0)
    elif isinstance(geometry, (list, MultiPoint)) and len(geometry) >= 2:
        # Handling a list of points or a MultiPoint by calculating the minimal bounding box
        if isinstance(geometry, list):
            geometry = MultiPoint(geometry)
        bounds = geometry.bounds
    else:
        # Fallback for other cases
        bounds = (0, 0, 0, 0)
    
    # Calculate width and height using the bounds
    width = (bounds[2] - bounds[0]) * scale
    height = (bounds[3] - bounds[1]) * scale
    # print(f"calcalue width and height {width} and {height}")
    return width, height


def process_room_data(assigned_rooms, scale):
    room_data = []
    count = 0
    # print(f"assigned_rooms {len(assigned_rooms)}")
    for index, room in enumerate(assigned_rooms):
        width, height = calculate_dimensions(room['polygon'], scale)
        room = {
            "corners": [[x * scale, y * scale] for x, y in room['polygon'].exterior.coords[:-1]],  
            "width": width,
            "height": height,
            "id": index,
            "label": room['type'] + "_" + str(index),
            "type": room['type']
        }
        room_data.append(room)
        # print(f"room_data count {count}, with {room}")
        count +=1
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


def define_scale_rate(assigned_rooms):
    total_area = 0
    room_count = 0
    for room in assigned_rooms:
        if room['type'] != 'corridor':
            area = room['polygon'].area
            total_area += area
            room_count += 1
    if room_count == 0:
        return 1
    actual_average_area = total_area / room_count
    print(f"actual_average_area {actual_average_area}")
    default_area = 180
    scale_rate_by_area =  default_area / actual_average_area
    linear_scale_rate = math.sqrt(scale_rate_by_area)
    return linear_scale_rate


def room_polygon_processing(rooms_polygons, max_base):
    processed_rooms = []
    total_area = 0
    # extremely smaller room is abandoned, and smaller room is corrdior
    for poly in rooms_polygons:
        if poly.area >= max_base / 10:  
            total_area += poly.area
            room_type = 'corridor' if poly.area < max_base / 6 else 'room'
            processed_rooms.append({'type': room_type, 'polygon': poly})
    
    # if the leagrest room take over 0.4 of floorplan, then join living and dining together
    if rooms_polygons[0].area / total_area >= 0.4:
        predefined_types = ['living_room']
    else:
        predefined_types = ['living_room', 'dining_room']
    for i, room in enumerate(processed_rooms):
        if room['type'] != 'corridor':
            if i < len(predefined_types):
                room['type'] = predefined_types[i]  
            else:
                room['type'] = 'bedroom'  
    # # if only two rooms, one is living one is bed.
    # if len(processed_rooms) == 2:
    #     processed_rooms[0]['type'] = 'living_room'  
    #     processed_rooms[1]['type'] = 'bedroom' 
    # else:
    #     # predefined_types = ['living_room', 'dining_room', 'kitchen', 'bathroom']
    #     predefined_types = ['living_room', 'dining_room']
    #     for i, room in enumerate(processed_rooms):
    #         if room['type'] != 'corridor':
    #             if i < len(predefined_types):
    #                 room['type'] = predefined_types[i]  
    #             else:
    #                 room['type'] = 'bedroom'  
    return processed_rooms



def process_room_data(assigned_rooms, scale):
    room_data = []
    for index, room in enumerate(assigned_rooms):
        # Assuming calculate_dimensions correctly calculates dimensions from the polygon and scale
        width, height = calculate_dimensions(room['polygon'], scale)
        room_label = room['type'] if room['type'] in ['living_room', 'dining_room', 'corrdior'] else 'room'
        room_data.append({
            "corners": [[x * scale, y * scale] for x, y in room['polygon'].exterior.coords[:-1]],  
            "width": width,
            "height": height,
            "id": index,
            "label": room_label + "_" + str(index),
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


def parse_json_to_visualizer(room_corners, outer_contour_corners):
    filtered_polygons = [Polygon(corners) for corners in room_corners if Polygon(corners).area > 0]
    sorted_polygons = sorted(filtered_polygons, key=lambda p: p.area, reverse=True)
    
    max_base = (sorted_polygons[0].area + sorted_polygons[1].area) / 2 if len(sorted_polygons) > 1 else sorted_polygons[0].area
    
    rooms_polygons = room_polygon_processing(sorted_polygons, max_base)
    print("finish room filter")
    scale = define_scale_rate(rooms_polygons)  
    json_structure = process_room_data(rooms_polygons, scale)
    
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
    data_for_payload = parse_json_to_visualizer(merged_rooms, outer_contour_corners)
    data_for_payload = rectangularized(data_for_payload)
    print(f"payload for visualizer:{data_for_payload}")
    lambda_response = call_visualizer(data_for_payload, lambda_client)
    # Return the same structure as the Lambda function
    return lambda_response
