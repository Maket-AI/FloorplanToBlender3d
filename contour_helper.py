import numpy as np

def polygon_area(vertices):
    """
    Calculate the area of a polygon with an arbitrary number of vertices.

    Parameters:
    vertices (list): A list of tuples, where each tuple contains the x and y coordinates of a vertex.

    Returns:
    float: The area of the polygon.
    """

    # Ensure there are at least 3 vertices
    if len(vertices) < 3:
        raise ValueError("A polygon must have at least 3 vertices.")
    
    # Extract the x and y coordinates
    x = np.array([vertex[0] for vertex in vertices])
    y = np.array([vertex[1] for vertex in vertices])

    # Apply the Shoelace formula
    return 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))

# Example usage:
# Define the vertices for the shape provided in the earlier example
vertices_example = [(1183, 1123), (1183, 1146), (1195, 1146), (1196, 1147),
                    (1196, 1158), (1277, 1158), (1277, 1150), (1278, 1149), (1278, 1123)]

# Calculate the area
polygon_area(vertices_example)
