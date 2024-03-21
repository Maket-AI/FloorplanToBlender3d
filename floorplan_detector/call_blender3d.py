from shapely.geometry import Polygon
from shapely.ops import snap
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


def list_icon_files(icon_folder_path):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    icon_folder_path = os.path.join(script_dir, icon_folder_path)

    supported_formats = ['.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff']
    icon_files = [os.path.join(icon_folder_path, f) for f in os.listdir(icon_folder_path)
                  if os.path.isfile(os.path.join(icon_folder_path, f)) and os.path.splitext(f)[1].lower() in supported_formats]
    return icon_files


def remove_icons_from_grayscale_image(gray_img, icon_paths, threshold=0.8, debug=True):
    if gray_img is None:
        raise ValueError("Grayscale image is not valid.")

    # Process each icon
    for icon_path in icon_paths:
        icon = cv2.imread(icon_path, 0)
        if icon is None:
            raise ValueError(f"Icon not found at path: {icon_path}")
        cv2.imwrite("./icon.png", icon)
        # Perform template matching
        result = cv2.matchTemplate(gray_img, icon, cv2.TM_CCOEFF_NORMED)

        # If debugging, save the result image
        if debug:
            cv2.imwrite(f"./debug_template_match_result_{os.path.basename(icon_path)}.png", result * 255)

        locations = np.where(result >= threshold)

        # If debugging, print the locations
        if debug:
            print(f"Locations for {icon_path}: {locations}")

        for loc in zip(*locations[::-1]):
            top_left = loc
            bottom_right = (top_left[0] + icon.shape[1], top_left[1] + icon.shape[0])

            # If debugging, draw a red rectangle instead of white to visualize detection
            if debug:
                cv2.rectangle(gray_img, top_left, bottom_right, (0, 0, 255), 2)
            else:
                cv2.rectangle(gray_img, top_left, bottom_right, (255), -1)

    return gray_img




def merge_close_polygons(polygons, tolerance=10):
    # Snap polygons together that are close to each other
    snapped_polygons = polygons.copy()

    # Iterate over the polygons to snap them to each other
    for i in range(len(polygons)):
        for j in range(i + 1, len(polygons)):
            snapped_polygons[j] = snap(snapped_polygons[j], snapped_polygons[i], tolerance)

    # Check for any overlaps and merge the polygons if they do
    merged_polygons = []
    for poly in snapped_polygons:
        merged = False
        for i in range(len(merged_polygons)):
            if poly.intersects(merged_polygons[i]):
                # Merge the two polygons
                merged_polygons[i] = merged_polygons[i].union(poly)
                merged = True
                break
        if not merged:
            merged_polygons.append(poly)

    # Convert the merged polygons back to the original coordinate format (list of list of lists)
    merged_polygons_coords = []
    for poly in merged_polygons:
        coords = list(poly.exterior.coords)
        # Convert tuples to lists and remove the last coordinate if it's the same as the first
        coords = [list(map(int, coord)) for coord in coords[:-1]]
        merged_polygons_coords.append(coords)

    return merged_polygons_coords

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


def highlight_walls(gray_image):
    # Assuming walls are darker in the grayscale image and we want to increase their contrast
    min_val = np.min(gray_image)
    max_val = np.max(gray_image)
    
    # Increase contrast for darker areas which we assume to be walls
    contrast_increased = np.clip((gray_image - min_val) * (255 / (max_val - min_val)), 0, 255).astype(np.uint8)

    # Apply this transformation only to the pixels below a certain intensity threshold
    wall_threshold = 128  # Needs adjustment based on actual image
    mask = gray_image < wall_threshold
    gray_image[mask] = contrast_increased[mask]
    
    return gray_image


def detect_and_mask_windows_and_doors_boxes(img):
    height, width, channel = img.shape
    blank_image = np.zeros(
        (height, width, 3), np.uint8
    )  # output image same size as original

    # grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = detect.wall_filter(gray)
    gray = ~gray
    doors, colored_doors = detect.find_details(img=gray.copy(), room_closing_max_length = 50)
    def adjust_and_filter_doors(doors):
        adjusted_doors = []
        for door_mask in doors:
            # Find the bounding box of the door
            rows, cols = np.where(door_mask)
            if rows.size == 0 or cols.size == 0:  # Skip if the mask is empty
                continue
            min_row, max_row = np.min(rows), np.max(rows)
            min_col, max_col = np.min(cols), np.max(cols)
            
            # Calculate the height and width of the bounding box
            height = max_row - min_row
            width = max_col - min_col
            
            # Increase the bounding box by 10% on each side
            increase_height = int(height * 0.1)
            increase_width = int(width * 0.1)
            min_row = max(0, min_row - increase_height)
            max_row = min(door_mask.shape[0], max_row + increase_height)
            min_col = max(0, min_col - increase_width)
            max_col = min(door_mask.shape[1], max_col + increase_width)
            
            # Check the aspect ratio
            aspect_ratio = max(height, width) / max(min(height, width), 1)  # Avoid division by zero
            if aspect_ratio < 4:  # If the aspect ratio is less than 4:1, it's not considered a door
                continue
            
            # Create an adjusted mask for the door
            adjusted_mask = np.zeros_like(door_mask)
            adjusted_mask[min_row:max_row, min_col:max_col] = True
            adjusted_doors.append(adjusted_mask)
        
        return adjusted_doors
    adjusted_doors = adjust_and_filter_doors(doors)

    # Apply the adjusted door masks to the image
    for door_mask in adjusted_doors:
        img[door_mask] = (0, 0, 0)  # Black out the door areas
    cv2.imwrite("./masked_door.png", img)
    return img


def norm_blender3d(path, save_image_path):
    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"Image not found at path: {path}")
    # Replace the windows by solid wall
    img = detect_and_mask_windows_and_doors_boxes(img)
    # FLip
    # img = cv2.flip(img, 0)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Resulting image
    height, width, channels = img.shape
    blank_image = np.zeros((height, width, 3), np.uint8)  # Output image
    cv2.imwrite("./gray_before.png", gray)
    gray = highlight_walls(gray)
    cv2.imwrite("./gray_after.png", gray)

    # remove icons
    # icon_paths = list_icon_files("icons")
    # if icon_paths:
    #     gray = remove_icons_from_grayscale_image(gray, icon_paths)
    # cv2.imwrite("./gray_remove_icon.png", gray)

     # Create wall image (filter out small objects from image)
    wall_img = detect.wall_filter(gray)

    # Detect walls
    wall_temp = wall_img
    boxes, img = detect.precise_boxes(wall_img, blank_image)
    # Detect outer contours (simple floor or roof solution)
    contour, img = detect.outer_contours(gray, blank_image, color=(255, 0, 0))
    outer_contour_corners = extract_contour_corners(contour)

    # Invert wall image for room detection
    gray = ~wall_temp
    cv2.imwrite("./gray_wall_temp.png", gray)
    try:
        # Detect rooms
        rooms, colored_rooms = detect.find_rooms(gray.copy())

        gray_rooms = cv2.cvtColor(colored_rooms, cv2.COLOR_BGR2GRAY)
        cv2.imwrite("./gray_rooms.png", gray_rooms)
        boxes, blank_image = detect.precise_boxes(
            gray_rooms, blank_image, color=(255, 215, 0)
        )

        room_corners = extract_room_corners(boxes)

        # Detect smaller rooms
        s_rooms, colored_s_rooms = detect.find_details(
            gray.copy(),
            noise_removal_threshold=50,
            corners_threshold=0.01,
            room_closing_max_length=100,
            gap_in_wall_max_threshold=6000,
            gap_in_wall_min_threshold=2000,
        )
        gray_details = cv2.cvtColor(colored_s_rooms, cv2.COLOR_BGR2GRAY)
        cv2.imwrite("./gray_smaller_rooms.png", gray_details)
        s_room_boxes, blank_image = detect.precise_boxes(
            gray_details, blank_image, color=(0, 200, 100)
        )

        # Extract smaller rooms corners
        s_room_corners = extract_room_corners(s_room_boxes)

        # merge smaller rooms that are close with each other
        s_room_corners = merge_close_polygons([Polygon(coords) for coords in s_room_corners])
        
        # Append smaller rooms corners to room corners
        room_corners.extend(s_room_corners)

        cv2.imwrite("./blank_image.png", blank_image)

        # Save the processed image
        cv2.imwrite(save_image_path, blank_image)
        print(f"Processed image saved as {save_image_path}")
        # Example: Print the corners of the first room
        if room_corners:
            print(f"there are {len(s_room_corners)} smaller rooms, the corner list: {s_room_corners}")
            print(f"there are {len(room_corners)} rooms, the corner list: {room_corners}")
            # for corner in room_corners:
            #     print("Corner", corner)

    except Exception as e:
        print(f"Error occurred in find_rooms: {e}")
        # Returning a predefined 500x500 rectangle in case of an error
        predefined_corner = [(0, 0), (500, 0), (500, 500), (0, 500)]
        room_corners = [predefined_corner]
        outer_contour_corners = predefined_corner
    print("Corners of the outer contour:", outer_contour_corners)
    return outer_contour_corners, room_corners