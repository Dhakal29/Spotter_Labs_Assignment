import math
from typing import List, Tuple
from trips.models import FuelStation

EARTH_RADIUS_MILES = 3958.8


def haversine_distance_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two geographic coordinates in miles."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_MILES * c


def point_to_segment_distance_and_mile(
    p_lat: float, p_lon: float,
    a_lat: float, a_lon: float, a_mile: float,
    b_lat: float, b_lon: float, b_mile: float,
) -> Tuple[float, float]:
    """
    Computes perpendicular distance from point P to line segment AB,
    and returns (distance_in_miles, projected_mile_along_route).
    Uses equirectangular planar projection locally on segment scale for speed and precision.
    """
    mean_lat_rad = math.radians((a_lat + b_lat) / 2.0)
    cos_lat = math.cos(mean_lat_rad)

    # Convert coordinates to local Cartesian miles relative to A
    # 1 deg lat ~= 69.0 miles; 1 deg lon ~= 69.0 * cos(lat) miles
    dx = (b_lon - a_lon) * 69.0 * cos_lat
    dy = (b_lat - a_lat) * 69.0

    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0.0:
        dist = haversine_distance_miles(p_lat, p_lon, a_lat, a_lon)
        return dist, a_mile

    px = (p_lon - a_lon) * 69.0 * cos_lat
    py = (p_lat - a_lat) * 69.0

    # Project P onto AB vector: t = (P . AB) / |AB|^2
    t = max(0.0, min(1.0, (px * dx + py * dy) / seg_len_sq))

    # Closest point coordinates in local Cartesian
    proj_x = t * dx
    proj_y = t * dy

    dist_x = px - proj_x
    dist_y = py - proj_y
    dist_miles = math.sqrt(dist_x * dist_x + dist_y * dist_y)

    projected_mile = a_mile + t * (b_mile - a_mile)
    return dist_miles, projected_mile


def find_stations_along_route(
    route_coords: List[List[float]],
    max_corridor_miles: float = 12.0,
    sample_interval: int = 8,
) -> List[dict]:
    """
    Finds fuel stations along a route corridor without calling external APIs.
    1. Computes the bounding box of the route to filter candidates in SQLite.
    2. Projects stations to the closest route line segments and records their exact mile marker.
    """
    if not route_coords:
        return []

    lats = [pt[0] for pt in route_coords]
    lons = [pt[1] for pt in route_coords]

    # Convert corridor distance to approximate degree delta
    lat_delta = max_corridor_miles / 69.0
    lon_delta = max_corridor_miles / 53.0

    min_lat, max_lat = min(lats) - lat_delta, max(lats) + lat_delta
    min_lon, max_lon = min(lons) - lon_delta, max(lons) + lon_delta

    # Fast indexed bounding-box query in SQLite
    candidate_stations = list(
        FuelStation.objects.filter(
            latitude__range=(min_lat, max_lat),
            longitude__range=(min_lon, max_lon),
        )
    )

    if not candidate_stations:
        return []

    # Calculate cumulative mile markers along the polyline segments
    sampled_segments: List[Tuple[float, float, float, float, float, float]] = []
    # (a_lat, a_lon, a_mile, b_lat, b_lon, b_mile)

    cumulative_mile = 0.0
    prev_pt = route_coords[0]
    prev_mile = 0.0

    for i in range(1, len(route_coords)):
        curr_pt = route_coords[i]
        seg_dist = haversine_distance_miles(prev_pt[0], prev_pt[1], curr_pt[0], curr_pt[1])
        cumulative_mile += seg_dist

        if i % sample_interval == 0 or i == len(route_coords) - 1:
            sampled_segments.append(
                (prev_pt[0], prev_pt[1], prev_mile, curr_pt[0], curr_pt[1], cumulative_mile)
            )
            prev_pt = curr_pt
            prev_mile = cumulative_mile

    stations_along_route = []

    for station in candidate_stations:
        st_lat, st_lon = station.latitude, station.longitude

        min_dist = float("inf")
        best_mile = 0.0

        for a_lat, a_lon, a_mile, b_lat, b_lon, b_mile in sampled_segments:
            dist, proj_mile = point_to_segment_distance_and_mile(
                st_lat, st_lon,
                a_lat, a_lon, a_mile,
                b_lat, b_lon, b_mile,
            )
            if dist < min_dist:
                min_dist = dist
                best_mile = proj_mile

        if min_dist <= max_corridor_miles:
            stations_along_route.append(
                {
                    "id": station.id,
                    "opis_id": station.opis_id,
                    "name": station.name,
                    "address": station.address,
                    "city": station.city,
                    "state": station.state,
                    "price": float(station.price),
                    "latitude": station.latitude,
                    "longitude": station.longitude,
                    "mile_along_route": round(best_mile, 2),
                    "distance_from_route_miles": round(min_dist, 2),
                }
            )

    # Sort strictly by mile along route
    stations_along_route.sort(key=lambda s: s["mile_along_route"])
    return stations_along_route
