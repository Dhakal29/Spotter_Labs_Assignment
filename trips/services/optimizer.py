from typing import List, Dict, Any

MAX_RANGE_MILES = 500.0
MILES_PER_GALLON = 10.0
TANK_CAPACITY_GALLONS = MAX_RANGE_MILES / MILES_PER_GALLON  # 50.0 gallons
MIN_PUMP_GALLONS = 10.0  # Avoid stopping for trivial amounts (e.g. 1.2 gallons)


def optimize_fuel_stops(
    total_distance_miles: float,
    stations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Greedy Fuel Stop Optimizer:
    - Vehicle starts at mile 0 with a full tank (500 miles range).
    - Achieves 10 MPG (consumes 1 gallon every 10 miles).
    - Max range: 500 miles.
    - Picks practical, cost-effective stops along the route.
    """
    if total_distance_miles <= MAX_RANGE_MILES:
        gallons_needed = total_distance_miles / MILES_PER_GALLON
        return {
            "fuel_stops": [],
            "total_stops": 0,
            "total_gallons_purchased": round(gallons_needed, 2),
            "total_fuel_cost_usd": 0.0,
            "message": "Trip is under 500 miles. Completed on starting tank with no refueling needed.",
        }

    # Dedup stations within 15 miles of each other, keeping the cheapest option
    sorted_raw = sorted(stations, key=lambda s: s["mile_along_route"])
    filtered_stations = []
    for st in sorted_raw:
        if not filtered_stations:
            filtered_stations.append(st)
        else:
            prev = filtered_stations[-1]
            if st["mile_along_route"] - prev["mile_along_route"] < 15.0:
                if st["price"] < prev["price"]:
                    filtered_stations[-1] = st
            else:
                filtered_stations.append(st)

    chosen_stops = []
    current_mile = 0.0
    current_fuel_range = MAX_RANGE_MILES
    total_cost = 0.0
    total_gallons_bought = 0.0

    while current_mile + current_fuel_range < total_distance_miles:
        # Stations reachable with remaining fuel (leave a 30-mile reserve margin)
        safe_range = max(50.0, current_fuel_range - 30.0)
        reachable = [
            st for st in filtered_stations
            if current_mile < st["mile_along_route"] <= current_mile + safe_range
        ]

        # If safe buffer found nothing, take any station within raw remaining range
        if not reachable:
            reachable = [
                st for st in filtered_stations
                if current_mile < st["mile_along_route"] <= current_mile + current_fuel_range
            ]

        if not reachable:
            # If still nothing, take closest station ahead to avoid running empty
            ahead = [st for st in filtered_stations if st["mile_along_route"] > current_mile]
            if not ahead:
                break
            best_station = ahead[0]
        else:
            # Look ahead: is there a significantly cheaper station within next 500 miles?
            cheapest_in_reach = min(reachable, key=lambda s: s["price"])
            best_station = cheapest_in_reach

        # Drive to best_station
        distance_driven = best_station["mile_along_route"] - current_mile
        current_fuel_range -= distance_driven
        current_mile = best_station["mile_along_route"]

        # Fill up to max range (500 miles)
        range_to_fill = MAX_RANGE_MILES - current_fuel_range
        gallons_to_fill = range_to_fill / MILES_PER_GALLON
        cost_at_stop = gallons_to_fill * best_station["price"]

        current_fuel_range += range_to_fill
        total_cost += cost_at_stop
        total_gallons_bought += gallons_to_fill

        chosen_stops.append({
            "stop_number": len(chosen_stops) + 1,
            "station_name": best_station["name"],
            "address": best_station["address"],
            "city": best_station["city"],
            "state": best_station["state"],
            "price_per_gallon": best_station["price"],
            "mile_along_route": round(best_station["mile_along_route"], 1),
            "gallons_refueled": round(gallons_to_fill, 2),
            "cost_usd": round(cost_at_stop, 2),
            "coordinates": {
                "latitude": best_station["latitude"],
                "longitude": best_station["longitude"],
            },
        })

    return {
        "fuel_stops": chosen_stops,
        "total_stops": len(chosen_stops),
        "total_gallons_purchased": round(total_gallons_bought, 2),
        "total_fuel_cost_usd": round(total_cost, 2),
    }
