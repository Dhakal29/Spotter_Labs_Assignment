import hashlib
import requests
from django.core.cache import cache

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


# Categories that represent valid geographic destinations for trip routing
VALID_PLACE_CLASSES = {"boundary", "place", "highway", "waterway"}
DISALLOWED_CLASSES = {"amenity", "shop", "tourism", "leisure", "office", "craft"}


def geocode_place(location_name: str) -> dict:
    """
    Geocodes a place name string (e.g. 'Austin, TX' or '90210') strictly within the USA.
    Ensures the matched location is a geographic destination (city, town, state, county, postcode),
    not a commercial point of interest like a restaurant or shop.
    Uses in-memory cache to prevent redundant external API calls and rate-limiting.
    """
    clean_name = location_name.strip()
    if not clean_name:
        raise ValueError("Location name cannot be empty.")

    key_hash = hashlib.md5(clean_name.lower().encode("utf-8")).hexdigest()
    cache_key = f"geocode_{key_hash}"
    cached_result = cache.get(cache_key)
    if cached_result:
        return cached_result

    params = {
        "q": clean_name,
        "format": "json",
        "limit": 5,
        "countrycodes": "us",
        "addressdetails": 1,
    }

    try:
        response = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=6)
        response.raise_for_status()
        results = response.json()
    except requests.RequestException as exc:
        raise ValueError(f"Geocoding service unavailable: {exc}") from exc

    if not results:
        raise ValueError(f"Location '{location_name}' could not be found within the USA.")

    # Filter out commercial amenities/shops, prioritize genuine geographic places
    selected_hit = None
    for hit in results:
        hit_class = hit.get("class", "")
        if hit_class in DISALLOWED_CLASSES:
            continue
        if hit_class in VALID_PLACE_CLASSES or hit.get("addresstype") in {
            "city",
            "town",
            "village",
            "hamlet",
            "suburb",
            "county",
            "state",
            "postcode",
            "road",
            "motorway",
        }:
            selected_hit = hit
            break

    if not selected_hit:
        raise ValueError(
            f"Location '{location_name}' does not match any valid geographic city or region in the USA."
        )

    lat = float(selected_hit["lat"])
    lon = float(selected_hit["lon"])

    if not is_within_contiguous_bounds(lat, lon):
        raise ValueError(
            f"Location '{location_name}' is outside the contiguous USA ({lat}, {lon})."
        )

    result = {
        "name": location_name,
        "display_name": selected_hit.get("display_name", location_name),
        "lat": lat,
        "lon": lon,
    }
    cache.set(cache_key, result, timeout=86400)
    return result

