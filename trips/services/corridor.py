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


def find_stations_along_route(
    route_coords: List[List[float]],
    max_corridor_miles: float = 12.0,
    sample_interval: int = 15,
) -> List[dict]:
    """
    Finds fuel stations along a route corridor without calling external APIs.
    1. Computes the bounding box of the route to filter candidates in SQLite.
    2. Projects stations to their closest route point and records their mile marker.
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

    # Fast indexed bounding-box query in SQLite (runs in ~2ms)
    candidate_stations = list(
        FuelStation.objects.filter(
            latitude__range=(min_lat, max_lat),
            longitude__range=(min_lon, max_lon),
        )
    )

    if not candidate_stations:
        return []

    # Calculate cumulative mile markers along the sampled polyline
    sampled_points: List[Tuple[float, float, float]] = []  # (lat, lon, cumulative_mile)
    cumulative_mile = 0.0
    prev_pt = route_coords[0]
    sampled_points.append((prev_pt[0], prev_pt[1], 0.0))

    for i in range(1, len(route_coords)):
        curr_pt = route_coords[i]
        seg_dist = haversine_distance_miles(prev_pt[0], prev_pt[1], curr_pt[0], curr_pt[1])
        cumulative_mile += seg_dist
        prev_pt = curr_pt
        if i % sample_interval == 0 or i == len(route_coords) - 1:
            sampled_points.append((curr_pt[0], curr_pt[1], cumulative_mile))

    stations_along_route = []

    for station in candidate_stations:
        st_lat, st_lon = station.latitude, station.longitude

        # Find closest point on sampled route
        min_dist = float("inf")
        closest_mile = 0.0

        for r_lat, r_lon, r_mile in sampled_points:
            d = haversine_distance_miles(st_lat, st_lon, r_lat, r_lon)
            if d < min_dist:
                min_dist = d
                closest_mile = r_mile

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
                    "mile_along_route": round(closest_mile, 2),
                    "distance_from_route_miles": round(min_dist, 2),
                }
            )

    # Sort strictly by mile along route
    stations_along_route.sort(key=lambda s: s["mile_along_route"])
    return stations_along_route
