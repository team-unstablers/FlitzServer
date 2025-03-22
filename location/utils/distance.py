from haversine import haversine

from location.utils.units import Point

def measure_distance(loc1: Point, loc2: Point) -> float:
    """
    Measure the distance between two points in kilometers
    """

    return haversine(loc1, loc2)
