from shapely.geometry import Polygon
import json
import cv2
import numpy as np
import sys
import os

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


def norm_blender3d(path, save_image_path):
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
    # Save the processed image
    cv2.imwrite(save_image_path, blank_image)
    print(f"Processed image saved as {save_image_path}")
    room_corners = extract_room_corners(boxes)

    # Example: Print the corners of the first room
    if room_corners:
        print(f"there are {len(room_corners)} rooms")
        for corner in room_corners:
            print("Corner", corner)
    return outer_contour_corners, room_corners