import requests

# Bounding box for contiguous United States
USA_BOUNDS = {
    "lat_min": 24.396308,
    "lat_max": 49.384358,
    "lon_min": -125.000000,
    "lon_max": -66.934570,
}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "SpotterLabsFuelOptimizer/1.0"}


def is_within_contiguous_bounds(lat: float, lon: float) -> bool:
    """Check if coordinates fall within the contiguous US bounding box."""
    return (
        USA_BOUNDS["lat_min"] <= lat <= USA_BOUNDS["lat_max"]
        and USA_BOUNDS["lon_min"] <= lon <= USA_BOUNDS["lon_max"]
    )


def geocode_place(location_name: str) -> dict:
    """
    Geocodes a place name string (e.g. 'Austin, TX') strictly within the USA.
    Returns a dict with:
        - 'lat': float
        - 'lon': float
        - 'display_name': str
    Raises ValueError if the location is not found or is outside the USA.
    """
    clean_name = location_name.strip()
    if not clean_name:
        raise ValueError("Location name cannot be empty.")

    params = {
        "q": clean_name,
        "format": "json",
        "limit": 1,
        "countrycodes": "us",
    }

    try:
        response = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=6)
        response.raise_for_status()
        results = response.json()
    except requests.RequestException as exc:
        raise ValueError(f"Geocoding service unavailable: {exc}") from exc

    if not results:
        raise ValueError(f"Location '{location_name}' could not be found within the USA.")

    first_hit = results[0]
    lat = float(first_hit["lat"])
    lon = float(first_hit["lon"])

    if not is_within_contiguous_bounds(lat, lon):
        raise ValueError(
            f"Location '{location_name}' is outside the contiguous USA ({lat}, {lon})."
        )

    return {
        "name": location_name,
        "display_name": first_hit.get("display_name", location_name),
        "lat": lat,
        "lon": lon,
    }
