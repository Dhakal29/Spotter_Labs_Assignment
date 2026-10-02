import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .services.geocoding import geocode_place


@csrf_exempt
@require_POST
def plan_route(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Request body must contain valid JSON."},
            status=400,
        )

    if not isinstance(data, dict):
        return JsonResponse(
            {"error": "Request body must be a JSON object."},
            status=400,
        )

    for field in ("start", "finish"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            return JsonResponse(
                {"error": f"'{field}' must be a non-empty string."},
                status=400,
            )

    start_input = data["start"].strip()
    finish_input = data["finish"].strip()

    if start_input.lower() == finish_input.lower():
        return JsonResponse(
            {"error": "Start and finish locations cannot be the same."},
            status=400,
        )

    try:
        start_location = geocode_place(start_input)
    except ValueError as exc:
        return JsonResponse({"error": f"Invalid start location: {exc}"}, status=400)

    try:
        finish_location = geocode_place(finish_input)
    except ValueError as exc:
        return JsonResponse({"error": f"Invalid finish location: {exc}"}, status=400)

    # 1. Fetch driving route via OSRM (1 single API call)
    try:
        from .services.osrm import get_driving_route
        route_data = get_driving_route(
            start_lat=start_location["lat"],
            start_lon=start_location["lon"],
            finish_lat=finish_location["lat"],
            finish_lon=finish_location["lon"],
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    # 2. Find stations along the corridor (offline in local SQLite database)
    from .services.corridor import find_stations_along_route
    stations = find_stations_along_route(route_data["route_coordinates"])

    # 3. Compute optimal fuel stops (next-cheaper-station greedy algorithm, 500-mi range, 10 MPG)
    from .services.optimizer import optimize_fuel_stops
    fuel_plan = optimize_fuel_stops(route_data["total_distance_miles"], stations)

    if not fuel_plan.get("is_feasible", True):
        return JsonResponse(
            {
                "error": fuel_plan.get("error", "Route is physically infeasible with vehicle range."),
                "trip": {
                    "distance_miles": route_data["total_distance_miles"],
                    "duration_hours": route_data["total_duration_hours"],
                    "mpg": 10.0,
                    "max_vehicle_range_miles": 500.0,
                },
            },
            status=422,
        )

    return JsonResponse(
        {
            "start": start_location,
            "finish": finish_location,
            "trip": {
                "distance_miles": route_data["total_distance_miles"],
                "duration_hours": route_data["total_duration_hours"],
                "mpg": 10.0,
                "max_vehicle_range_miles": 500.0,
            },
            "fuel_optimization": {
                "total_fuel_cost_usd": fuel_plan["total_fuel_cost_usd"],
                "total_gallons_consumed": fuel_plan["total_gallons_consumed"],
                "total_gallons_purchased_en_route": fuel_plan["total_gallons_purchased_en_route"],
                "origin_fuel_price_usd": fuel_plan.get("origin_fuel_price_usd"),
                "total_stops": fuel_plan["total_stops"],
                "stops": fuel_plan["fuel_stops"],
            },
            "map": {
                "encoded_polyline": route_data["encoded_polyline"],
                "geojson": route_data["geojson"],
            },
        }
    )


def health_check(request):
    """Liveness probe for docker/kubernetes/monitors."""
    return JsonResponse({"status": "healthy", "service": "fuel-route-optimizer"})


