import os
import requests

OSRM_DEFAULT_URL = "https://router.project-osrm.org"
HEADERS = {"User-Agent": "SpotterLabsFuelOptimizer/1.0"}


def get_driving_route(start_lat: float, start_lon: float, finish_lat: float, finish_lon: float) -> dict:
    """
    Fetches the driving route between two points using OSRM in a single API call.
    Returns:
        - total_distance_miles: float
        - total_duration_hours: float
        - route_coordinates: list of [lat, lon] tuples along the road
        - encoded_polyline: compact polyline string for lightweight map rendering
        - simplified_coordinates: sampled [lon, lat] coordinates for fast GeoJSON payload
    """
    base_url = os.getenv("OSRM_API_URL", OSRM_DEFAULT_URL).rstrip("/")
    # OSRM expects coordinates in {lon},{lat} order
    url = f"{base_url}/route/v1/driving/{start_lon},{start_lat};{finish_lon},{finish_lat}"
    params = {
        "overview": "full",
        "geometries": "polyline",  # Google Encoded Polyline algorithm (100x more compact)
        "steps": "false",
    }

    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise ValueError(f"Routing service error: {exc}") from exc

    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError("Could not find a valid driving route between the specified locations.")

    route = data["routes"][0]
    distance_meters = route["distance"]
    duration_seconds = route["duration"]
    encoded_polyline = route["geometry"]

    # Decode polyline into [lat, lon] coordinates for corridor filtering
    coords = decode_polyline(encoded_polyline)

    distance_miles = distance_meters * 0.000621371

    # Simplify coordinates for the GeoJSON payload (sample ~every 15 points)
    # This reduces 30,000 points down to ~1,500 points (~50 KB instead of 3.2 MB)
    sample_rate = max(1, len(coords) // 1000)
    sampled_geojson_coords = [
        [round(pt[1], 5), round(pt[0], 5)]
        for i, pt in enumerate(coords)
        if i % sample_rate == 0 or i == len(coords) - 1
    ]

    return {
        "total_distance_miles": round(distance_miles, 2),
        "total_duration_hours": round(duration_seconds / 3600, 2),
        "route_coordinates": coords,
        "encoded_polyline": encoded_polyline,
        "geojson": {
            "type": "LineString",
            "coordinates": sampled_geojson_coords,
        },
    }


def decode_polyline(polyline_str: str) -> list:
    """
    Decodes an encoded polyline string into a list of [lat, lon] coordinates.
    Standard Google / OSRM polyline algorithm.
    """
    index, lat, lng = 0, 0, 0
    coordinates = []
    length = len(polyline_str)

    while index < length:
        # Decode latitude
        shift, result = 0, 0
        while True:
            byte = ord(polyline_str[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        # Decode longitude
        shift, result = 0, 0
        while True:
            byte = ord(polyline_str[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng

        coordinates.append([lat / 1e5, lng / 1e5])

    return coordinates
