from shapely.geometry import Polygon
from itertools import combinations
import numpy as np
from shapely.geometry import Polygon, box, MultiPolygon
import copy


def transform_rectilinear(json_structure):
    room_data = json_structure['data']['plans'][0]

    # Converting each room to a rectilinear shape
    rectilinear_rooms = []
    for room in room_data:
        room_polygon = Polygon(room["corners"])
        rectilinear_polygon = room_polygon.minimum_rotated_rectangle
        rectilinear_corners = list(rectilinear_polygon.exterior.coords)
        rectilinear_rooms.append({
            "id": room["id"],
            "label": room["label"],
            "type": room["type"],
            "width": room["width"],
            "height": room["height"],
            "corners": rectilinear_corners
        })

    def resolve_overlap(poly1, poly2):
        # Check and handle MultiPolygon for poly1
        if isinstance(poly1, MultiPolygon):
            poly1 = max(poly1.geoms, key=lambda p: p.area)

        # Check and handle MultiPolygon for poly2
        if isinstance(poly2, MultiPolygon):
            poly2 = max(poly2.geoms, key=lambda p: p.area)

        if poly1.contains(poly2):
            return poly1.difference(poly2), poly2
        elif poly1.intersects(poly2):
            if poly1.area > poly2.area:
                return poly1.difference(poly2), poly2
            else:
                return poly1, poly2.difference(poly1)
        else:
            return poly1, poly2

    # Function to resolve the overlaps and return the updated list of polygons
    def resolve_overlaps(rooms):
        polygons = [Polygon(room['corners']) for room in rooms]
        updated_polygons = polygons.copy()

        for room1, room2 in combinations(rooms, 2):
            poly1 = updated_polygons[room1['id']]
            poly2 = updated_polygons[room2['id']]
            if poly1 and poly2:
                new_poly1, new_poly2 = resolve_overlap(poly1, poly2)
                updated_polygons[room1['id']] = new_poly1
                updated_polygons[room2['id']] = new_poly2

        updated_polygons = [poly for poly in updated_polygons if poly is not None]
        return updated_polygons

    # Resolve the overlaps
    resolved_polygons = resolve_overlaps(rectilinear_rooms)
    # print(f"resolved_polygon_type: {type(resolved_polygons)}")
    # Constructing the transformed data
    transformed_data = json_structure.copy()
    for i, poly in enumerate(resolved_polygons):
        # Convert each tuple in the polygon's exterior coordinates to a list
        transformed_data['data']['plans'][0][i]['corners'] = [list(corner) for corner in list(poly.exterior.coords)]

    return transformed_data


def largest_inscribed_rectangle_in_multipolygon(multi_polygon):
    """
    Find the largest inscribed rectangle within a given MultiPolygon.

    :param multi_polygon: A shapely MultiPolygon object.
    :return: The largest inscribed shapely Polygon (rectangle) and its area.
    """
    max_area = 0
    best_rectangle = None

    # Iterate over each polygon in the MultiPolygon
    for polygon in multi_polygon.geoms:
        rect, area = largest_inscribed_rectangle(polygon)
        if area > max_area:
            max_area = area
            best_rectangle = rect

    return best_rectangle, max_area


def largest_inscribed_rectangle(polygon):
    """
    Find the largest inscribed rectangle within a given polygon. Not consider the polygon with the hole

    :param polygon: A shapely Polygon object.
    :return: The largest inscribed shapely Polygon (rectangle) and its area.
    """

    # Initialize variables
    max_area = 0
    best_rectangle = None

    # Generate candidate points (discretizing the boundary)
    boundary_points = np.array(polygon.exterior.coords[:-1])  # exclude duplicate first/last point

    # Iterate over all pairs of points to consider them as potential rectangle corners
    for i in range(len(boundary_points)):
        for j in range(len(boundary_points)):
            p1 = boundary_points[i]
            p2 = boundary_points[j]

            # Check if a rectangle can be formed (non-degenerate case)
            if p1[0] != p2[0] and p1[1] != p2[1]:
                # Construct rectangle points
                rect_points = [(p1[0], p1[1]), (p2[0], p1[1]), (p2[0], p2[1]), (p1[0], p2[1])]

                # Create a rectangle polygon
                rect = Polygon(rect_points)

                # Check if the rectangle is within the original polygon
                if polygon.contains(rect):
                    area = rect.area
                    if area > max_area:
                        max_area = area
                        best_rectangle = rect

    return best_rectangle, max_area


def is_almost_equal_area(polygon1, polygon2, tolerance_percent=1):
    """
    Check if two polygons have almost equal area within a certain percentage tolerance.
    """
    tolerance = tolerance_percent / 100.0 * polygon1.area
    return abs(polygon1.area - polygon2.area) < tolerance


def is_rectangular(corners):
    """
    Check if a polygon defined by corners is a rectangle using Shapely's library.
    """
    polygon = Polygon(corners)
    if not polygon.is_valid or polygon.is_empty:
        return False

    min_rotated_rect = polygon.minimum_rotated_rectangle

    # Check if the area difference is less than 1%
    return is_almost_equal_area(polygon, min_rotated_rect, tolerance_percent=1)


def split_to_rectangulars(input_data):
    """
    Split non-rectangular rooms into the largest possible rectangles.
    """
    plans = input_data['data']['plans']
    new_plans = []
    corridor_id = 0  # Starting ID for corridors

    for room_list in plans:
        for room in room_list:
            corners = room['corners']
            polygon = Polygon(corners)
            area = polygon.area

            if is_rectangular(corners):
                new_plans.append(room)
            else:
                remaining_polygon = polygon
                while True:
                    if isinstance(remaining_polygon, MultiPolygon):
                        largest_rect, largest_area = largest_inscribed_rectangle_in_multipolygon(remaining_polygon)
                    else:
                        largest_rect, largest_area = largest_inscribed_rectangle(remaining_polygon)

                    # Break if no rectangle is found or it's too small
                    if largest_rect is None or largest_area < 0.1 * area:
                        break
                    min_rotated_rect = largest_rect.minimum_rotated_rectangle
                    # print(min_rotated_rect, list(min_rotated_rect.exterior.coords))
                    # Add the largest rectangle as a new 'corridor'
                    new_plans.append({
                        'corners': [list(coord) for coord in min_rotated_rect.exterior.coords],
                        'width': min_rotated_rect.bounds[2] - min_rotated_rect.bounds[0],
                        'height': min_rotated_rect.bounds[3] - min_rotated_rect.bounds[1],
                        'id': corridor_id,
                        'label': f'corridor_{corridor_id}',
                        'type': 'corridor'
                    })
                    corridor_id += 1

                    # Update the remaining polygon by subtracting the found rectangle
                    remaining_polygon = remaining_polygon.difference(largest_rect)

    input_data['data']['plans'] = [new_plans]
    return input_data


def check_if_rectilinear(polygon, label):
    centroid = polygon.centroid
    edges = list(zip(polygon.exterior.coords[:-1], polygon.exterior.coords[1:]))

    def classify_edge(edge):
        (x1, y1), (x2, y2) = edge
        if x1 == x2:  # Vertical edge
            return "r" if x1 > centroid.x else "l"
        elif y1 == y2:  # Horizontal edge
            return "u" if y1 > centroid.y else "d"
        else:
            # Non-rectilinear, return minimum rotated rectangle
            print(f"Non-rectilinear polygon adjusted for room: {label}, {polygon}")
            return polygon.minimum_rotated_rectangle

    for edge in edges:
        result = classify_edge(edge)
        if isinstance(result, Polygon):
            return result  # Non-rectilinear case

    return polygon  # Rectilinear case


def align_rooms_to_grid(input_data, grid_unit=2):
    """
    Snap the coordinates of rectangles and polygons to a specified grid.

    Parameters:
    - rooms: List of dictionaries representing rectangles or polygons.
                  Each dictionary for rectangles has keys like 'x', 'y', 'width', 'height'.
                  Each dictionary for polygons has a key 'polygon' with a Shapely Polygon object.
    - grid_unit: The unit size of the grid to snap to. Default is 0.5.

    Returns:
    - List of dictionaries with snapped attributes.
    """

    def snap_to_grid(value, unit):
        """Snap a single value to the nearest grid point."""
        return round(value / unit) * unit

    def snap_polygon(polygon, unit):
        """Snap a polygon's points to the grid."""
        snapped_points = [
            (snap_to_grid(x, unit), snap_to_grid(y, unit))
            for x, y in polygon.exterior.coords
        ]
        return Polygon(snapped_points)

    plans = input_data['data']['plans']
    for plan in plans:
        for shape in plan:
            if "corners" in shape:
                shape_poly = Polygon(shape["corners"])
                snapped_poly = snap_polygon(shape_poly, grid_unit)
                snapped_poly = check_if_rectilinear(snapped_poly, shape['type'])
                shape['corners'] = [list(coord) for coord in snapped_poly.exterior.coords]
                shape['width'] = snapped_poly.bounds[2] - snapped_poly.bounds[0]
                shape['height'] = snapped_poly.bounds[3] - snapped_poly.bounds[1]

    return input_data


def rectangularized(input_data):
    # approximate rectangular with overlapped; then remove overlap, shape may not be rectangulars.
    data_with_polygon = transform_rectilinear(input_data)
    # break into rectangulars rooms from a non-rectangular polygon room
    data_transformed_copy = copy.deepcopy(data_with_polygon)
    data_transformed_rect = split_to_rectangulars(data_transformed_copy)
    # merge small gaps by grid
    data_transformed_rect = align_rooms_to_grid(data_transformed_rect)
    # check rectilinear
    return data_transformed_rect
