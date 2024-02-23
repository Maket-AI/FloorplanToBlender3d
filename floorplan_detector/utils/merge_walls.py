import numpy as np
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection
from shapely.validation import explain_validity

# Function to create bounding boxes that are aligned with the axis
def create_bounding_boxes_for_rooms(room_contours, outer_contour):
    outer_polygon = Polygon(outer_contour)
    updated_room_contours = []

    for room in room_contours:
        room_polygon = Polygon(room)
        minx, miny, maxx, maxy = room_polygon.bounds
        bounding_box = Polygon([(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)])
        intersection_polygon = bounding_box.intersection(outer_polygon)
        if not intersection_polygon.is_empty:
            updated_room_contours.append(np.array(intersection_polygon.exterior.coords).round().astype(int))

    return updated_room_contours

# Function to dilate each room and intersect with the outer contour
def dilate_and_intersect_with_outer(room_contours, outer_contour, expansion_pixels):
    outer_polygon = Polygon(outer_contour)
    dilated_room_contours = []

    for room in room_contours:
        room_polygon = Polygon(room)
        dilated_room = room_polygon.buffer(expansion_pixels)
        intersection_polygon = dilated_room.intersection(outer_polygon)
        if not intersection_polygon.is_empty:
            dilated_room_contours.append(np.array(intersection_polygon.exterior.coords).round().astype(int))

    return dilated_room_contours


# Function to compute minimum distance between non-adjacent room polygons to estimate wall thickness
def estimate_wall_thickness(room_polygons):
    min_distance = float('inf')
    for i, room1 in enumerate(room_polygons):
        for j, room2 in enumerate(room_polygons):
            if i != j:
                distance = room1.distance(room2)
                if distance > 0:
                    min_distance = min(min_distance, distance)
    return min_distance / 2


# Function to adjust corners of the polygons to merge walls
def adjust_corners(poly1, poly2, threshold):
    min_dist, point1, point2 = None, None, None
    
    # Check each corner of poly1 against all corners of poly2
    for p1 in poly1.exterior.coords:
        for p2 in poly2.exterior.coords:
            dist = np.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
            if min_dist is None or dist < min_dist:
                min_dist = dist
                point1 = p1
                point2 = p2

    # If the closest points are within the threshold, adjust the corners
    if min_dist is not None and min_dist <= threshold:
        new_coords1 = [point2 if p == point1 else p for p in poly1.exterior.coords]
        new_coords2 = [point1 if p == point2 else p for p in poly2.exterior.coords]
        new_poly1 = Polygon(new_coords1)
        new_poly2 = Polygon(new_coords2)
        return new_poly1, new_poly2
    else:
        return poly1, poly2


# Function to merge all walls between rooms
def merge_walls(room_contours, threshold):
    rooms = [Polygon(room) for room in room_contours]
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            rooms[i], rooms[j] = adjust_corners(rooms[i], rooms[j], threshold)
    return rooms


def inflate_rooms(room_polygons, outer_polygon, wall_thickness):
    inflated_rooms = []
    outer_polygon_is_valid = outer_polygon.is_valid

    for room in room_polygons:
        # Inflate the room
        try:
            inflated_room = room.buffer(wall_thickness, cap_style=2, join_style=2)
        except ValueError as e:
            print(f"Error inflating room with wall thickness {wall_thickness}: {e}")
            # If an error occurs, use the original room
            inflated_room = room
        # Intersect with the outer contour only if it's valid and ensure it remains within the building
        if outer_polygon_is_valid:
            inflated_room = inflated_room.intersection(outer_polygon)
        inflated_rooms.append(inflated_room)

    # Now ensure that the inflated rooms do not overlap with each other
    non_overlapping_rooms = []
    for i, room in enumerate(inflated_rooms):
        # Start with the current inflated room
        current_room = room
        # Subtract the area of all other inflated rooms
        for j, other_room in enumerate(inflated_rooms):
            if i != j:
                current_room = current_room.difference(other_room)
        # Ensure the result is a polygon, and use the largest polygon if it's a MultiPolygon
        if isinstance(current_room, MultiPolygon):
            # Iterate over each polygon in the MultiPolygon to find the largest
            largest_polygon = max(current_room.geoms, key=lambda p: p.area)
            current_room = largest_polygon
        non_overlapping_rooms.append(current_room)

    return non_overlapping_rooms


def merge_wall_processing(outer_contour_corners, room_corners):
    # Convert the room corners to shapely Polygons
    room_polygons = [Polygon(room) for room in room_corners]
    outer_contour_polygon = Polygon(outer_contour_corners)
    # Estimate the wall thickness
    wall_thickness = estimate_wall_thickness(room_polygons)
    print(f"wall_thickness {wall_thickness}")

    # Inflate the rooms without them overlapping each other
    non_overlapping_room_polygons = inflate_rooms(room_polygons, outer_contour_polygon, wall_thickness)

    # # Merge walls by adjusting corners
    # threshold = 0.5  # Set a threshold for how close corners should be to considered them for merging
    # merged_rooms = merge_walls([r.exterior.coords for r in non_overlapping_room_polygons], threshold)

    valid_polygons = []
    # print(f"non_overlapping_room_polygons {non_overlapping_room_polygons}")
    # Filter out only Polygon and MultiPolygon objects
    for geom in non_overlapping_room_polygons:
        if isinstance(geom, (Polygon, MultiPolygon)):
            valid_polygons.append(geom)
        elif isinstance(geom, GeometryCollection):
            # Handle GeometryCollection, extract only Polygon and MultiPolygon parts
            valid_parts = [part for part in geom.geoms if isinstance(part, (Polygon, MultiPolygon))]
            valid_polygons.extend(valid_parts)

    # Merge walls by adjusting corners
    threshold = 0.5  # Set a threshold for how close corners should be to considered them for merging
    merged_rooms = merge_walls([r.exterior.coords for r in valid_polygons], threshold)

    return merged_rooms
