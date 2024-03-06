"""
Small demo program of detections
If someone want to just use the same detections
"""

import cv2
import numpy as np
import sys
import os
floorplan_lib_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
try:
    sys.path.insert(0, floorplan_lib_path)
    from FloorplanToBlenderLib import *  # floorplan to blender lib
except ImportError:
    from FloorplanToBlenderLib import *  # floorplan to blender lib
from subprocess import check_output
# from FloorplanToBlenderLib import detect  # Assuming this import path is correct


def detect_floorplan_image(path, save_image_path):
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

    # Invert wall image for room detection
    gray = ~wall_temp

    # Detect rooms
    rooms, colored_rooms = detect.find_rooms(gray.copy())
    gray_rooms = cv2.cvtColor(colored_rooms, cv2.COLOR_BGR2GRAY)
    boxes, blank_image = detect.precise_boxes(
        gray_rooms, blank_image, color=(0, 100, 200)
    )

    # Detect details
    doors, colored_doors = detect.find_details(gray.copy())
    gray_details = cv2.cvtColor(colored_doors, cv2.COLOR_BGR2GRAY)
    boxes, blank_image = detect.precise_boxes(
        gray_details, blank_image, color=(0, 200, 100)
    )

    # Save the processed image
    cv2.imwrite(save_image_path, blank_image)
    print(f"Processed image saved as {save_image_path}")


# Set the paths

image_names = ["test (1).jpg", "test (1).png", "test (2).jpg", "test (2).png", "test (3).jpg"]
image_names = ["floorplan_google2.jpg"]
for image_name in image_names:
    input_image_path = os.path.abspath(os.path.join(os.path.dirname(__file__), image_name))
    save_image_path = os.path.abspath(os.path.join(os.path.dirname(__file__), f"detected_{image_name}"))
    # Call the processing function
    detect_floorplan_image(input_image_path, save_image_path)
