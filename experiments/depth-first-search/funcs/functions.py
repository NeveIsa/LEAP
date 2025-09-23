def neighbor(x, y):
    """
    Returns valid neighbors for a given position (x, y) in a 5x5 grid.
    Valid neighbors are (x+1, y), (x-1, y), (x, y+1), (x, y-1) that are within the range [0, 4].
    
    Args:
        x (int): The x-coordinate (0-4)
        y (int): The y-coordinate (0-4)
        
    Returns:
        list: List of tuples representing valid neighboring coordinates
    """
    # Convert inputs to int in case they come as other types
    x, y = int(x), int(y)
    
    neighbors = []
    
    # Possible moves reordered to prioritize vertical movement: down, up, right, left
    moves = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    
    for dx, dy in moves:
        new_x = x + dx
        new_y = y + dy
        
        # Check if the new position is within the 5x5 grid bounds
        if 0 <= new_x <= 4 and 0 <= new_y <= 4:
            # Always return tuples (hashable for sets)
            neighbors.append((new_x, new_y))
    
    return neighbors


def start():
    """
    Returns the starting node for the depth-first search as provided by the instructor.
    For this experiment, we'll start at position (0, 0) - top-left corner.
    
    Returns:
        tuple: The starting position (x, y) - always a tuple for hashability
    """
    # Always return a tuple (hashable for sets)
    return (0, 0)
