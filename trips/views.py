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

    try:
        start_location = geocode_place(start_input)
    except ValueError as exc:
        return JsonResponse({"error": f"Invalid start location: {exc}"}, status=400)

    try:
        finish_location = geocode_place(finish_input)
    except ValueError as exc:
        return JsonResponse({"error": f"Invalid finish location: {exc}"}, status=400)

    return JsonResponse(
        {
            "start": start_location,
            "finish": finish_location,
        }
    )

