from shapely.geometry import Polygon
import json
from call_blender3d import norm_blender3d
from utils.merge_walls import merge_wall_processing
from utils.rectangularized import rectangularized
import matplotlib.pyplot as plt
import numpy as np


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


# def prase_json_to_visualizer(room_corners):
#     scale = 0.1
#     rooms_polygons = sorted([Polygon(corners) for corners in room_corners], key=lambda p: p.area, reverse=True)

#     # Assign room types
#     room_types = ['living', 'dining', 'kitchen', 'bathroom'] + ['bedroom'] * (len(rooms_polygons) - 4)
#     assigned_rooms = [{'type': room_type, 'polygon': room} for room_type, room in zip(room_types, rooms_polygons)]
#     # Create the JSON structure
#     json_structure = process_room_data(assigned_rooms, scale)
#     return json_structure


def prase_json_to_visualizer(room_corners):
    scale = 0.1
    rooms_polygons = sorted([Polygon(corners) for corners in room_corners], key=lambda p: p.area, reverse=True)

    # Assign room types based on the new requirement
    day_rooms = ['living', 'dining', 'kitchen']
    room_types = day_rooms + ['other'] * (len(rooms_polygons) - len(day_rooms))
    
    assigned_rooms = []
    for i, room in enumerate(rooms_polygons):
        room_type = 'dayroom' if room_types[i] in day_rooms else 'nightroom'
        assigned_rooms.append({'type': room_type, 'polygon': room})

    # Create the JSON structure
    json_structure = process_room_data(assigned_rooms, scale)
    print(json_structure)
    return json_structure


def call_visualizer(invoke_payload, lambda_client):
    try:
        response = lambda_client.invoke(
            FunctionName="test-asyncPlanGenStack-VisualizePlanFunction-GbKUbaR4g7fl",
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
    # detect room contour by Blender3D API.
    outer_contour_corners, room_corners = norm_blender3d(path, save_image_path)
    print(f"outer_contour_corners{outer_contour_corners}")
    # Merge the wall gaps (output: non-rectangular, rooms not glued)
    merged_rooms = merge_wall_processing(outer_contour_corners, room_corners)
    data_for_payload = prase_json_to_visualizer(merged_rooms)
    data_for_payload = rectangularized(data_for_payload)
    lambda_response = call_visualizer(data_for_payload, lambda_client)
    # Return the same structure as the Lambda function
    return lambda_response
